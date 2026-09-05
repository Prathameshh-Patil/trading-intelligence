# Reconciling the two L1-only strategy proposals

**Date:** 2026-09-06 · **Status:** reconciliation. Nothing is built; this resolves which four go forward.
**Inputs:** [`four-l1-strategies.md`](four-l1-strategies.md) (a12d87d) · [`strategy-architecture.md`](strategy-architecture.md) (e4a10f3)
**Both read:** [`xauusd-regimes.md`](xauusd-regimes.md)

---

## 1. Verdict

The two documents were written independently, hours apart, and **agree on every structural
conclusion.** That convergence is worth more than either document on its own, and §2 records it
because it is now settled and should not be re-argued.

They disagree on which four strategies fill the slots, and one of those disagreements is decided by
a fact neither document checked: **there is no quote data in this repo.** Not one bid or ask, in any
of the 19 months. §3 is that finding, and it moves `strategy-architecture.md`'s Adverse Selection
Filter from "Day 3" to "the only thing in either document that costs money."

**The merged four are in §6.** Two come from each document, and the fourth slot stays contested.

**§7 is the budget, and it is zero.** Five of the six candidates run on the 46M trades already on
disk; the sixth is settled on a free spot feed instead of a paid GC one — **route 2, Varad's call,
6 Sep.** Nothing in the recommended order at §9 is bought. The `mbp-1` question is deferred, not
answered: GC quote data gets priced only if the free test comes back positive.

---

## 2. What both documents concluded independently — treat as settled

| Conclusion | `four-l1-strategies.md` | `strategy-architecture.md` |
| :--- | :--- | :--- |
| Source doc's Strategies 2 and 3 need volume; spot gold has none | §2.2 | §1 |
| Pattern recognition is underpowered on ~2,500 H4 bars | §2.5 | §1 |
| Source doc's claims have no nulls, so they cannot be wrong | §2.1 | §1 |
| Portable L1 surface is **price, spread, quote rate, time** | §3 | §2, §4 |
| Buckets must be normalised to **basis points**, not GC ticks | §3.2 | §3, §4 |
| Quote rate must be **z-scored per instrument**, never a raw threshold | §3.1 | §2 |
| Predict **magnitude distributions**, not direction | §4 | §1 |
| `instruments.py` with a `has_flow` boundary; `features/portable.py` | §6.2 | §4, §10 |
| Kill conditions pre-committed, lifts quoted against MDE at 80% power | §5 | §6, §7 |
| Calibration is the product | §4 | §9 |

Two independent passes over the same constraint landing on the same architecture, including the same
two module names, is the strongest evidence available here that the architecture is forced by the
problem rather than chosen. **§2 is closed.** The remaining argument is only about the four slots.

---

## 3. The finding that sets the budget: this repo holds no quote data

Checked directly, because `strategy-architecture.md`'s S1 rests entirely on `spread_z` and
`quote_rate_z` and neither document verified the inputs exist.

```
data/2026-07/gc_trades.parquet
  cols: timestamp, price, size, aggressor_side, symbol, instrument_id
  rows: 1,616,772

find data -name "*.dbn.zst"  ->  19 trades  ·  19 definition
```

**Every one of the 19 months is the `trades` schema. There is no `tbbo`, no `mbp-1`, no `bbo`.** The
one TBBO pull that ever ran — `pull_tbbo_validate.py`, the 2026-07-16 quote-rule check that produced
the 99.65% agreement — **did not leave its raw cache on disk.** All that survives is
`analysis/gc_footprint_quoterule_2026-07-15.csv`, which is aggregated to price levels and carries
`price, buy_vol, sell_vol, delta, total_vol`. No bid. No ask.

### 3.1 And the two features have different data requirements

This is the part that matters for budgeting, and it is easy to miss because both features get called
"L1":

| Feature | Minimum schema | Why |
| :--- | :--- | :--- |
| **Spread** at trade times | `tbbo` | One record per trade, carrying the BBO immediately before it. Comparable row count to `trades` |
| **Spread** sampled | `bbo-1s` | A 1-second sample. Cheaper, but it is a sample of the level |
| **Quote rate** | `mbp-1` | It is a *count of book updates*. TBBO only observes the book at trade times, so **quote rate is not computable from TBBO at all** |

