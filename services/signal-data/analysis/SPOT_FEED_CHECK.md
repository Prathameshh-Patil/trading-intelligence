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
