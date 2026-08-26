# Data requirements — serving predicted direction and magnitude

**Date:** 2026-08-26 · **Status:** analysis, nothing built · **Asked by:** Prathamesh
**Question:** to serve customers a predicted candle — direction, and *maximum ticks* of travel —
read on screen and later synthesized for prediction, what data does that need, and why each piece?

---

## 0. The measurement that should shape this whole conversation

Before listing data, one number, measured on `data/gc_trades.parquet` (the existing month,
31,260 one-minute bars, session-aware, no lookahead):

| Relationship | Value |
| :--- | ---: |
| `delta[t]` vs `return[t]` — **contemporaneous** | **+0.5076** |
| `delta[t]` vs `return[t+1]` — **predictive** | **−0.0192** |
| `return[t]` vs `return[t+1]` | −0.0362 |
| Hit rate, `sign(delta[t])` → `sign(return[t+1])` | **48.48%**, N = 28,812 |

**`DELTA_CVD_FINDINGS.md` §1(c) reports the +0.50 and it is correct — but it is
contemporaneous, and contemporaneous is very nearly tautological.** Aggressive buying is
*what moves price inside that bar*. Measuring that the two agree is a validation that the
delta sign convention is right — which is exactly what §1 used it for, correctly — and it is
**not** evidence of predictive power. It is the single easiest number in this repo to
misread, and misreading it would put a product on air.

The predictive figure is ~0, and the hit rate is *below* 50% by roughly 5 standard errors
(SE ≈ 0.30% at this N), which is consistent with short-horizon mean reversion and bid-ask
bounce, not momentum.

**What this implies for the data question, and it is the whole answer in one line:
trade-flow data alone is exhausted at the 1-minute horizon. This is not a modelling
problem that a better model fixes. It is a data problem.** Everything below is ordered by
that.

---

## 1. Pin the target before buying anything

The data you need is a function of the target, and "maximum ticks of direction" is not yet a
defined target.

### 1.1 "Maximum ticks" is MFE, and MFE is not achievable

Measured on the same month:

| 1-minute bar | median | p75 | p90 | p99 |
| :--- | ---: | ---: | ---: | ---: |
| **Range** (high−low), ticks | 15 | 23 | 33 | 70 |
| **Travel** (\|close−open\|), ticks | 7 | 13 | 22 | 49 |

More than half of a typical bar's range is retraced inside the bar. **Maximum favourable
excursion is the best it ever looked, and capturing it requires exiting at exactly the right
instant.** A customer shown "expected +8 ticks" who holds to the close gets a materially
different outcome, and the gap is not a rounding error — it is roughly half the range.

`backtest.py` already computes MFE **and** MAE for this reason, and the selector design §4
states the rule directly: *"The honest form of the answer is 'median +X ticks, IQR [a, b],
N=n' — never 'it predicts X ticks.'"* A screen showing one number contradicts the project's
own standard. **If a single figure must be shown, it should be a quantile of the realized
move with its interval, not MFE.**

### 1.2 Which price series is the target

This decides a data purchase, so it is not cosmetic.