**`mbp-1` is every top-of-book change, not one row per trade.** On an instrument as active as GC that
is a different order of magnitude from the ~46M trade rows already held, and nobody has run
`pull_futures_trades.py`'s cost-estimate flow against it. **That estimate is one command and it should
be run before any of this is scheduled.**

### 3.2 What this does to each strategy

**Two different questions get conflated here, so they are split: does the data exist, and does it
cost anything.** Only one candidate needs a purchase.

| Strategy | Source | Data on disk? | Cost to run |
| :--- | :--- | :--- | :--- |
| Geometry frontier | `four-l1-strategies` S1 | ✅ OHLC | **$0** |
| Compression / vol momentum | both S2 | ✅ OHLC | **$0** |
| Clock, session, events | `four-l1` S4 / `arch` S3 | ✅ clock + public calendar | **$0** |
| Anchor-distance reversion | `four-l1` S3 | ✅ OHLC + session anchors | **$0** |
| **Path-Dependent Dynamic Exit** | `arch` S4 | ✅ **yes** — `timestamp, price, size` at ~1.6M rows/month is enough to order MFE against retracement | **$0**, but the replay is unbuilt (§5.6) |
| **Adverse Selection Filter** | `arch` S1 | ❌ needs `mbp-1` (quote rate) + `tbbo` (spread) | **The only one that costs money** — and §7 routes around it |

**Five of the six run for nothing on data already paid for.** The correction is on the
Path-Dependent Exit: it is *not* blocked on a purchase, only on tooling that does not exist yet, and
that tooling is buildable from the trades already on disk. `strategy-architecture.md`'s Phase 1
schedules the one genuinely blocked candidate — the Adverse Selection Filter — on Day 3.

---

## 4. What `strategy-architecture.md` adds that `four-l1-strategies.md` does not

Credit where it is due — four things in it are genuinely better, and three of them should be adopted.

**4.1 The session taxonomy is better and should be taken wholesale.** Six phases with explicit ET
boundaries — Asia, Asia-London, London, London-NY, NY, NY-Asia — against `four-l1-strategies.md`'s
vaguer "minute buckets". The handoff phases are the insight: the 02:00–03:00 and 08:00–09:30 windows
are where liquidity regime actually changes, and a fixed 15-minute binning would smear exactly those
boundaries. **Adopt the taxonomy; measure the rates rather than asserting them (§5.2).**

**4.2 The event table is concrete and correct in shape.** NFP/CPI at 08:25–08:40, FOMC at
14:00–14:30, London Fix at 10:00–10:30, NY open. `four-l1-strategies.md` said "an event calendar"
and left it at that. This is the calendar. The `%` vol-shift column is invented (§5.2) but the
windows are right and they are the hard part.

**4.3 The edge-case tables are a real contribution.** Crossed markets, feed outage, spread blowout,
DST transitions, early closes, holiday-thinned sessions, gap-through-stop. `four-l1-strategies.md`
has none of this and it is the sort of thing that is only ever written after something breaks.
`validate_l1_data`'s four assertions belong in the codebase regardless of which strategies survive.

**4.4 "Focus on avoiding negative EV rather than finding alpha" is the better framing, and I was
half-hearted about it.** `four-l1-strategies.md` argued for non-directional strategies from the
evidence but still framed them as edge-seeking. Given a null that is **−1.73 to −6.42 ticks per leg
before costs** in every ATR bucket, the first-order win is not entering the bad ones. That reframing
is right and should lead the merged document.

---

## 5. Defects in `strategy-architecture.md`, ranked

Stated bluntly because it is a v1.0 draft asking for approval to start Phase 1 on Monday.

### 5.1 `liquidity_score` is mathematically broken

```python
liquidity_score = (1 / spread_z) * max(0, quote_rate_z)
```

`spread_z` is a z-score. **It crosses zero.** `1/spread_z` has a pole there and flips sign either
side of it, so `liquidity_score` is discontinuous and sign-inverting in the exact middle of the
variable's normal range. The entry rule then ANDs `spread_z > 0.3` with `liquidity_score > 0.8` —
and since `1/0.3 = 3.33` while `1/1.5 = 0.67`, the composite threshold is already implied by the
spread band in a way the table does not state and probably did not intend.

Whatever this was meant to express, it is not what it computes. It needs rewriting from the
hypothesis, not patching.

### 5.2 Invented constants are presented as pre-committed thresholds

