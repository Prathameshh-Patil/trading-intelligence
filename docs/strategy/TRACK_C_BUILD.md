# Track C as built — four mathematical strategies, and where it stops

**Written 2026-09-18.** This is the build record for
[`TRACK_C_ENGINE.md`](TRACK_C_ENGINE.md)'s plan, and it **changes that plan in one structural way**
which is stated first because everything else follows from it.

> **Status: code complete through build step 3; steps 4–5 unrun.** 22 modules, ~2,400 lines under
> `services/signal-data/track_c/`, 126 new tests (660 passing repo-wide), `ruff` and `mypy` clean.
> **No result is claimed, because no market data has been read.**
>
> **Amended 2026-09-19 — §6.1.** The blocker is no longer "credentials, full stop": the HTTP
> datafeed's rate limit has lifted, `preload --transport http` pulls the same days with no AWS
> account, and S3 stays the default and the bulk path. **The first real pull still did not
> complete**, and E1–E4's predictions still gate any claim. Read §6.1 before §7.

---

## 1. What changed from the plan: one strategy became four, and nothing is fitted

`TRACK_C_ENGINE.md` describes **one** strategy — §9's sweep-and-reclaim event, scored by §13's
weighted sum, gated on §8's isotonic-calibrated logistic and §7's 3-state HMM. The build brief of
18 Sep replaces that with **three to four structurally independent strategies, every input a
closed-form quantity of OHLC bars, and no fitted model anywhere**.

That is not a smaller version of the plan. It removes two of its four blockers outright:

| Plan blocker | Status under the new brief |
| :--- | :--- |
| **E4's verdict on the HMM** (`p_expand` is NaN on every row, so `fsm_row` refuses every row) | **Dissolved.** None of S1–S4 reads `p_expand`, `p_e`, `s_hmm` or `classifier.py`. The HMM cannot gate what nothing consumes. |
| **The granularity decision** (§6's 15-minute Hurst cannot come from 5-minute bars) | **Decided by the user:** 5-minute is the trading resolution, 1-minute exists to audit what 5-minute cannot resolve. Hurst is computed on the trading resolution over a 256-bar window and the decision is recorded in `config/track_c.toml`. |
| **E1–E4 predictions unwritten** | Still open, and still binding on any *claim*. It does not block the code, and no claim is made below. |
| **AWS credentials for the requester-pays bucket** | **The blocker the build stops at — narrowed 19 Sep, not removed.** There is now a second transport that needs no account, but it is a bounded-window path and its first real pull aborted. §6 and §6.1. |

**What is reused rather than re-spelled** — `features/volatility.py` (Yang-Zhang),
`features/hurst.py` (DFA + variance-time + agreement), `features/expansion.py` (ATR),
`features/structure.py` (session windows, §12 lockout, §9's reclaim delta), `e3_cost.py` (target
floor and cap, cost arithmetic), `fsm.py` (§10's stop bounds, §11's sizing, `Day`), `tuning.py`
(purged folds, `Trials`, deflated Sharpe), `backtest.first_touch_from` (the first-touch convention,
in the audit), `spot.py` (ticks → bars), `instruments.py`, `calendars.py`.

**What is new and Track C's own** — the level universe, the four strategies, the funnel counter, the
pessimistic fill model, the event loop with day state, R-based metrics, the walk-forward driver, the
report, the CLI, and the intra-bar audit.

---

## 2. The four strategies, and the evidence that they are four

The brief asks for strategies that differ *in kind*. The claim is held by tests, not by prose:
`tests/test_track_c_strategies.py` asserts the gates are mutually exclusive and exercises 300 random
rows to show S1 and S3 never both fire.

| | Idea | Level comes from | Regime it needs | Entry |
| :--- | :--- | :--- | :--- | :--- |
| **S1** | Asian-range breakout | **the clock** — a fixed level all session | Expansion: `vol_ratio ≥ 1.15`, `H ≥ 0.50` | buys strength |
| **S2** | Prior-day extreme swept, then reclaimed | **the previous session** | Range: `H ≤ 0.55` | buys the failure of S1's break |
| **S3** | Session-VWAP mean reversion, `\|z\| ≥ 2` | **no level** — a mean | Chop: `H ≤ 0.45`, `vol_ratio ≤ 0.90` | fades the excursion, hard 2-hour time stop |
| **S4** | Momentum out of a Bollinger squeeze | **volatility** — a moving level | Build→expansion: width in its own bottom fifth, `H ≥ 0.50` | buys the start of the move |

Every entry is a **passive limit placed back from the close** (`0.25 × ATR`), with §9's 20-second
life. It is never converted to a market order. Every stop is **structural** and every one outside
§10's `[$2, $5]` is a **refusal, never a clip** — a clipped stop sits behind nothing and is a
different trade with the same name.

**`confidence` is an ordinal score in [0, 1], not a probability.** It is a deterministic function of
how far the continuous conditions were cleared by. Nothing is calibrated, because nothing is fitted.

---

## 3. Two findings that came out of the build, before any market data

**(1) §13's cost exclusion narrows §10's stop band to about half a dollar.** §13 refuses a trade
whose cost exceeds a quarter of intended risk. The modelled round trip is `1.75 × spread` — one
spread crossed (half at each end, `e3_cost`'s rule) plus half a spread of slippage at the 1.5×
margin — so the exclusion is `D ≥ 7 × spread`. At the spread `SPOT_FEED_CHECK.md` measured on
XAUUSD (1.91 bp, about **$0.65/oz** at $3,400) that is **D ≥ $4.55**, against §10's cap of $5.00.

Both rules are the spec's, and neither is wrong. Together they say the structural stop must land in
a half-dollar-wide window or the trade is refused before anything else is measured. Pinned in
`test_section_13s_cost_exclusion_narrows_section_10s_stop_band`.

**(2) A defect in this build's own first draft, corrected before the first run.** `s1.range_min_atr`
and `range_max_atr` were 0.5 and 3.0 — comparing a **six-hour** Asian range against a **one-hour**
ATR, horizons that differ by a factor of six. On a synthetic archive `range_width` refused **100%**
of bars: the strategy was untestable by construction, and it would have read as "the filter is
selective" rather than as an error. Corrected to 2.0 and 12.0 from the diffusion scaling argument
(√6 ≈ 2.4 hourly ranges, and a max-minus-min runs 2–3× the average true range at the same horizon,
so 4–7× is neutral; a random walk's 1st–99th percentiles measure 3.6 and 10.9). **The pair is a
degeneracy guard, not a selective filter, and its pass rate in the attrition table will be near 1.**
That is said in the config so nobody later reads a near-1 pass rate as a broken filter.

---

## 4. What the engine produces

`python -m track_c {preload, suggest, backtest, walkforward, audit, report, live}`.

**`suggest` is the one public entry** and both the live path and the backtest path go through it, so
they cannot disagree. It returns one outcome per strategy: a `Suggestion` carrying side, entry
limit, stop, target, lots, expiry and confidence — or a `Refusal` naming the condition that stopped
it and that condition's position in its strategy's ordered list.

**A refusal is the normal return value**, which is what makes the attrition table possible. The
report puts that table *before* the metrics, for the reason E2 puts it first: "of 20,000 bars,
19,994 were refused, and here is the stage that refused them" is a statement about the archive,
whether or not the six survivors made money.

**Every fill is flagged unresolved.** §9's limit lives 20 seconds; a 5-minute bar cannot say whether
it was touched inside that life, and neither can a 1-minute one. `fills.resolves_limit` returns
False and every report header says the numbers are upper bounds. `audit.py` measures the size of the
gap — how many 5-minute fills the first *minute* after the signal does not confirm, and how many
resolved outcomes flip at 1-minute resolution — and it does not close it. **Only a tick replay
does.**

---

## 5. Verification, and what it does and does not cover

```
uv run pytest -q          660 passed   (534 before)
uv run ruff check .       All checks passed
uv run mypy .             Success: no issues found in 103 source files
```

Covered by fixtures whose answer is known by construction: the three places lookahead could enter
(the Asian range is NaN until its window closes; prior-day extremes are the previous session's;
Donchian excludes the bar that breaks it), both Hurst estimators reading the same scale set, the
pessimistic fill rules, the same-bar tie pinned against `backtest.first_touch_from`, break-even at
1.5D, the daily caps, the funnel's arithmetic, and a purity scan that fails the build if any Track C
module imports or names anything tape-derived.

**Not covered, because there is no data:** every number a strategy would produce on the real
archive. The end-to-end test runs on a random walk and asserts nothing about profitability — a
random walk has no edge, and an assertion that it did would be the test fitting itself.

---

## 6. The blocker, stated exactly

```
$ PYTHONPATH=. python -m track_c preload --months 2026-08
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

`~/.aws/` does not exist and `data/spot/XAUUSD/` is **empty — zero bytes, zero days**. Dukascopy's
XAUUSD history is a requester-pays S3 bucket (`spot_s3.py`), so every object is billed to the caller
and authenticated; ~$0.12 for five years by E0's own measurement.

**Until a scoped IAM user exists, steps 4 and 5 of the build order cannot run:** no preload, no
walk-forward, no gate table with numbers in it, no intra-bar audit. The machinery for all four is
written and tested; what it lacks is bars.

**What is deliberately not done instead:** nothing is run on GC futures as a stand-in, and no
synthetic result is reported as if it were a measurement. Track C is a spot XAUUSD engine; a number
from another instrument would be a different measurement wearing this one's name.

### 6.1 Amended 2026-09-19 — the blocker is now a bounded choice, and still unrun

**"Requester-pays, therefore credentials" is no longer the whole story.** `spot_s3.py` chose S3
because the HTTP datafeed served ~2 requests and then returned 429, unlifted after 40 minutes.
**Re-measured 19 Sep: that limit is gone** — a sequential day paced 1s apart returns 20 of 24
hours. `spot.pull`'s `fetch` seam accordingly has a second implementation, `dukascopy.fetch_day`,
and `preload --transport {s3,http}` selects it; `s3` stays the default.

**It does not retire step 1 and the credential task is still worth doing.** HTTP runs ~3–5 minutes
a day — a month in an hour, and **the five years this walk-forward wants in ~120 hours** — against
one S3 object a day at ~$0.12 total.

⛔ **And the first real pull did not complete.** 2026-08 aborted on 2026-08-01: **503 is returned
both by the throttle and by hours the market was shut**, the two cannot be separated by status
code, and after ~120 requests the feed stopped answering rather than refusing. `fetch_day` aborts
the day rather than guessing — treating a 503 as an empty hour would write a throttled weekday as
a calm session, which is §4's "a hole looks exactly like a quiet day" failure arriving through the
transport. **Whether a session calendar belongs at the pull level is left open on purpose.**

### 6.2 Superseded the same night — the day object, and bars on disk

**§6.1's "bounded window" was a limit of the unit of work, not of the feed.** `E0_TRANSPORT.md` §1
recorded that the bucket holds a day's ticks as a **sibling object at month level**; the HTTP
datafeed turns out to serve the same path. **One request per day, not 24** — five years is 1,776
requests rather than ~43,800 — and hour 13 of 2026-08-03 from the day object is **identical row for
row** to `13h_ticks.bi5` (20,758 quotes, timestamp/bid/ask). A shut day is **HTTP 200 with zero
bytes**, which `decode_bi5` already reads as a shut market, so the ambiguity §6.1 worked around
disappears and the `SHUT`/`BOUNDARY` table was deleted with it.

**So the credential blocker is gone, not narrowed.** `preload --transport http` is an archive
transport at full tick resolution. **53 days / 119 MB of real XAUUSD ticks are on disk** and the
rest of the three-month window is filling by paced passes.

🔴 **And the real bars sharpen §3 — §3 was closer than it knew.** §3 records §13's exclusion
narrowing §10's `[$2,$5]` band to ~$0.45, reasoning from `SPOT_FEED_CHECK.md`'s single quoted
1.91 bp at $3,400. **Measured over June 2026 — 6,024 bars, median close $4,224 — the spread median
is 1.452 bp**, and the exclusion eats the band from the bottom rather than shifting it:

| spread | `D` needed (`7 x spread`) | left of `[$2, $5]` |
| :--- | :--- | :--- |
| p10 1.201 bp | $3.55 | $1.45 |
| **p50 1.452 bp** | **$4.29** | **$0.71 — 24% of the band** |
| p75 1.696 bp | $5.01 | **empty** |

So a median bar admits a structural stop only inside a **71-cent window**, and **the widest quarter
of bars admit none at all**. The attrition table shows the mechanism: `slippage` refuses almost
nothing because **`stop_too_wide` refuses first** (s2 7 → 0). §10 is in dollars and §13 is a
fraction of price, so the surviving window moves when gold does with no config edit to show for it.
**A spec decision for the room — §10's cap, §13's share, or a band that scales with price.**

🔴 **And on the full three-month archive, §13 turns out not to be the binding constraint at all.**
92 days, 20.8M ticks, 18,120 bars → **four suggestions; s3 and s4 produced none.** `stop_too_wide`
refused **16 of 17** (s1), **36 of 41** (s2), **8 of 8** (s4), while **`stop_too_tight` refused
nothing in any strategy**. §10's `[$2,$5]` is 20–50 ticks at GC's $0.10 tick — a futures spec
carried onto spot — and the **60-minute ATR median is $4.53, 91% of the whole cap**, with **40.2%
of bars above $5.00** on ATR alone. A structural stop sits behind the noise; on this instrument at
this volatility it does not fit in §10. **That is the decision that governs whether Track C trades
gold at all, and §7 below should not run before it is taken.**

**E1–E4's predictions still gate any claim.** Bars do not license one.

---

## 7. What happens when the credentials exist

In order, and each is a commit that runs:

1. `preload --months 2021-09 … 2026-09` — **once, not twice.** Corrected 2026-09-19: this line
   read "5-minute bars, then again for the 1-minute audit frame", and there is no second pull.
   `preload` caches **ticks**; `cli.load_bars` and `cmd_audit` both resample the same cached days,
   at `[data].bar` and `[data].audit_bar` respectively. **That the two frames come from one pull is
   the point** — `cmd_audit`'s docstring says so: the only difference between them is resolution,
   which would not hold if one side came from a different fetch.
2. `backtest` — attrition table first. **Read it before anything else.** Two outcomes are bad in
   opposite directions: a stage that refuses everything (untestable), and a late stage still holding
   thousands of bars (the conditions condition on nothing).
3. `audit` — how much of the 5-minute answer came from four extra minutes of hindsight.
4. `walkforward` — the windows, the holdout opened **once**, and §7's eight gates.
5. `report` — one markdown file, gate table first, assumptions in the header, KEEP/KILL per
   strategy. **A strategy that fails is killed and the reason printed. No re-tune follows.**

The gates and every threshold were committed **before** the first run, in this commit. A gate chosen
after seeing an equity curve is not a gate — and the four strategies' own thresholds are in
`config/track_c.toml`, each beside the decision that set it.
