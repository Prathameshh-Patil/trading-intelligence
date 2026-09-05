# Four L1-only strategies for gold — analysis, selection, architecture

**Date:** 2026-09-05 · **Author:** Claude, at Varad's request · **Status:** analysis and proposal. Nothing here is built.
**Input:** [`xauusd-regimes.md`](xauusd-regimes.md) · **Constraint:** must run on **spot XAUUSD and GC futures**, from **L1 data only**.

---

## 0. The verdict, before the reasoning

**I do not recommend the four strategies in `xauusd-regimes.md` as written.** Three of the four
cannot be computed on spot gold at all, and the one that can is the one this repo has already
measured and found to be a random walk.

But the document is not wrong so much as *unfalsifiable*, and that is fixable. Underneath its four
regimes there are three real hypotheses and one free lunch, and all four survive the L1 constraint
if they are re-specified. My proposal is a different four:

| # | Strategy | Hypothesis | Directional? | Portable? |
| :--- | :--- | :--- | :--- | :--- |
| **S1** | **Bracket geometry frontier** | Some `(target, stop, horizon)` triple is positive-EV per volatility state — or none is | No | Yes |
| **S2** | **Compression → expansion** | Volatility clusters, so a compressed state raises `P(\|move\| ≥ T)` above its own ATR-matched base rate | No | Yes |
| **S3** | **Anchor-distance reversion** | Distance from a session liquidity anchor, in ATR units, predicts reversion at 5–30m | **Yes** | Yes |
| **S4** | **Clock and event conditioning** | `p_target` / `p_stop` are conditioned by minute-of-day and event proximity, stably across 19 months | No | Yes, for free |

**Only one of the four is directional, and that is deliberate.** Section 2 explains why betting
three or four slots on direction would be spending them on the one thing this repo has already
failed to find twice, on two instruments, at adequate power.

---

## 1. What is already proven here, and therefore binding

Any strategy proposal that ignores these is not a proposal, it is a wish. All five are measurements
in this repo, with committed code and recorded N.

### 1.1 Gold is a random walk at 5, 15 and 30 minutes

[`horizon.py`](../../services/signal-data/horizon.py), GC July 2026, 6,276 bars: dispersion grows as
`sqrt(h)` to within **0.1%**, and the overlap correlation between adjacent bars' legs lands at 0.659
and 0.831 against a random walk's predicted 0.667 and 0.833. Two independent statistics, not fitted
to each other. The AllTick spot-gold path reproduced it to **0.4%** on a different instrument through
different code.

**Consequence:** no *unconditional* trend or reversion exists at the product's horizons. Any
directional strategy must be conditional, and must name its condition before it is measured.

### 1.2 The 70/20/30m bracket is negative-EV in every volatility bucket

[`BASE_RATES.md`](../../services/signal-data/analysis/BASE_RATES.md), 19 months, **107,359 legs**:

| ATR bucket | n | `p_target` | breakeven | EV |
| :--- | ---: | ---: | ---: | ---: |
| <30 | 38,573 | 0.0563 | 0.1480 | −6.42 ticks |
| 30–40 | 18,509 | 0.1370 | 0.1977 | −4.25 |
| 40–50 | 14,854 | 0.1688 | 0.2112 | −2.97 |
| 50+ | 35,423 | 0.1990 | 0.2237 | −1.73 |

The gap narrows monotonically with volatility — −0.092, −0.061, −0.042, −0.025 — **and never
closes.** Cost is another 1.4 ticks ($14) on top.

**Consequence:** a strategy is not competing against zero. It is competing against a hole between
1.7 and 6.4 ticks deep, before costs. That is the bar.

### 1.3 Four order-flow conditions carried no edge, at power

[`FAMILIES.md`](../../services/signal-data/analysis/FAMILIES.md): the exhaustion arm landed at
**−0.0058** on 393 legs, the continuation arm at **−0.0003** on 545 — dead on its own matched null to
four decimals. And this was a *powered* null: `mde_rate` says a lift of about **+0.05, a 30% relative
improvement, would have been detected at 80% power.**

That is the difference between "we could not tell" and "we looked, and there is nothing there."

**Consequence:** delta, CVD, absorption and range-expansion, at those thresholds, on that month, do
not beat their base rate. This matters enormously for the current question, because those are exactly
the features **spot gold does not have anyway.** The thing we would lose by going cross-instrument
has already been measured as worth approximately nothing.

### 1.4 Volatility *state* is the only thing found so far that reliably orders outcomes