```python
SESSION_MULTIPLIER = {'Asia': 0.85, 'London-NY': 1.15, 'NY-Asia': 0.80, ...}
vol_multiplier = 1.0 + (rv_slope / rv_5m) * 0.3     # "Pre-committed"
NFP: +400%   CPI: +350%   FOMC: +300%   London Fix: +50%
```

**Pre-committing a number you made up is not the same as pre-committing a threshold.**
Pre-commitment protects against choosing a value *after seeing the answer*. It does not make a
fabricated constant true, and a made-up 1.15 that is never revisited is worse than a tuned one,
because a tuned one at least touched the data.

This is the same defect both documents convicted `xauusd-regimes.md` of — "65%+ success rates",
"60–70% accuracy" — arriving in a different costume. And this repo's standard is stricter than
"pre-committed": `strategies.py` and `regime_filter.py` carry **no defaults at all**, so a threshold
must be transcribed from where a human committed it or the module raises. `families.py` states the
rule outright: *"No number in this file was authored here."*

**The fix is a change of type, not of value.** The session effect is a **measured table** with an N
per cell — that is `four-l1-strategies.md`'s S4 — not a multiplier applied to a base rate. Turning a
measurement into an assumption is the one move that loses information for free.

Related: `get_session_adjusted_rate` returns `base_rate * MULTIPLIER` capped at 0.95. Probabilities
do not compose multiplicatively like that, and a 0.95 cap is inert on base rates near 0.20.

### 5.3 §9's expected outcomes are the exact claim `FAMILIES.md` already falsified

> Expected `p_target`: 0.22–0.25 (10–25% lift)

`FAMILIES.md` measured this class of claim yesterday, on 393 and 545 legs, against a mix- and
side-matched null, and got **−0.0058 and −0.0003** — at a power where **a 30% relative lift would
have been detected.** The prior on a 10–25% lift from conditioning is therefore low and *measured*,
not merely unproven.

And the range straddles nothing useful: `BASE_RATES.md`'s 50+ bucket breakeven is **0.2237** against a
realised 0.1990. "0.22–0.25" is a band whose bottom half still loses money, which the document's own
EV line concedes (−0.5 to +0.5, "after costs: −0.5 to 0").

**Publishing a numeric expected outcome before the measurement is the failure mode both documents
identified in the source.** Delete §9's numbers; keep its last paragraph, which is honest and good.

### 5.4 The risk-management section crosses a line the pipeline design froze

§6 specifies max daily loss, max concurrent positions, volatility-adjusted sizing, and **Kelly
fraction capped at 2.5%.** From `2026-09-05-live-signal-pipeline-design.md` §2.3 and §6.3:

> **Position sizing is the user's, never ours.** The output carries a probability and a distribution;
> it does not carry a lot size, and **no field in §6's contract may become one.**

That rule is not stylistic. It is the SEBI Research Analyst question `plans/current.md` records as
open pending Shreyas's CA call, and a Kelly fraction attached to a paid signal is further past the
line than a pip count is. If sizing belongs anywhere it is in a **personal** trading tool that is not
the product — the same split the 25 Aug selector spec drew — and it needs saying explicitly in the
document rather than arriving inside an architecture diagram.

### 5.5 Internal inconsistencies

- **"Composite Score = S1 * S2 * S3 * S4 (multiplicative)"** — the four outputs are a boolean, a
  bracket tuple, a time adjustment and a set of exit rules. They are not multiplicable, and the
  pseudocode directly beneath it multiplies nothing. One of the two is wrong.
- **"Full depth (L2)" appears under GC in the ingestion diagram** of a document titled *L1-Only*.
- **"Cross-instrument: GC edge → spot edge, correlation > 0.7"** — an edge is a scalar per arm. Two
  scalars have no correlation. The intended test is presumably rank agreement across buckets, and it
  needs specifying before it can pass or fail.
- **S2's `STABLE / 30–40bp` row prescribes the (70, 20, 30m) bracket as "base case"** — the geometry
  that `BASE_RATES.md` measured as **−4.25 ticks** in that bucket. It is the null, not a base case,
  and the other five rows in that table — (100,25,45m), (120,30,60m), (90,25,40m) — are invented
  geometries where `four-l1-strategies.md`'s S1 exists to *measure* the surface. See §6.

### 5.6 S4 (path-dependent exits) is a good idea blocked on data resolution, not on a purchase

The hypothesis is right and neither of my four had it: fixed brackets are certainly suboptimal, and
`backtest.evaluate` already records MFE and MAE per leg, so the raw material exists.

