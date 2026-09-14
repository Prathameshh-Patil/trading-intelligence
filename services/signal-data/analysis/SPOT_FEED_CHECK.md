# Route 2, step one — Dukascopy is reachable, and it was never a reachability problem

**Run 2026-09-07.** [`docs/strategy/ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §4.1
asked for *"a ten-minute check that a download completes"* before anything else in Route 2. This is
that check. Decoder and its tests: [`dukascopy.py`](../dukascopy.py),
[`tests/test_dukascopy.py`](../tests/test_dukascopy.py).

```sh
PYTHONPATH=. uv run python -c "
import pandas as pd, dukascopy as dk
print(dk.fetch_hour('XAUUSD', pd.Timestamp('2025-06-18T14:00:00Z')))"
```

**This does not choose a vendor.** Step 6 is unscheduled (`strategy-split.md` §9) and the vendor
decision is the room's. What this does is replace *"unverified"* with numbers.

---

## 1. The verdict

> ## ⚠️ AMENDED 2026-09-11 — this verdict is true for one hour and false for a backtest
>
> **The datafeed endpoint has blocked this IP, and 22 hours was not enough for it to clear.**
> Attempting step 6's bulk pull, roughly 40–60 requests over an evening were enough to trip it.
> Since then every request to `datafeed.dukascopy.com` returns a 503, a connection reset or a
> timeout — **across three header sets, across instruments (`EURUSD` too), and through `curl`
> as well as `urllib`**, so it is neither a client bug nor the `User-Agent` problem §2 diagnoses.
> Controls run in the same second: `example.com` 200 and **`www.dukascopy.com` itself 200**, so
> the network is fine and only the data endpoint is refusing us.
>
> **What that does to the claim below: "free, complete and decodable" survives; "usable as a
> backtest source" was never tested and does not.** One hour is a spot check. 19 months is
> ~13,900 hour-files, three months is ~2,200, and this endpoint does not tolerate either from one
> address. A free feed you cannot bulk-pull is a different proposition from a free feed, and that
> belongs in the vendor decision rather than in a footnote.
>
> **Nothing below is retracted** — the spread numbers, the quote rate and the decoder are all
> still good, and `dukascopy.py` is still correct. What changed is what the result licenses.

> ## 🔄 RE-MEASURED 2026-09-14 — it is a request budget, not a blanket refusal
>
> **The 11 Sep amendment said "every request returns a 503, a reset or a timeout". That is no
> longer what happens, and the correction matters because it changes what to build.** Three cold
> probes returned real payloads — 49,523 bytes, 104,222 bytes, and a zero-byte hour that is a
> legitimate answer (2026-05-10 is a Sunday). Then, sequentially from the same address:
>
> ```
> pull, 2026-07-01          14 of 24 hours ok, 10 LOST, 519s
> pull, 2026-07-02 00h      LOST
> 8 probes @ 6s pause       0 of 8, after a 90s cooldown
> ```
>
> **~17 successful requests from cold, then the wall, and 90 seconds does not lift it.** The
> post-wall failures are immediate rather than timeouts — refusal, not congestion.
>
> **The recovery probe is the decisive part. 8 attempts across 13h 40m, every one refused:**
>
> ```
> 00:13  00:18  00:23  02:26  07:31  09:05  13:37  13:53      all fail
> ```
>
> ⚠️ **The probe was written to fire every five minutes and the machine slept**, so its own `t+N`
> labels are wrong and the intervals are uneven. The span and the outcome are what the run
> supports; the cadence is not. Consistent with 11 Sep's "22 hours was not enough".
>
> **So the budget is ~17 requests and the period is longer than half a day — call it ~17
> hour-files a day:**
>
> ```
> 3 months     2,208 hour-files    ~130 days
> 19 months   13,896 hour-files    ~817 days
> ```
>
> **That closes it. Dukascopy is finished as a bulk source from this address** — not "throttled"
> and not "retry tomorrow". §5's cost model below should be read as superseded: it prices a
> download this endpoint will not serve.
>
> **A longer pause is not the lever, and that retires the theory `PAUSE` was raised on.** 0 of 8 at
> six seconds is *worse* than 14 of 24 at two, because the budget is consumed cumulatively rather
> than per unit time. §5's cost model below is a throughput calculation and this is not a
> throughput limit; plan against requests-per-period instead, once that number exists.
>
> **What this changes about the verdict: nothing, and that is worth saying plainly.** "Free,
> complete and decodable" still survives. "Usable as a backtest source" still does not — a
> ~17-request budget against 2,208 hour-files for three months is not closer to usable than a
> blanket 503 was. What changed is the *shape* of the obstacle, which is what a fix has to fit.
>
> ⚠️ **It also exposed a defect in `spot.py` that the blanket 503 had been hiding.** `pull()`
> resumed by **day** — it accumulated 24 hours and discarded all of them if any one was lost. With
> a budget under 24 that loop is **non-convergent**: every pass burns the budget, throws the result
> away, and leaves the next pass where the last one started. Re-running it forever would have
> produced nothing, and it would have been read as the block never clearing. **Fixed the same day:
> resume is now by hour**, with the day parquet still written only when all 24 are present, so the
> no-holes-on-disk invariant is unchanged. 330 tests pass and the mutation fails.

**The feed works. XAUUSD tick history is free, complete and decodable, and the spread is not
degenerate.** One hour, 2025-06-18 14:00 UTC — a Wednesday in the London–NY overlap:

| | |
| :--- | ---: |
| quotes in the hour | **20,654** |
| quote rate | **344 / min** |
| mid | 3373.861 … 3392.471 |
| spread, median | **1.91 bp** |
| spread, p10 / p90 | 1.64 / 2.15 bp |
| spread, max | 3.77 bp |
| fetch + decode, warm | **1.2 s** |

## 2. It was never a reachability problem — it is a `User-Agent` problem

**A request without a browser `User-Agent` is reset, not refused.** No status code, no body:
`Recv failure: Connection reset by peer` after a ~25-second hang, then a plain timeout on retry.
That is indistinguishable from an unreachable host, and **it is very likely what
[`DELTA_CVD_FINDINGS.md`](DELTA_CVD_FINDINGS.md) §4 recorded as "unreachable".**

With a `User-Agent` header the identical URL returns 200. Diagnosed by controls rather than assumed
— `github.com` 200 and `www.dukascopy.com` 302 from the same shell in the same second, so the
network was fine and the host was answering.

**The lesson is not about Dukascopy.** A negative infrastructure result that was never
differential-diagnosed sat in this repo for weeks and gated a whole route of the strategy track. One
control request would have separated "host is down", "we are firewalled" and "the host dislikes our
headers", and those have completely different costs.

## 3. Cross-checked against our own GC archive, same hour

The check that a spot feed is the instrument it says it is, at the scale it says it is. Same hour,
2025-06-18 14:00–15:00 UTC:

| | range |
| :--- | :--- |
| GC futures (`data/2025-06`) | 3391.70 … 3411.50 |
| XAUUSD spot (this feed) | 3373.86 … 3392.47 |
| basis, GC − spot | **≈ +19** |

**+19 on ~3,390 is cost of carry**, which is what a futures–spot basis should be at those rates and
that time to delivery. It is emphatically **not** a 10× or 0.1× mismatch — which is exactly the
error §4.6 exists to prevent, and the one a guessed point scale would produce. `dukascopy.POINTS`
carries the scale explicitly and refuses an instrument it has no scale for.

## 4. What this closes, and what it does not

**Closes §4.1's open item.** Dukascopy is reachable from this machine and Route 2's step one
passes. `ARCHITECTURE.md` §9's open question 3 can be marked answered.

**Bears on §7's open experiment — *does top-of-book spread carry enough structure to filter on?***
§7's reasoning was that GC's spread is probably degenerate (one tick, overwhelmingly) while spot
spread "genuinely moves". **On this hour it moves**: 1.64 bp at p10 against 2.15 at p90 and 3.77 at
the max, so a trailing z-score has something to work with and is not a z of a near-constant.

**It does not show that spread predicts anything.** One hour, one session, one broker. It shows the
variable is non-degenerate, which is the precondition §7 doubted — not the result §7 asks for.

**§7's caveat survives intact and is repeated because it is easy to lose:** spot spread is a
**broker pricing decision, not a market outcome**. Two brokers disagree about the same instant. Any
result here is a yes/no on whether spread structure predicts anything, and **never a threshold that
transfers** to GC or to another broker.

## 5. What a bulk pull would cost, measured

**Warm, a good hour is 1.2 s.** Under sequential load it is worse and it fails:

```
10h  33,413 B  10.0 s
11h  37,870 B  11.2 s
12h       0 B  16.2 s   <- connection reset, WITH the User-Agent set
13h  57,492 B  21.6 s
```

**One request in four was reset on a warm connection**, and the failure is a reset rather than an
HTTP status, so `raise_for_status` never sees it. `fetch_hour` retries with backoff on exactly the
exceptions this produced.

19 months is roughly **10,000 hourly files**. At the sequential rate above that is many hours and
needs retry bookkeeping — **not a ten-minute job, and it should be a resumable script that verifies
what it already has**, the same discipline `pull_futures_trades.py`'s raw cache applies. The GC
restore on 6 Sep is the cautionary case: `fetch_or_load` reuses any cache file it finds without
validating it, and only the manifest's `sha256` caught a partial download.

## 6. Two traps recorded so nobody pays for them twice

- **The month in the URL is zero-indexed.** June 2025 is `/2025/05/`. An off-by-one returns a
  **real file for the wrong month** — it downloads, it decodes, it looks entirely fine, and it is
  May. Pinned by `test_the_month_in_the_url_is_zero_indexed`.
- **An hour with no ticks is a zero-byte file, not a 404.** Weekends and the daily break arrive
  this way; 2025-06-21 (Saturday) 14:00 UTC returns 0 quotes in 0.8 s. `decode_bi5` returns an
  empty frame rather than raising, because on a 24×5 instrument the gap is the normal case and a
  retry loop should not chase a hole that is meant to be there.

## 7. The MT5 fallback, assessed 2026-09-14 — read from the documentation, not from a terminal

⚠️ **Nothing here was run. No broker account exists, no terminal is installed, and not one tick
has been exported.** This is a desk check of §7.4's second free source done *before* a signup, on
the principle that the signup is the expensive part. Everything below is a documentation claim with
a source, and every one of them needs confirming against a real terminal before it is worth
anything. Two of them are load-bearing enough that the signup should not happen until they are.

**The Python API is Windows-only, and that is not the obstacle it looks like.** The official
`MetaTrader5` package requires the Windows terminal; on macOS it needs Wine/CrossOver or a
Docker-QEMU bridge (`mt5-mac`, `mt5linux`, `silicon-metatrader5`), and `plans/current.md`'s row B
already records that **there is no Windows or Linux dev machine in the loop**. But the export does
not need Python: an **MQL5 script runs inside the terminal**, which has an official macOS build,
and `CopyTicksRange` writes CSV directly. The `Historex` script in the MQL5 Code Base already does
exactly this with a `FilterStart`/`FilterStop` date range. **So the platform objection is real for
the *API* and does not reach the *export*.**

### ⛔ The finding that decides it: depth, and what lives past the edge

**Real tick history in MT5 is served by the broker, and the depth is the broker's choice — commonly
1–3 months.** Nineteen months of *real* spot ticks from a demo account should be assumed
unavailable until a specific broker proves otherwise. **That retires the 19-month target for this
source** and leaves the 3-month one, which is the smaller of the two already in the plan and which
a single dated export could satisfy outright — no throttle, no 130 days, no resume bookkeeping.
On depth alone, MT5 is a plausible 3-month source and not a 19-month one.

**And the part that would quietly poison the result.** MT5's Strategy Tester documents that when a
minute bar has no tick data it **generates ticks from the M1 bar using a fixed spread inside the
bar**. Route 2's entire question is *does spot bid/ask spread vary enough to filter on* — so a
generated tick does not merely add noise, it **answers the question by construction**, and it
answers it wrongly in the confident direction: a fixed intra-bar spread reads as a degenerate
spread, which is precisely the null §7 was built to test. **A study fed generated ticks would
conclude "spot spread is degenerate" and be measuring MetaQuotes' interpolation.**

This is the same shape as the trap the day-completeness invariant exists to stop — an absent hour
reading as a calm one — and it deserves the same treatment: **make it impossible rather than
remember it.**

⚠️ **One distinction is deliberately left open, because the documentation does not close it.** Tick
generation is documented as **Strategy Tester** behaviour. Whether a terminal-side
`CopyTicksRange` export can *also* contain synthesized ticks is **not established here**, and it
would be dishonest to assert it either way from the docs alone. The point is that the question has
an empirical answer and does not need a ruling: **the `flags` field settles it per tick.**

### The acceptance test, to be passed before any MT5 tick is trusted

`MqlTick` carries a `flags` bitmask — `TICK_FLAG_BID` / `TICK_FLAG_ASK` mark a tick that actually
moved the bid or the ask. **Any export used for route 2 must carry that column**, and this is the
second reason to prefer the MQL5 script over the GUI: the MQL5 forum reports the **`Flags` column
missing from GUI-exported tick CSV**, and an export without it cannot be audited at all.

So, in order, and none of it costs a signup until step 3:

1. **Name the broker and check the depth first** — the Symbols panel (`Ctrl+U`) reports available
   tick history per symbol. A broker that does not serve 3 months of real XAUUSD ticks ends this
   route before an account is opened.
2. **Export via `CopyTicksRange`, keeping `flags`.** GUI export is not acceptable.
3. **Refuse the file if the flags do not vouch for it.** A loader for this source must reject an
   export with no `flags` column outright, and must not average a spread over ticks that never
   moved a quote. This is a hard failure, not a warning — the whole value of the source is that
   the spread is a real one.

**What this does not change.** Spot spread is a broker's pricing decision, so §6's standing caveat
holds exactly as written: the result is a **yes/no on the hypothesis and never a threshold that
transfers** to GC or to another broker. A demo account's spread is additionally not guaranteed to
be its live spread, which weakens the yes/no but does not invalidate it.

### ⛔ Amendment, same day: an MT5 demo account now exists, and it is the wrong one

`54ac312` closed Week 1's gate line #3 against **a real MetaQuotes demo account (XAUUSD M5) in the
MT5 web terminal**. So step 1 above appears answered — an account exists and nobody has to sign up.
**It is not answered, and using that account would produce a confidently wrong result.** Two
reasons, and the second is disqualifying:

1. **The web terminal cannot run MQL5 scripts, EAs or indicators.** Custom code is desktop-terminal
   only. So that account supplies no export path at all — not a `CopyTicksRange` one, and the GUI
   tick export the web terminal lacks is the one that drops `flags` anyway. The desktop terminal
   (macOS build) with the same credentials is a different question from the web terminal.
2. ⛔ **`MetaQuotes-Demo` is not a broker.** MetaQuotes does not operate a live venue, and the demo
   server exists to exercise the platform and its beta builds. Its prices are widely reported to
   diverge from real brokers' — there is a forum thread asking whether its XAUUSD is artificial,
   another titled *"real ticks in MetaQuotes Demo account are missing"* — and MetaQuotes' own
   guidance is not to rely on the feed.

**Why (2) ends it rather than complicating it.** Route 2 asks whether **a broker's** spot bid/ask
spread varies enough to filter on. §6's standing caveat — *spot spread is a broker pricing decision,
so the answer is a yes/no and never a transferable threshold* — assumes there is a broker. On
`MetaQuotes-Demo` there is not one, so a spread measured there is **MetaQuotes' demo price generator
and nothing else**. That is the same "plausible number from the wrong population" this repo keeps
naming, arriving this time through a convenient account rather than a file copy.

⚠️ **Weigh the evidence honestly.** (1) is a documented platform limitation. (2) rests on user
reports and an absence — MetaQuotes publishes no claim that its demo carries real broker ticks,
which is not the same as a documented statement that it does not. It is enough to disqualify the
server for a measurement whose entire content is *whose* spread this is, and not enough to call the
prices fabricated.

**So step 1 stands exactly as written, with one name struck out:** the depth check must run in the
**desktop** terminal against a **real broker's** demo server, and `MetaQuotes-Demo` is not a
candidate. The existing account closes a gate line; it does not open this route.