`BASE_RATES.md` §3 is the most useful result in the repo and it is easy to under-read. The headline
monthly `p_target` swings **5.6×** (0.0345 → 0.1916). Almost all of that is **mix**, not rate: across
a regime change that moved the headline by 2.2×, the 50+ ATR bucket held **0.2000 → 0.1989** — stable
to one part in two hundred.

**Consequence:** conditioning on volatility state is real, stationary and portable. It is the only
conditioning variable with 19 months of evidence behind it. Three of my four strategies are built on
it, and that is not a coincidence — it is the only ground that has held.

### 1.5 A base rate has to be mix- *and* side-matched or it flatters everything

`FAMILIES.md` §3: the filtered arms' nulls rise from 0.164 to 0.189–0.193 **purely because the ATR
gate pushes them into higher buckets.** An arm scored against a pooled rate would have banked that as
edge. And gold trended over the archive, so shorts beat longs in every bucket — a two-sided arm
scored against a long-only null is credited with the drift.

**Consequence:** every number in §5 below must be reported against a `(side, ATR-bucket)`-weighted
null, computed by reweighting the archive onto the arm's own distribution. This is the single
easiest way to fake a result, and it is not optional.

---

## 2. Reading `xauusd-regimes.md` against that evidence

The document is a competent summary of retail technical-analysis orthodoxy. Taken as a map of what
people believe about gold, it is useful. Taken as a specification, it has four structural problems.

### 2.1 It has no nulls, so none of its claims can be wrong

"Breakouts following volatility compression have 65%+ success rates." Success at what target, over
what horizon, against what base rate, on what sample? A 65% hit rate on a 1:3 reward-to-risk bracket
loses money. A 20% hit rate on a 70/20 bracket makes money. **A hit rate without its bracket geometry
and its null is not a number, it is a mood.** Same for "60–70% when confirmed" on reversal patterns
and "accuracy" throughout §3.

This is not pedantry. §1.2 above is a hit rate of 0.199 that is *losing 1.73 ticks a leg*, and §1.3
is a lift of −0.0003 that would have looked like a plausible strategy in any write-up that omitted
its null.

### 2.2 Three of the four strategies cannot be computed on spot gold

This is the hard blocker on the actual request, and it comes straight out of the repo's own founding
fact:

> `delta` and `cvd` are the numbers a screenshot can never contain — they need the aggressor side of
> every individual trade. — `apps/desktop/src/lib/engine/types.ts`

Spot XAUUSD has **no centralised tape.** There is no consolidated volume, no aggregate size, no
aggressor. MT5's `real_volume` for spot gold is empty — that finding is what cut A2 on 25 Aug. A
retail spot feed gives you **quotes, and possibly not even trades.**

| Doc strategy | Needs | On spot XAUUSD |
| :--- | :--- | :--- |
| S1 Trend following | EMA, ADX, MACD | ✅ price only — computable |
| S2 VWAP mean reversion | **VWAP** | ❌ needs volume |
| S3 Breakout momentum | **volume > 150% average** | ❌ needs volume |
| S4 Range compression | BB width, ATR | ✅ price only — computable |

So as written, the strategy set is **half unportable**, and its two portable members are the two that
§1.1 measured as a random walk.

### 2.3 It cites monthly-horizon research to justify minute-horizon rules

Strategy 1's justification is Moskowitz, Ooi & Pedersen (2012). That paper's result is **time-series
momentum at 1–12 month holding periods**, cross-sectional across 58 instruments. It says nothing
whatsoever about a 50-EMA cross on 5-minute gold bars, and `horizon.py` has directly measured that
the intraday version does not hold here.

This is a category error, and it is worth naming because it is the most seductive one in the
document: a real, replicated, well-powered academic finding is being borrowed to lend weight to a
rule that operates three orders of magnitude away from where the finding was made. **TSMOM in gold is
probably real. It is a daily-bar, multi-day-hold product, and it is a different product than a live
overlay signal.**

### 2.4 §4's denoising section contains a lookahead trap

MODWT wavelet denoising, as described — "decompose the series, zero the high-frequency components,
reconstruct" — is **acausal**. The reconstruction at time *t* depends on samples after *t*. Applied
to a full price history and then backtested, it produces spectacular and entirely fictitious results,
because the "denoised" price at every bar already knows where price went next. This is one of the
most common ways a backtest is destroyed, and it destroys it silently — the equity curve just looks
good.

If wavelets are used at all they must be in a strictly streaming, boundary-truncated form, and the
first thing to check is whether the streaming version still helps. Usually it does not.