**But the rules cannot be evaluated on 5-minute bars.** "Move stop to BE+0.5 ATR once MFE > 1.5 ATR"
and "exit if retracement > 0.8 × MFE" both depend on the **intrabar order** of the favourable
excursion and the retracement — and an OHLC bar does not record which came first. `backtest.py`
resolves same-bar ties to the stop precisely because that ordering is unknowable, which is why every
`p_target` in `BASE_RATES.md` is a stated lower bound.

`regime_filter.py` already named this gap:

> at ATR 40 a 20-tick stop is roughly *half a typical bar*, so more volatility makes the stop **more**
> prone to intrabar noise […] that fragility is real and is exactly what D4 must measure at tick
> resolution.

**That tick-resolution replay does not exist.** The trades are on disk, so it is buildable without
buying anything — but it is a real piece of work and it is the actual prerequisite for S4, not
"Day 4."

### 5.7 The roadmap is unscheduled work with a production date on it

Fourteen days, ending "Day 14: Documentation + deployment — production-ready system", with **Day 12
being "Spot XAUUSD feed integration"** when C1 reopened yesterday, AllTick closed yesterday, and no
spot vendor exists. It also declares production-readiness for a system whose four kill conditions may
all fire.

`2026-09-05-live-signal-pipeline-design.md` §8 handled this correctly and the same move applies here:

> **This design is not scheduled.** It takes no week from `plans/team/`, and saying so here is
> deliberate — so an unscheduled model does not quietly eat Week 6.

---

## 6. The merged four

Two from each document. The overlap is larger than it looks — `arch` S2 and `four-l1` S2 are nearly
the same strategy, as are `arch` S3 and `four-l1` S4 — so merging costs less than the two documents
suggest.

### M1 · Bracket-geometry frontier
**From `four-l1-strategies.md` S1. Non-directional. Runs today.**

Sweep `(target, stop, horizon)` over the 19-month archive per `(ATR bucket in bp × session phase ×
side)`, entering on every bar. Report the whole surface with per-cell N and breakeven.

**This must run first, and `strategy-architecture.md` is the argument for why.** Its S2 hardcodes six
brackets — (100,25,45m), (120,30,60m), (90,25,40m) and three more — and calls (70,20,30m) the "base
case". Those are guesses at points on a surface **nobody has measured**, and (70,20,30m) is not a
base case, it is a null that loses in all four buckets. Run M1 and S2's bracket table stops being
invented and starts being read off a measurement. Skip M1 and every lift either document ever quotes
is quoted against an arbitrary geometry that happens to lose.

It selects no entries, so like `BASE_RATES.md` it costs no out-of-sample data, and it cannot fail —
it returns a shape either way.

### M2 · Volatility momentum and compression
**Merge of `four-l1` S2 and `arch` S2. Non-directional. Runs today.**

Take **`arch`'s feature** — signed `rv_slope` from Parkinson realized vol, giving
EXPANDING/CONTRACTING/STABLE — over `four-l1`'s percentile-based compression state. It is strictly
better: a signed slope distinguishes vol rising from vol falling, where a low percentile alone
conflates "quiet and staying quiet" with "quiet and about to break".

Take **`four-l1`'s measurement discipline**: the output is `P(|move| ≥ T within H)` against the
ATR-matched null, feeding `PipForecast.bucket` as a second conditioning dimension. Drop
`vol_multiplier = 1.0 + (rv_slope/rv_5m) * 0.3` entirely — §5.2. The adjustment is measured per
cell or it is not made.

**Highest prior of the four.** Vol clustering is the one effect here that is well-established outside
this repo, and it is not in tension with `horizon.py`: a random walk in *direction* can have entirely
predictable *scale*, and only the first has been tested.

### M3 · Session phase and event conditioning
**Merge of `four-l1` S4 and `arch` S3. Non-directional. Runs today, needs no market data.**

Take **`arch`'s six-phase taxonomy and its event table** — §4.1, §4.2. Take **`four-l1`'s test**:
report `p_target`/`p_stop`/EV per `(ATR bucket × phase)` cell over 19 months, then split
2025-01–09 against 2025-10–2026-07 and check the profile survives the volatility regime change, the
way the 50+ ATR bucket held **0.2000 → 0.1989** while the headline moved 2.2×.