- **Last trade** — what you have. Alternates between bid and ask, inducing negative serial
  correlation (Roll's bid-ask bounce). At GC's 0.10 tick, that is ±1 tick of pure noise
  injected into a target measured in single-digit ticks. The −0.0362 return autocorrelation
  above is partly this artefact, not a market property.
- **Midprice** — removes the bounce. **Requires continuous L1 quotes, which you do not have**
  (one session of TBBO exists, pulled only to validate the aggressor mapping).
- **Microprice** — mid weighted by book imbalance (Stoikov). A better short-horizon estimator
  of future mid than mid itself. **Requires L2.**

**Predicting ticks off last-trade prices means a measurable fraction of the target is
microstructure noise.** That is a correctness issue, not a refinement.

### 1.3 What is a "candle"

Time bars oversample quiet periods and undersample active ones — a 1-minute bar at 03:00 ET
and one at 08:30 ET are not comparable observations, yet a model treats them as equal rows.
**Volume bars or dollar bars** (a bar closes after N contracts rather than 60 seconds)
produce returns closer to IID and far less heteroskedastic. For a *magnitude* model this
matters more than for a direction model, because "ticks per bar" is only a meaningful unit
if bars carry comparable information. Cheap to test against the existing month; requires
nothing new.

---

## 2. What exists today, and the ceiling it imposes

**S1 (`contracts.md`):** `timestamp`, `price`, `size`, `aggressor_side`, `symbol`,
`instrument_id` — 1,616,772 GC trades, 23 sessions, July 2026, plus one session of TBBO.

That supports what has already been built: delta, CVD, footprint, the four Stage 1
candidates, session-level regime features. It **cannot** support magnitude prediction, for
one structural reason:

> **Trades tell you what was consumed. They never tell you what was resting.** The same
> 500-contract buy that lifts one tick through a stacked book moves fifteen ticks through a
> thin one. Trade data cannot distinguish those two cases *even in principle* — the
> information is in the book, which was never recorded.

This is not hypothetical for this project. `DELTA_CVD_FINDINGS.md` §2 documents the
2026-07-16 session closing CVD **+1,842 while price fell 89 points**, with the 08:00 ET hour
at delta **+1,083 against a 47.7-point drop**. The findings correctly identify this as
absorption. **Absorption is a statement about resting liquidity, and the data cannot see
it** — the conclusion was reached by elimination and reasoning, not measurement. A model
asked to predict magnitude on that session has the same blindness, with nobody reasoning on
its behalf.

---

## 3. Tier 1 — what the target directly demands

### 3.1 Full order book: L2 (top-10) and ideally L3 / order-by-order

**The single highest-value addition, and the one that addresses the §0 finding directly.**

| What it enables | Why it matters here |
| :--- | :--- |
| **Book imbalance** (bid depth vs ask depth, multiple levels) | Among the most consistently documented short-horizon directional predictors in the microstructure literature — and it is *state*, computable without lookahead, so it fits `regimes.py`'s §2 rule as-is |
| **Order Flow Imbalance (OFI)** — net queue changes at the touch (Cont–Kukanov–Stoikov) | Explains substantially more short-horizon price variation than trade imbalance. Critically, its **price-impact coefficient scales inversely with depth** — which is *literally the ticks-per-unit-flow question* the product is asking |
| **Price impact / Kyle's λ** | The magnitude coefficient itself: how many ticks per contract of imbalance, conditioned on current depth. There is no way to estimate this without the book |
| **Cancellation and replenishment** (L3 only) | Liquidity withdrawal ahead of a move is invisible in trades — no trade occurs. A book that thins without printing is the clearest available warning of a large move |
| **Exact aggressor** (L3) | §5 of the selector design already notes this: order-by-order determines the aggressor exactly, which is *strictly stronger* than the quote rule that closed the Week 3 gate. It would also **eliminate the ~15–20% magnitude residual**, which is currently inherited by every threshold in the project |

That last row deserves emphasis. The ~15–20% method-dependence in session-total delta
(side field +1,842 vs quote rule +2,216) is currently carried as an irreducible error bar
through every downstream number. **It is not irreducible — it is an artefact of inferring
the aggressor. L3 measures it.** The error bar disappears rather than being carried.

**Practical form:** L2 as incremental book updates with sequence numbers plus periodic
snapshots (Databento's MBP-10 / MBO schemas are the relevant shape). Sequence numbers are
not optional — a gap in an incremental feed silently corrupts every reconstructed book state
after it, and the corruption looks like ordinary data.

### 3.2 Continuous L1 quotes (BBO)

Needed even if L2 is bought, and needed regardless of everything else in this document:

- **Midprice / microprice targets** (§1.2) — the target variable itself.
- **Spread** as a state feature and as a regime input. Spread widening is a volatility
  regime signal available before the volatility arrives.
- **The realistic cost floor.** A 1-tick spread on GC is $10 per contract round turn against
  a *median 7-tick* directional move. **Any edge below roughly 1–2 ticks is not an edge, it
  is a rebate to the exchange.** Without continuous quotes there is no way to know what
  fraction of any backtested result survives the spread — and the current backtest assumes
  a fill at the bar close with no spread cost at all, which is optimistic by construction.

### 3.3 Far more history

The selector design §6 already states this — *"The cheapest fix is more data, not more
modelling"* — and it is more acute for a served product than for the research tool.

The arithmetic: 23 sessions, walk-forward split ≈ 11 / 11. Partitioned into 3 regimes ×
4 strategies, the average cell holds a handful of signals against a §6.5 floor of 30.
**The design's own predicted outcome is "inconclusive," recorded in advance.** A customer
product cannot ship on inconclusive.

For a model with parameters — not four hand-written rules — the requirement is higher again.
Serving direction and magnitude across regimes plausibly needs **12–24 months minimum**, and
it must include regime variety: a trending month, a chopping month, a crisis, a Fed cycle
turn. A model fit on one calm July has learned July.

### 3.4 Book state reconstruction integrity

Snapshots + increments + sequence numbers + gap detection. Also required: the exchange's own
**status feed** — halts, pauses, and the daily maintenance window. A reconstruction that
does not know the market was halted will read the resumption as a violent move that a model
happily learns to predict.

---

## 4. Tier 2 — the exogenous drivers, which is where GC's magnitude actually comes from

Gold's large moves are frequently **not endogenous to GC's own order flow.** They are dollar
and real-rate repricings that arrive through the book rather than originating in it. A model
that sees only GC's book will be structurally blind to the moves that matter most — and
those are precisely the high-magnitude moves the product is meant to size.

### 4.1 Cross-asset, synchronized to the same clock

| Series | Why |
| :--- | :--- |
| **US real yields (10y TIPS), 2y/10y nominals, ZN/ZB futures** | The dominant macro driver of gold. Gold is a zero-coupon asset; real yields are its opportunity cost, and the relationship is strongly negative |
| **DXY / EUR-USD** | Gold is dollar-denominated. A large share of "gold moved" is "the dollar moved" |
| **ES / NQ** | Risk-on/risk-off; gold's safe-haven bid is conditional on equity stress |
| **SI (silver), HG (copper), PL** | The metals complex moves together; silver is gold's high-beta cousin and often leads on momentum |
| **CL (crude)** | Inflation expectations channel |
| **VIX / equity vol** | Volatility regime — directly informative about expected magnitude |

**The mechanism to keep in mind:** the same order-flow signature produces a 3-tick move on a
quiet macro day and a 30-tick move while the dollar is repricing. Cross-asset state is what
separates those two cases, and it is entirely absent from the current data.

### 4.2 Event calendar — the cheapest high-value dataset in this document

FOMC decisions, minutes and dot plots; CPI, PPI, PCE, NFP; Fed speakers; ECB and BoJ
decisions; LBMA fixes (10:30 / 15:00 London); options expiry; futures roll and first notice
day; physical-demand holidays in China and India.

Two distinct reasons, and the second is the one people miss:

1. **Serving.** A magnitude estimate 200 milliseconds before CPI is meaningless. The
   decision filter (§3 of the selector design) needs this to implement rules the trader
   already has in mind — the spec's own example is *"never during NFP."*
2. **Training contamination.** Without event labels, the model learns event-window
   volatility as if it were ordinary volatility, and that distortion contaminates **every**
   prediction, including the quiet ones. Event days must be identifiable so they can be
   modelled separately, weighted, or excluded — a decision you cannot make if you cannot see
   them.

### 4.3 Options-implied volatility on GC

IV, term structure, and skew. **IV is the market's own forward-looking estimate of magnitude
— which is the exact quantity being predicted.** It is close to a free prior: any model
whose magnitude forecast systematically disagrees with the options market is making a strong
claim that should be examined rather than shipped. Skew adds directional asymmetry of
expectations, which is otherwise very hard to observe.

### 4.4 Open interest, roll schedule, and volume by contract

The existing month contains the GCQ6 → GCZ6 roll on 29 July. The S1 fixture deliberately
avoids it; **a production system cannot.** Rolls create artificial gaps that a naive
continuous series turns into fake moves, and OI tells you when the roll is happening in
practice rather than on the calendar. Continuous-contract splicing method (ratio-adjusted,
difference-adjusted, or none) is a decision that changes every historical magnitude number,
and it should be made explicitly and recorded.

---

## 5. Tier 3 — what serving live adds that backtesting never reveals

- **Exchange timestamp vs receipt timestamp, and the latency between them.** Training on
  exchange time and serving on receipt time is a train/serve skew that is fatal at
  one-minute horizons and completely invisible in backtest. §5's checklist already asks
  quantfeed this — it matters more for a served product than for research.
- **Feed gaps and recovery behaviour in real time.** Backtests silently skip gaps; a live
  system must decide whether to predict through one or go quiet. Predicting through a gap is
  how a confident wrong number reaches a screen.
- **Halts, limits, and the settlement window.** `verify_settlement_close.py` already
  established that settlement ≠ last trade (a 12.2-point difference). A served product must
  agree with whatever number the customer sees on their own platform, or it will be judged
  wrong even when it is right.

---

## 6. Labels — a data requirement in disguise

- **MFE/MAE need the full intra-horizon path**, not bar closes. That means tick (or book)
  data through the entire label horizon, at the resolution the label claims.
- **Overlapping labels break independence.** A 30-minute forward label computed on
  1-minute bars means adjacent samples share 29 of 30 minutes. Standard significance tests
  assume independent samples and will report confidence that is not there — this is one of
  the most common ways a backtest lies to the person who wrote it, and it is directly
  relevant to §6's null tests.
- **Path-dependent labelling** (triple-barrier: profit target, stop, time limit) matches how
  a trade actually terminates far better than a fixed-horizon close, and needs the same
  path data.

---

## 7. What data cannot buy — read this before committing spend

**None of the above makes 1-minute direction reliably predictable.** The §0 measurement is a
floor observation, not a ceiling one, but the honest framing is:

- Short-horizon directional prediction is close to the noise floor. Well-resourced firms with
  full book data and colocation operate at modest edges over 50%, and they monetize them
  through volume and cost structure that a retail-facing product does not have.
- **Magnitude is more predictable than direction.** Volatility clusters and is strongly
  autocorrelated; direction is close to a martingale. **The most defensible product here is
  a magnitude/volatility estimate — "the next 15 minutes look like a 20-tick range, not a
  7-tick range" — which is genuinely forecastable and does not require calling direction at
  all.**
- The ~15–20% magnitude residual is carried by every threshold today. L3 removes it; nothing
  else does.
- **A point estimate on a screen is the wrong product regardless of data.** The distribution
  *is* the deliverable — §4 already says so, and shipping a single number would contradict
  the standard the project holds its own research to.

**This also bears on §1's regulatory line.** "Unusual flow at this level, N=847 similar
prior instances, median subsequent range 22 ticks, IQR [11, 38]" is *information*.
"Next candle: +8 ticks, long" is a *recommendation*. The first is both more honest given the
§0 measurement and materially further from the SEBI Research Analyst question that Shreyas's
CA call exists to answer. **The data supports the first far better than the second.**

---

## 8. Priority, and what to ask on today's quantfeed call

Ordered by measured value per unit of effort, not by cost:

1. **L2 book, full history, GC on COMEX specifically.** Addresses §0 directly. Nothing else
   on this list changes the picture as much.
2. **Continuous L1/BBO for the same span.** Required for an honest target and for knowing
   what survives the spread.
3. **12–24 months of history**, spanning varied regimes. Cheap relative to its effect.
4. **Event calendar.** Nearly free, and prevents a contamination that silently affects every
   prediction.
5. **Cross-asset: real yields, DXY, ES, SI** at matched resolution and clock.
6. **L3 / order-by-order.** Best data, heaviest lift — and it retires the ~15–20% residual
   rather than carrying it.
7. **GC options IV surface.** A forward prior on the exact quantity being predicted.
8. **Open interest and roll metadata.** Required for correctness, not for edge.

**Add to §5's existing checklist for the call:** L2/L3 depth and *how many levels*; whether
book data is incremental-with-sequence-numbers or snapshot-only; **history depth for the
book specifically, not just for trades** (these are commonly very different products); and
whether a status/halt feed is included.

---

## 9. Not verified

- §0 and §1.1's figures were computed for this document against
  `data/gc_trades.parquet` — 31,260 one-minute bars, session-aware, `groupby(session)`
  before shifting so no forward return crosses the overnight break. **They are a simple
  linear and sign test with no conditioning, no regime split and no feature engineering.**
  They establish that the naive reading of the +0.50 is wrong and set a realistic baseline.
  **They do not prove no signal exists** — conditioning on regime or book state may well
  find one, which is the argument for §3.1 rather than against it.
- The 48.48% hit rate is significantly below 50% at this N, consistent with mean reversion
  and bid-ask bounce. **Whether a contrarian edge survives the spread is untested and, at a
  1-tick spread against a 7-tick median move, is the first thing to check** before anyone
  gets excited about a below-coin-flip number being "signal with the sign flipped."
- Everything about quantfeed's coverage remains unconfirmed, per §5 of the selector design.
- No claim here is based on running a model. This is a data-requirements analysis, and the
  §6 guardrails — pre-committed thresholds, both nulls, walk-forward, N beside every
  number — apply unchanged to anything built on it.