Kalman filtering (§4B) is fine — it is causal by construction. But a Kalman filter on a univariate
price is an exponential moving average with an adaptive gain. It smooths; it adds no information the
price did not already carry. It is not a source of edge, and should not be listed as one.

### 2.5 The pattern-recognition section cannot be measured on the data that exists

§3 asks for H4/Daily head-and-shoulders, triangles and flags. The archive is 419 sessions — roughly
**2,500 H4 bars.** A pattern that fires 30 or 40 times in that span, against `horizon.py`'s MDE math,
cannot separate a real effect from nothing. It is not that patterns are fake; it is that **we have no
mechanism to find out**, and building a scanner whose output can never be adjudicated is the most
expensive kind of nothing.

Cut it. Revisit if a daily-bar, multi-decade gold series is ever pulled — that is where the sample
size lives.

### 2.6 What §5 gets right, and how to use it

The macro drivers table is directionally correct and I would keep it — but not as a signal. Real
yields, DXY and Fed expectations move at daily frequency; the product answers at 5–30 minutes. They
do not move intrabar and cannot time an entry.

Their real uses are two, and both are worth having:
- **A slow regime conditioner.** Whether the 10Y real yield is rising or falling over 20 days is a
  legitimate covariate to bucket by, alongside ATR.
- **An event blackout calendar.** FOMC, CPI, NFP at 08:30 / 14:00 ET. This is S4 below, and it is the
  cheapest real thing in the whole document.

---

## 3. What "L1 only, both instruments" actually leaves you

This is the constraint that determines the architecture, so it is worth being exact rather than
approximate about it.

**L1 on GC (Databento MBP-1 / TBBO):** top-of-book bid/ask price and size, plus every trade with
price, size and an aggressor field. Rich.

**L1 on spot XAUUSD (a retail broker or aggregator):** bid/ask, a timestamp, and — depending entirely
on the vendor — possibly a size that is synthetic, and possibly no trade prints at all.

**The intersection is the strategy surface. It is smaller than it looks.**

| Feature | GC | Spot XAUUSD | Portable? |
| :--- | :---: | :---: | :---: |
| Mid, OHLC bars from mid | ✅ | ✅ | **✅** |
| Spread | ✅ | ✅ | **✅** |
| ATR, realized vol, range, efficiency ratio | ✅ | ✅ | **✅** |
| Session anchors (open, prior close, session H/L, opening range) | ✅ | ✅ | **✅** |
| Clock, session phase, event proximity | ✅ | ✅ | **✅** |
| **Quote update rate** | ✅ | ✅ | **✅ — with a caveat, §3.1** |
| Microprice (size-weighted mid) | ✅ | ⚠️ sizes may be synthetic | ⚠️ |
| Traded volume | ✅ | ❌ | ❌ |
| Delta, CVD, absorption, footprint | ✅ | ❌ | ❌ |
| Depth beyond top of book | L2 | ❌ | ❌ |

**The portable feature set is: price, spread, quote rate, and time.** That is the whole of it. Any
strategy that must run on both is built from those four things or it is not portable.

### 3.1 Quote rate is the volume proxy, and it is vendor-relative

Quote update count per interval is the only activity measure available on both instruments, and it is
genuinely informative — quote intensity spikes on news and on liquidity withdrawal. But it is **not
comparable in absolute terms across vendors.** The AllTick evaluation measured spot gold at 1 Hz with
roughly 2% tick delivery; Databento delivers every book update. A "quote rate of 40" means nothing
shared between them.

**Therefore quote rate enters every strategy as a z-score against its own trailing distribution,
within instrument and within vendor, and never as a raw threshold.** If we change spot vendors, the
z-score survives and a raw threshold silently changes meaning. This is the same trap as `p_stop`
looking flat in July: a number that is really a property of the sample, mistaken for a property of
the market.

### 3.2 Volatility buckets must be defined in basis points, not ticks

Every bucket in the repo today is in **GC ticks** (`atr_min = 40`), and `TICK = 0.10` is hardcoded in
`s1.py`. An MT5 broker may define a XAUUSD pip as 0.01 or 0.10 — a 10× spread in what "40" means. A
40-tick bucket is a $4.00 move on GC and could be a $0.40 move on spot.

**Buckets must be normalised: ATR as a fraction of price, in basis points.** At gold near $2,400, a
40-tick (=$4.00) ATR is ~16.7 bp. That number means the same thing on both instruments and on both
sides of a roll. This is not cosmetic — it is what makes a base rate table computed on GC legitimately
readable as a prior for spot.

The pipeline design's §6.4 already flagged the display-side version of this trap. This is the same
trap on the input side, and it is the more dangerous of the two because it never renders wrong on
screen.