**Drop `SESSION_MULTIPLIER` (§5.2).** The multipliers are the hypothesis, not the result. The result
is a table with an N in every cell.

Cheapest of the four by a distance — a clock, a calendar, and one extra groupby.

### M4 · Contested — see §7

Three candidates, none of which can be run this week without something first:

| Candidate | From | Blocked on | Cost |
| :--- | :--- | :--- | :--- |
| **Path-Dependent Dynamic Exit** | `arch` S4 | Tick-resolution replay, unbuilt (§5.6). Data is on disk | **$0**, real work |
| **Anchor-distance reversion** | `four-l1` S3 | Nothing. Runs today, but is the lowest-prior of the six and sample-limited by construction | **$0** |
| **Adverse Selection Filter** | `arch` S1 | On GC: `mbp-1` + `tbbo`, unpriced (§3). §5.1's formula needs rewriting either way | Paid on GC, **$0 on spot** — §7 |

---

## 7. The whole programme runs for nothing — decided 2026-09-06

**Varad's call, 6 Sep: take the free route on every candidate, including the fourth slot.** This
section replaces the earlier version, which proposed buying one session of GC `tbbo` to settle the
spread question. That purchase is no longer the plan and the reason is not the price — it is §7.3.

### 7.1 Five of six cost nothing, and the sixth has a free instrument

Restating §3.2 as a budget. **M1, M2, M3, anchor reversion and the Path-Dependent Exit all run on
the 46M trades already on disk, for $0.** The only paid item in either document was quote data for
the Adverse Selection Filter, and only on GC.

**The Path-Dependent Exit is the correction worth reading twice.** §5.6 called it blocked, and it is
— but on *tooling*, not on a purchase. Trade-by-trade replay needs `timestamp, price, size`, which
is exactly what every month on disk carries. It resolves the one thing an OHLC bar cannot record —
whether the favourable excursion or the retracement came first — and that unblocks not only `arch`'s
S4 but the intrabar-stop fragility `regime_filter.py` flagged and nobody has measured. **It is the
largest single piece of work in the merged set and it costs nothing but time.** Budget it as work,
not as a day.

### 7.2 M3's calendar is public

NFP and CPI release schedules are published by the BLS, FOMC dates by the Federal Reserve. The event
overlay needs no vendor and no subscription — which is the second reason M3 is the cheapest of the
four and should run early.

### 7.3 Route 2: test the spread hypothesis on spot, where quotes are free

The spread question is *does top-of-book spread carry enough structure to filter on.* Three ways to
answer it without buying GC quote data:

| Route | Method | Verdict |
| :--- | :--- | :--- |
| 1 | **Roll (1984)** — back out effective spread from the serial covariance of trade-price changes, `2·√(−cov(Δp_t, Δp_{t−1}))`, on trades already held | Free, but **undefined whenever that covariance is positive**, which is common in trending intraday tape. Expect gaps. Corwin–Schultz (2012) has the same problem in a different place: it is a daily high/low estimator and gets noisy intraday |
| **2** | **Get spot XAUUSD bid/ask, where quotes are the whole feed** | **CHOSEN** |
| 3 | **Trade intensity** — trades per minute, on disk now, as a stand-in for quote rate | Free, and honest, but it is not the same object as a book-update count. Keep as a fallback feature, not as the test |

**Why route 2 is the right one and not merely the cheap one.** The problem inverts across the two
instruments. On GC, quotes cost money *and* the variable is probably degenerate — GC is among the
most liquid futures in the world and sits at exactly one tick ($0.10) the overwhelming majority of
the time, which would make `spread_z` a z-score of a near-constant, its rolling σ tiny and its tails
unstable by construction. **`spread_z_max = 1.5` would then be a threshold on noise.** On spot,
quotes *are* the entire feed — free, and spread is a live, moving variable rather than a constant.

So route 2 tests the hypothesis on the instrument where it has a chance, using the feed that gives
it away, and **spending money to test a hypothesis that may be structurally void on GC was the wrong
order.** That is the actual argument; the $0 is a side effect.

### 7.4 What route 2 requires, and what is unverified about it

Two free sources of spot XAUUSD L1, in the order I would try them:

- **Dukascopy historical tick data** — publishes XAUUSD ticks with **bid and ask** going back years,
  free. This is the one that makes the *historical* test possible rather than only a live one.
  ⚠️ **Not verified from this machine.** `DELTA_CVD_FINDINGS.md` §4 once recorded A2 as *"blocked on
  Dukascopy being unreachable"* — later rewritten because that was the wrong reason for A2, but the
  reachability problem itself was never retested. **Step one of route 2 is confirming a download
  actually completes**, before anything is built on it.
- **An MT5 demo account** — free, streams live L1 and stores exportable tick history. The product
  already assumes the trader is on MT5, so this doubles as the platform check that has been sitting
  open since Day 2.

**The caveat that survives either source, and it is not small.** Spot XAUUSD spread is a **broker
pricing decision, not a market outcome** — a dealer widens on its own risk policy and its own client
flow, so two brokers disagree about the same instant. That makes the spot result a legitimate test of
*whether spread structure predicts anything*, and **not** a number that transfers to GC or to another
broker. Read it as a yes/no on the hypothesis, never as a calibrated threshold to carry across.

**What this does to the `mbp-1` question:** it defers it, it does not close it. If route 2 says
spread structure is real and useful, that is the moment to price GC quote data — with an answer in
hand about whether it is worth anything. `pull_tbbo_validate.py --estimate-only` and
`pull_futures_trades.py`'s cost-estimate flow both return a number **without spending anything**, so
the estimate itself stays free and can be run any time out of curiosity.

---

## 8. Adopt regardless of which four win

- **`validate_l1_data`'s assertions** (`arch` §6) — crossed market, insane spread, stale timestamp.
  Cheap, and they catch the class of vendor bug `pull_tbbo_validate.py` was written to catch. They
  matter more under route 2, not less: a broker feed is exactly where a crossed or stale quote shows
  up.
- **The edge-case tables** (§4.3) — DST, early close, holiday-thinned sessions, gap-through-stop.
  `four-l1-strategies.md` has nothing equivalent.
- **"Avoid negative EV" as the framing** (§4.4).
- **`arch`'s `StrategyReport` dataclass** — it already carries `lift`, `mde`, `p_target_null` and
  `kill_triggered` as first-class fields, which is the reporting shape `families.py` builds by hand
  each time.

---

## 9. Recommended order — all free

**M1 → M3 → M2 → tick replay + Path-Dependent Exit → route 2 spot spread → M4 decided.**

| | Step | Data | Cost |
| :--- | :--- | :--- | :--- |
| 1 | **M1** geometry frontier | on disk | $0 |
| 2 | **M3** session + event conditioning | on disk + public calendar | $0 |
| 3 | **M2** vol momentum and compression | on disk | $0 |
| 4 | **Tick replay**, then the Path-Dependent Exit on top of it | on disk | $0, largest work item |
| 5 | **Route 2** — confirm a spot bid/ask download completes, then test spread structure | free vendor | $0 |
| 6 | **M4 decided** on 4 and 5's results | — | — |

**Nothing in this list is bought.** Steps 1–3 need no new data, no feed and no vendor decision at
all; step 4 needs none either, only the replay. If M1 returns no positive-EV cell and M2 and M3 both
land inside their own MDE, **that is three kill conditions firing for free**, and it is worth knowing
before the spot-vendor question is reopened or `mbp-1` is priced.

The ordering also front-loads the cheap negatives. Steps 1–3 are days; step 4 is the one that could
run long, and putting it fourth means three kill conditions have already had their chance to fire
before anyone commits to building a replay engine.

---

## 10. Open decisions — Varad's

1. **Does M1's geometry grid get committed before the sweep, and by whom.** Unchanged from
   `four-l1-strategies.md` §10.1, and now more load-bearing: M2's brackets are read off M1's surface.
2. **Does a Dukascopy XAUUSD download actually complete from this machine** (§7.4). It was recorded
   unreachable once and never retested. This is step one of route 2 and it is a ten-minute check.
3. **Where sizing lives** (§5.4) — out of the product, in a personal tool, or deferred to the CA call.
   It is currently specified inside a product architecture, which is the one place the pipeline
   design says it may not be.
4. **Whether `strategy-architecture.md`'s 14-day roadmap is withdrawn or scheduled.** Right now it is
   neither, and `plans/team/` does not contain it.
5. **How much time the tick replay gets before it is called too expensive.** It is free in money and
   it is the largest work item here; a budget set now is worth more than one set halfway through.

**Closed 6 Sep:** the `mbp-1` purchase question, deferred rather than answered — route 2 tests the
hypothesis for nothing first, and GC quote data gets priced only if that comes back positive.