### 3.3 The current regime labelling does not port, at all

Worth stating loudly. [`regimes.py`](../../services/signal-data/regimes.py) clusters on four features:
`realized_vol`, `cvd_slope`, `cvd_persistence`, `price_efficiency`. **Two of the four are order flow.**
The three committed regimes are separated primarily by `cvd_slope` (+27.6 / −26.7 / −0.2) and
`cvd_persistence` (0.61 / 0.61 / 0.21) — that is, *by exactly the features spot gold does not have.*

So the regime label is not a shared object between the two instruments and cannot be made one by
relabelling. A portable regime must be refit on the portable set — realized vol, price efficiency,
spread, quote-rate z — and it will be a **different and probably weaker labelling.** That refit is
work, it is honest work, and it must not be skipped by assuming the GC labels transfer.

### 3.4 Cost is higher on spot, and L1 lets you measure it instead of assuming it

`horizon.py` uses a 1.4-tick round-trip cost floor ($14/contract) for GC. Spot XAUUSD from a retail
broker is typically 15–30 cents of spread — **1.5 to 3.0 GC-tick-equivalents, and it widens on
exactly the news events S4 cares about.**

A GC strategy therefore has to clear a *higher* bar to port, not a lower one. The upside: spread is
an L1 observable on both feeds. **`cost_ticks` should stop being a scalar constant and become a
per-bar series read from the quote.** That is a small change with a real payoff — it makes the
"does this survive costs" question answerable at the moment of the signal rather than on average, and
it will disqualify news-window trades on their own merits rather than by a blanket rule.

---

## 4. Why only one of my four is directional

Because the evidence says so, and I would rather say it plainly than distribute the disappointment
across four hopeful strategies.

- §1.1: no unconditional direction at 5/15/30m, measured twice, on two instruments.
- §1.3: four order-flow conditions produced +0.000 and −0.006 lift at power sufficient to see +0.05.
- §1.4: the one thing that *did* replicate over 19 months is that outcome distributions are ordered
  by volatility state, and that ordering is stable to 1 part in 200 across a regime change.

And critically — **the product contract does not require direction to be worth money.** The pipeline
design's `PipForecast` is a *conditional distribution*: `mfe` quantiles, `mae` quantiles, and a
`reach` table of `P(target before stop)` per candidate bracket. A trader can size on a better-
conditioned reach table with `side` chosen by their own thesis. §7 of that design already names the
thing being sold: *when the model says 61%, does it happen 61% of the time.* **Calibration is the
product. Direction is one possible input to it.**

Three non-directional strategies that sharpen the distribution are worth more here than three
directional ones that repeat an experiment already run.

---

## 5. The four strategies

Every one is specified from the §3 portable set, measured through `backtest.evaluate` against a mix-
and side-matched null, reported with `horizon.mde_rate` beside it, and carries a kill condition
written before the measurement. **No threshold below has a default value** — same rule as
`strategies.py` and `regime_filter.py`, for the same reason: a number chosen while looking at the
answer is a fit, not a filter.

---

### S1 · Bracket geometry frontier

**The question nobody has asked yet, and it is cheap.**

`base_rates.py` measured one triple: 70 ticks target, 20 stop, 30-minute horizon. It loses in all four
buckets. **But that is one point on a surface, and the surface has never been swept.** It is entirely
possible — and it is a claim about gold's return distribution, not about any signal — that some other
geometry is positive-EV unconditionally, or positive within a volatility bucket.

**Spec.** For each `(ATR bucket in bp) × (session phase) × (side)` cell, and for a grid of
`target ∈ T`, `stop ∈ S`, `horizon ∈ H`, compute `P(target first)` and EV over the whole 19-month
archive, entering on every bar. Report the EV surface with per-cell N and per-cell breakeven.

**Why it is not a fit.** Nothing selects entries. It is the population, the same class of statistic as
`horizon.py`'s sigma — which is why `BASE_RATES.md` could legitimately run over all 19 months without
spending out-of-sample data. Sweeping the geometry of the *measurement instrument* does not fit the
data any more than choosing a bucket width does. The one discipline required: the chosen grid must be
committed before the sweep, and the surface reported whole, not just its maximum.

**Why it is first.** Every other strategy's result is quoted as a lift over a null, and right now the
null is a single arbitrary geometry that happens to lose. If a positive-EV geometry exists, **every
lift measured against 70/20/30m has been measured against the wrong thing.** If none exists — the
likely outcome, given §1.1 — then it is proven that all EV must come from conditioning, and S2–S4
inherit a hard, honest bar.

**Portability.** Perfect. Needs only OHLC and a tick size. Re-run per instrument once spot bars exist;
the bp normalisation of §3.2 is what lets the two surfaces be compared.

**Kill condition.** None — this cannot fail, it can only return a shape. It is a measurement, not a
bet. That is precisely why it goes first.

---

### S2 · Compression → expansion

**Merges the document's Strategies 3 and 4, and changes what is being predicted.**

The doc treats compression as a *directional* setup ("direction typically follows the prevailing
higher-timeframe trend"). That is the weak version and §1.1 has already made it unlikely. **The strong
version predicts magnitude, not direction** — and magnitude is what the product actually sells.

**Hypothesis.** Volatility clusters. A bar in a compressed state has a *higher* `P(|move| ≥ T)` over
the next H than the ATR-matched base rate implies, because trailing ATR under-states forward vol
precisely at the moment vol is about to mean-revert upward.

This is the most robustly replicated empirical fact in financial time series — it is what GARCH is —
and it is **not in tension with §1.1.** A random walk in *direction* can have entirely predictable
*scale*. Those are separate claims and only the first has been tested here.

**Spec.** Portable compression state from price alone:
- `bb_width = 2σ(close, W) / mid`, in bp, and its percentile against a trailing distribution;
- `atr_slope`: ATR over the short window relative to ATR over the long, both in bp;
- `range_ratio`: current bar range against trailing median range;
- optionally `quote_rate_z` (§3.1) as a corroborating, never a required, condition.

Fire on: compression percentile below a committed threshold, sustained for a committed number of bars.
**No direction. No entry side.** The output is `P(|move| ≥ T within H)`, compared against the archive
rate for the same ATR bucket.

**What a positive result buys.** Not a trade — a *better bucket*. If the compression state lifts
`P(|move| ≥ 70)` by 5 points over the ATR-matched rate, that flows straight into `PipForecast.bucket`
as a second conditioning dimension alongside ATR, and every `reach` number computed inside it gets
sharper. That is a product improvement with **zero directional claim attached**, which also means zero
new regulatory surface under §2.3 of the pipeline design.

**Portability.** Perfect. Price only, in bp.

**Kill condition.** Committed before running: if the compression state's lift over its ATR-matched
null is below `mde_rate(null, n)` — i.e. below what its own sample could have detected — it is
reported and dropped. Not tuned. Dropped.

**My confidence.** Highest of the four. It is the only one where the underlying effect is
well-established outside this repo, the measurement is cheap, and a positive result is directly
consumable by a contract that already exists.

---

### S3 · Anchor-distance reversion

**The document's Strategy 2, with the unportable part removed and the mechanism named.**

VWAP needs volume, so it is out on spot. But VWAP was never the point — it is a proxy for *a price
level that participants treat as fair*, and there are portable proxies for that:

- session open;
- prior session close / settlement;
- session high/low and the opening-range boundaries;
- a time-weighted average of mid over the session (**TWAP** — the volume-free sibling of VWAP, and
  causal by construction the same way `orderflow.vwap` is);
- the levels the trader drew, arriving from `CaptureContext.levels` in the OCR stage.

**Hypothesis.** Displacement from a session anchor, measured **in ATR units** so it is comparable
across instruments and volatility regimes, predicts partial reversion at 5–30 minutes. The mechanism
is real and specific: liquidity providers accumulate directional inventory as price runs away from
the level they quoted around, and they price to attract the offsetting flow. It is the one hypothesis
in the source document with a microstructure story rather than a chart story.

**The honest caveat, stated up front.** §1.1 found no *unconditional* reversion — the overlap
correlations match a random walk almost exactly. That does **not** close this door, because a
conditional effect at the extreme tail of the displacement distribution is entirely invisible to an
unconditional autocorrelation. But it does mean the prior should be low, and that the effect, if it
exists, lives in the far tail where N is smallest and MDE is worst. **Expect to be sample-limited.**

**Spec.** `displacement = (mid − anchor) / ATR`, per anchor. Fire when `|displacement|` exceeds a
committed threshold, side against the displacement. Measure `p_target` against a null matched on
**side and ATR bucket and anchor type** — the last one matters, because displacement from the session
open is mechanically larger late in the session, so an unmatched null would credit the strategy with
time-of-day.

Adding, as free corroborating conditions from L1: spread widening at the extreme (liquidity
withdrawal argues *against* reversion, not for it), and a quote-rate spike.

**Portability.** Good, with care. Anchors must be defined per-instrument: GC has a settlement and a
Globex 18:00–17:00 ET session; spot has neither a settlement nor a clean daily boundary. `instruments.py`
below is where those definitions live, and they are not interchangeable.

**Kill condition.** If, at every displacement threshold on the committed grid, the lift is inside the
MDE for that threshold's own N, S3 is reported as unmeasurable-at-this-sample and dropped. It is not
retried at a finer grid — that is how a threshold gets chosen while looking at the answer.

**My confidence.** Moderate. It is the only directional strategy I would spend a slot on, and I would
spend exactly one.

---

### S4 · Clock and event conditioning

**Not a strategy in the source document — it is one line inside Strategy 3 — and it is the best
value in the whole set.**

**Hypothesis.** `p_target` and `p_stop` are strongly and *stably* conditioned by minute-of-day and by
proximity to scheduled releases. Gold's intraday volatility is structured to an unusual degree: the
London AM and PM fixes, the 08:30 ET data window, the 09:30 equity open, the 13:30 COMEX pit close,
the Asian lull. This is not a belief about gold, it is a fact about when its participants are awake.

**Why it is nearly free.** It requires **no market data at all** beyond a clock and an economic
calendar. There is nothing to compute, nothing to fit, no feature to get wrong, and it ports to spot
gold *exactly* — the London fix is at the same instant on both instruments, because it is the same
gold.

**Spec.** Extend `base_rates.py` with two conditioning dimensions: `minute_bucket` (15- or 30-minute
bins of the session) and `event_proximity` (minutes to/from the nearest high-impact release).
Report `p_target`, `p_stop` and EV per `(ATR bucket × minute bucket)` cell over all 19 months.

**The test that makes it worth anything.** Stability. Run the same split `BASE_RATES.md` §3 ran —
2025-01–09 against 2025-10–2026-07 — and check whether the *shape* of the clock profile holds across
the volatility regime change, the way the 50+ ATR bucket held at 0.2000 → 0.1989. **A clock effect
that is stable across that break is a genuine structural feature of the instrument. One that is not
is a description of 2025.** That distinction is the entire test and it costs one extra groupby.

**What it buys.** Another conditioning dimension on the reach table, plus an event blackout that is
justified by measurement rather than by folklore. `regime_filter.session_interior` already implements
the crudest version of this — drop the first and last N minutes — and it was added on intuition. This
replaces the intuition with a profile.

**Kill condition.** If the clock profile does not survive the 2025/2026 split, it is a curiosity, not
a feature. Report and drop.

**My confidence.** High that a large effect exists. Genuinely uncertain whether it is *tradeable* as
opposed to merely *descriptive* — much of it will be volatility, and volatility is already in the
ATR bucket. The interaction is the interesting part: whether 08:30 ET at ATR 40 differs from 03:00 ET
at ATR 40. If the answer is no, S4 collapses into S1 and that is a clean, cheap negative result.

---

## 6. Architecture

The repo already has almost all of the machinery. What it does not have is an **instrument
abstraction**, and it has one hardcoded constant standing where that abstraction belongs. The
temptation here is a framework; the correct move is roughly 80 lines and two file moves.

### 6.1 The one real coupling to break

```
s1.py:22   TICK = 0.10          # GC minimum price increment
s1.py:23   TICK_VALUE = 10.0    # USD per tick per contract
```

Imported by `backtest.py`, `strategies.py`, `horizon.py`, `features/expansion.py`,
`features/orderflow.py` and two test modules. **Every tick-denominated number in the repo flows
through those two lines**, which means today the entire measurement stack silently assumes GC.

### 6.2 What to add

```
instruments.py              # NEW, ~40 lines. The only new abstraction.
features/portable.py        # NEW. The §3 intersection: spread, quote_rate_z, anchors, bp helpers.
features/orderflow.py       # EXISTING — docstring amended: VENUE-SPECIFIC, GC only.
features/expansion.py       # EXISTING — atr() gains a bp-denominated sibling.
strategies.py               # EXISTING — S2/S3/S4 conditions land here as functions.
reach.py                    # NEW. S1: generalises base_rates.py from one (T,S,H) to a grid.
```

`instruments.py`, in full shape:

```python
@dataclass(frozen=True)
class Instrument:
    name: str                 # 'GC' | 'XAUUSD'
    tick: float               # 0.10 | broker-dependent
    tick_value: float | None  # USD per tick per contract; None for spot (size is the user's)
    session: SessionCalendar  # Globex 18:00-17:00 ET | 24x5 with a named daily boundary
    anchors: tuple[str, ...]  # which S3 anchors are defined for this instrument
    has_flow: bool            # may features/orderflow.py be read at all
```

`has_flow` is the load-bearing field and it should read as a hard boundary, not a hint. **A strategy
that touches `features/orderflow` on an instrument where `has_flow` is False should raise, not degrade.**
This is the same discipline the pipeline design applied to OCR-derived numbers — *forbidden, not as a
fallback when the feed is down, not as a cross-check, not behind a flag* — and for the identical
reason: a silent degradation produces a number that looks like the real one.

### 6.3 The layering

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  L1 feed                                                            │
  │  GC: Databento MBP-1/TBBO   ·   XAUUSD: broker quotes (TBD)         │
  └─────────────────────────────────────────────────────────────────────┘
                │                                    │
                ▼                                    ▼
  ┌─────────────────────────────┐   ┌─────────────────────────────────────┐
  │ features/portable.py        │   │ features/orderflow.py   VENUE-ONLY  │
  │ mid · spread · quote_rate_z │   │ delta · cvd · absorption · vwap     │
  │ atr_bp · range · efficiency │   │ gated on Instrument.has_flow        │
  │ anchors · clock · events    │   │                                     │
  └─────────────────────────────┘   └─────────────────────────────────────┘
                │                                    │
                │  ◀── STRATEGIES S1-S4 READ         │  ◀── VETO LAYER ONLY
                │      ONLY FROM THIS SIDE           │      may suppress a signal,
                ▼                                    ▼      may never create or flip one
  ┌─────────────────────────────────────────────────────────────────────┐
  │  strategies.py  ·  S1 geometry · S2 compression · S3 anchor · S4 clock│
  └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  backtest.evaluate  →  legs (move, MFE, MAE, first_touch)  UNCHANGED │
  └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  reach.py  ·  EV surface + mix/side/clock-matched null + mde_rate    │
  └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  calibration.py  ·  reliability diagram, live  UNCHANGED             │
  └─────────────────────────────────────────────────────────────────────┘
```

**The one rule that makes this architecture worth having:** order flow is a **veto layer**. It may
suppress a signal on GC; it may never create one and it may never flip a side. If flow could create
signals, then GC and XAUUSD would be running different strategies wearing the same name, every
cross-instrument comparison would be meaningless, and the first time spot underperformed nobody could
say whether it was the instrument or the missing feature. Keeping flow purely subtractive means the
*signal set* is identical on both instruments and only the *filtering* differs — which is a
difference you can actually measure.

It also means §1.3's result — that flow carried no edge — costs us very little to respect.

### 6.4 What does not change

`backtest.py`, `horizon.py` and `calibration.py` are already instrument-agnostic once `TICK` is
injected rather than imported. Their contracts hold: clock-based horizons, session-bounded legs,
same-bar ties resolving to the stop, MFE/MAE signed in the trade's own favour, N reported beside every
number. **That machinery is the most valuable thing in this repo and none of this proposal touches
it.**

---

## 7. Order of work

| | Step | Why here | Cost |
| :--- | :--- | :--- | :--- |
| 1 | `instruments.py` + inject `TICK`; bp-denominated ATR | Nothing else is portable until this lands, and it is small | Half a day |
| 2 | **S1 · geometry sweep** on the existing 19 months | Sets the null everything else is quoted against. Uses data already on disk. Cannot fail | 1 day |
| 3 | **S4 · clock conditioning** + the 2025/2026 stability split | No new data, no new features, and it either lands or dies in one run | 1 day |
| 4 | **S2 · compression** against S1's corrected null | The highest-prior hypothesis, measured properly for the first time | 2 days |
| 5 | Spot XAUUSD feed decision + a portable regime refit (§3.3) | Blocks everything cross-instrument; do not let it block 2–4 | — |
| 6 | **S3 · anchor reversion** | Lowest prior, most sample-hungry, and it wants the portable regime from 5 | 2 days |

**Steps 2–4 need no new data, no vendor decision and no feed.** That is the point of ordering them
first: three of the four strategies can be adjudicated on the 46 million trades already sitting in
`data/`, before a single dollar is spent on a spot feed. If S1, S2 and S4 all come back flat, that is
worth knowing *before* the spot-vendor question is answered, not after.

**On the held-out half.** Steps 2 and 3 are population statistics — nothing selects, tunes or fits —
so by `BASE_RATES.md`'s own reasoning they cost no out-of-sample data. Steps 4 and 6 do select, and
run on the training half only. The held-out half is spent once, at the end, on whichever arms are
still alive. It is the one asset that cannot be bought back.

---

## 8. My opinion, stated plainly

**On the source document.** It is a good map of consensus and a poor specification. Its real defect
is not that any individual claim is wrong — several are probably right — but that not one of them is
stated in a form that could come back false. Every number in it (65%, 60–70%, −0.8) arrives without a
sample, a horizon or a null. This repo's whole culture is the opposite of that, and the gap is the
work.

**On the four-strategy framing.** Four regimes each with its own strategy is an appealing structure
and I think it is the wrong one here. It assumes the hard part is *choosing among* edges, when this
repo's measurements say the hard part is *finding one*. Three of my four are non-directional because
the evidence points at the distribution, not the direction — and the product contract was already
written to sell a distribution.

**On the L1-only constraint.** I think it is a better constraint than it looks. It costs you delta,
CVD and footprint — and §1.3 measured those, at power, as worth about −0.006. It buys you an
instrument-portable strategy set, a much cheaper data bill, a feed that a retail broker will actually
give you, and the ability to check every result twice on two different instruments. **The AllTick
spot run reproducing `horizon.py`'s random-walk exponent to 0.4% is exactly that check working**, and
it is the strongest form of validation available here. Do not give it up.

**On what I actually expect to happen.** S1 returns a surface with no positive-EV cell, confirming
that all EV must come from conditioning. S4 finds a large clock effect that turns out to be mostly
volatility already captured by the ATR bucket, with a modest residual around 08:30 ET. S2 finds a
real but small compression effect on magnitude — enough to sharpen the reach table, not enough to be
a trade on its own. S3 is sample-limited and inconclusive. **That combination is not a failure; it is
a well-conditioned reach table, which is what §7 of the pipeline design says the product is.** The
mistake would be to read "no directional edge" as "no product."

**The one thing I would push back on hardest.** If the choice comes down to spending the next two
weeks on a directional model versus spending them on S1 and S4, take S1 and S4. They are cheaper, they
run on data already on disk, they cannot fail to return an answer, and they improve the number the
subscriber can actually verify. A directional model built before the geometry surface is known is a
model being measured against a null we already know is the wrong one.

---

## 9. What I would cut from the source document

| Section | Recommendation | Reason |
| :--- | :--- | :--- |
| §2 S1 trend following, as an intraday rule | **Cut**, keep `trend_aligned` as a filter | §1.1 measured it. Re-propose as a daily-bar product if wanted |
| §2 S2 VWAP reversion | **Re-specify as S3** | VWAP is unportable; the hypothesis survives with a TWAP/session anchor |
| §2 S3 + S4 breakouts | **Merge into S2**, predicting magnitude | Same hypothesis twice; volume condition unportable; direction claim unsupported |
| §3 pattern recognition | **Cut** | ~2,500 H4 bars cannot adjudicate it. Not wrong — unmeasurable |
| §4A wavelet denoising | **Cut** unless strictly streaming | Acausal as described. Silently destroys a backtest |
| §4B Kalman | **Keep, demote** | Causal and fine, but it is an adaptive EMA. Smoothing, not information |
| §4C practical methods | **Keep** ATR filtering and MTF confirmation | Both portable and both already have analogues here |
| §4D preprocessing | **Keep, with one change** | Outlier removal at 5σ must never touch a real gap. `pull_tbbo_validate.py`'s posture: validate, do not clean |
| §5 macro drivers | **Keep as a slow conditioner and a calendar** | Correct, but daily-frequency. Cannot time a 5-minute entry |
| §5 microstructure table | **Keep COT/OI/ETF as weekly context** | Not L1, not intraday, but genuinely informative at the regime level |
| §6 papers | **Keep the triage** | Already handled in `docs/research/2026-08-28-gold-literature-triage.md` |

---

## 10. Open decisions — Varad's, not this file's

1. **Does S1's geometry grid get committed before the sweep, and by whom.** It is the one place in
   this proposal where a number could be chosen while looking at the answer.
2. **The spot XAUUSD vendor.** AllTick was closed out; nothing replaced it. S3 and every
   cross-instrument claim are blocked on this, and steps 2–4 deliberately are not.
3. **Whether the portable regime refit (§3.3) replaces the committed GC labelling or runs beside it.**
   `regimes.py` §6.2's pre-commitment rule says a new run gets a new directory, never an overwrite.
4. **`MIN_SAMPLES` per cell in the S1 surface**, committed before the surface is looked at. The
   existing floor is 30 (`backtest.MIN_SAMPLES`); a 3-dimensional grid will produce many thin cells
   and the honest answer for those is no forecast, not a wide one.
5. **Whether `cost_ticks` becomes a per-bar series** (§3.4). I think it should. It is a small change
   that makes the cost question answerable at signal time.
