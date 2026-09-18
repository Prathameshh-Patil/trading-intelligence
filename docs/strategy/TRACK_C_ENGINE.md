# Track C as an independent mathematical engine — the build plan

**Written 2026-09-18.** Track C (spot XAUUSD magnitude expansion) becomes **its own algorithmic
engine**: a deterministic mathematical pipeline that takes bars in and emits *a suggested trade or
nothing*, with its own filters, its own backtester, its own pass/fail gates and its own CLI —
structurally modelled on `~/Documents/Quant_trading`, and held to this repo's evidence discipline.

> **Status, updated 2026-09-18: built, and on one point superseded.**
> [`TRACK_C_BUILD.md`](TRACK_C_BUILD.md) is the build record and takes precedence where the two
> disagree. **The disagreement is structural and is stated here rather than left to be discovered:
> this document designs ONE strategy — §9's sweep event, §13's score, §8's logistic, §7's HMM. The
> 18 Sep brief replaces that with FOUR structurally independent strategies whose every input is a
> closed-form quantity of OHLC bars, and no fitted model anywhere.**
>
> What that changes below: §2's table rows for §7 (HMM) and §8 (the logistic) are **not in Track C's
> path** — nothing reads `p_expand` or `p_e` — so **§9.1's blocker 2 (E4's verdict) no longer gates
> anything**, and §9.1's blocker 3 (granularity) was decided by the user: 5-minute trades, 1-minute
> audits. §9.1's blocker 4 (AWS credentials) is where the build stops. §4's module layout, §5's four
> refusing layers, §6's fill model and walk-forward, §7's gates and §11's borrowings are all built
> as written.
>
> Precedence is otherwise unchanged: [`plans/current.md`](../../plans/current.md) is live status and
> [`plans/team/`](../../plans/team/README.md) is the plan of record.

---

## 1. The ask, and the one tension worth stating before the plan

**The ask.** Track C stops being a research lane that tabulates and becomes an **engine that
suggests a trade**: purely mathematical, independently buildable, with filters and backtests of its
own, in the shape of the Quant_trading system.

**The tension.** Those two codebases are built on opposite reflexes, and this plan only works if
that is said out loud rather than discovered in month two.

| | `trading-intelligence` today | `Quant_trading` |
| :--- | :--- | :--- |
| What a pipeline ends in | **A table.** `reach.py` is *"a lookup, not a chooser"* | **An order.** 13 strategies, a risk engine with veto, live MT5 |
| What a result is | A number with a null and a power calculation behind it | A gate-passing equity curve |
| Track record here | **Track A flat on its own null. Track B: no cell clears the cost floor** | 13 strategies live, audited, some retired for failing the gate |

Track A and Track B both ran to completion on this archive and **found no edge**. An engine that
suggests trades, built by the same people on the same data, will produce a backtest that looks good
long before it produces one that is true. **So this plan borrows Quant_trading's *structure* and
keeps this repo's *burden of proof*.** Concretely: the engine is built, and it is not believed until
it clears §7's gates on out-of-sample windows with a deflated Sharpe and a pre-committed prediction
standing against it.

That is the whole design argument. Everything below is detail.

---

## 2. What "purely mathematical" means here, precisely

**Every stage is a closed-form quantity or an estimated parameter of a stated model. No discretion,
no pattern recognition, no "price looks like".** The engine's entire input is a 20-column frame of
numbers and its entire output is a number, a side, three prices and a reason string.

| § | Stage | The mathematics | Status today |
| :--- | :--- | :--- | :--- |
| §2 | Volatility forecast | Yang-Zhang σ at n = 12/48/288; GARCH(1,1)-t, m-step cumulative variance; a 50/50 ensemble → `r̂₆₀` | ✅ `features/volatility.py` |
| §6 | Memory | Hurst by DFA and by variance-time, plus their agreement | ✅ `features/hurst.py` |
| §7 | Regime | 3-state HMM {Chop, Build, Expansion} → `P(B_t)`, `P(E_{t+1})` | ⛔ **E4 first** |
| §1/§12 | Clock | Session windows; hard news lockout ±2m, internal ±5m | ✅ `features/structure.py` |
| §9 | Event | Sweep of a prior extreme with reclaim inside 30s, δ = max(2 ticks, 0.05·ATR) | ✅ `structure.sweeps` (ticks) |
| §8 | Probability | Logistic on four features, **isotonic-calibrated**, `p_E ≥ 0.62` | ✅ `classifier.py` |
| §13 | Score | Deterministic weighted sum of six normalised components, `Score ≥ 0.72` | ✅ `fsm.score` |
| §15 | Execution | FSM: limit at `P_s + 0.50W`, 20s expiry, never converted to market | ✅ `fsm.py` |
| §10 | Exit | Structural stop, `$2 ≤ D ≤ $5`; `R = clip(2.5D, $10, $15)`; BE at 1.5D | ◐ partial — §10.1 |
| §11 | Size | `C = ⌊A·r / (D·V + F)⌋`, r = 0.4%; daily caps | ✅ `fsm.size_lots` |

**The one fitted object is the logistic**, which is why it is the one thing that is isotonically
calibrated, scored by Brier, and haircut by `tuning.deflated_sharpe`. Everything else has parameters
that come from the spec, not from the data.

**Deliberately not in this engine:** no RandomForest regime classifier, no RL-lite weight feedback,
no nightly re-weighting. Quant_trading has all three and earns them across 13 strategies; **one
strategy with ~40–100 trades a year cannot support a model that re-weights itself** — it is a
machine for fitting the last six months. Stated here so it is a decision rather than an omission.

### 2.1 A defect this plan is not allowed to inherit — ✅ fixed 2026-09-18

**§10 requires `20 ≤ D ≤ 50` ticks — $2.00 to $5.00 per ounce, and `fsm.exclusions` enforced only the
upper bound.** A $0.50 stop passed, and its target was then `clip(2.5 × 0.50, 10, 15) = $10` — a 20:1
nominal R that came from the target *floor* rather than from anything anyone chose, which is exactly
the confusion §10's own note about *"target distance in ticks"* against *"risk-reward multiple"*
exists to prevent.

**`D_MIN_USD = 2.00` and a `stop_too_tight` exclusion**, four tests, 534 passing. Both bounds are
§10's ticks in USD at GC's $0.10 — the same translation `TARGET_FLOOR_USD` and `TARGET_CAP_USD`
already carry for §10's 100 and 150. XAUUSD's `tick` is Dukascopy's 0.001 price quantum and is
explicitly not a tradeable tick, so it is not where these come from.

---

## 3. Independent — and exactly how independent

**Location: `services/signal-data/track_c/`.** Its own package, own config, own CLI, own reports
directory. Not its own service.

**Why not a separate `services/engine-c/`:** it would have to fork nine feature modules —
`volatility`, `hurst`, `structure`, `portable`, `frame`, `fsm`, `classifier`, `e3_cost`, `tuning` —
all of which exist, are tested, and are the *definitions* of the quantities involved. Discipline rule
10 is *one definition per quantity*; two copies is how two files quietly disagree. The engine is
independent in **control flow and measurement**, not in arithmetic.

| Shared, imported, never re-spelled | Built new inside `track_c/` |
| :--- | :--- |
| `features/*` — every feature definition | The bar-by-bar event loop and day state |
| `fsm.py` — §13 score, §15 FSM, `fsm_row` | The pessimistic fill model |
| `classifier.py` — `p_E` and its calibration | R-based daily metrics and the gate table |
| `e3_cost.py` — cost, EV, target floor/cap | The walk-forward driver and its report |
| `tuning.py` — purged folds, deflated Sharpe | The level universe (Asian range, prior day) |
| `instruments.py`, `calendars.py` | The 16-condition funnel as a counter |

**What it does *not* share with Track B**, and why that is correct rather than duplication:
`backtest.py` is a **vectorised grid sweep** — every bar an entry, first-touch against a
`(target, stop, horizon)` lattice. Track C is **event-driven**: a handful of candidates per week,
each a limit order with a 20-second life, a structural stop, one position at a time and a two-trade
daily cap. Forcing one engine to be both would make `backtest.py` worse at the thing it is already
proven at. **The one quantity that must not fork is the first-touch convention** — `backtest.py`
owns it, and `track_c/engine.py` imports `first_touch_from` rather than writing its own.

---

## 4. Module layout

```
services/signal-data/track_c/
  __init__.py
  config.py        every §-threshold in one typed place, sourced to its §       ~80
  levels.py        the level universe: Asian high/low, prior-day extremes       ~90
  funnel.py        §9's 16 conditions, ordered, cumulative, counted             ~120
  suggest.py       frame row -> Suggestion | None. The engine's one entry point ~90
  fills.py         spread, slippage, queue. Pessimistic by construction         ~110
  engine.py        the event loop: bars -> candidates -> orders -> fills -> day ~200
  metrics.py       R-based: daily win rate, worst day, PF, Sharpe, DSR          ~120
  walkforward.py   24/6/3 roll, final-year holdout, per-window records          ~120
  report.py        one markdown report per run, gate table first                ~100
  cli.py           python -m track_c {funnel,suggest,backtest,walkforward}      ~80
```

**~1,110 lines, ten files, none over 200.** Style rule: files under ~300, functions under ~40.

Plus `track_c/tests/` mirroring one-to-one, and `config/track_c.toml` holding the numbers so a
parameter change is a reviewable diff rather than an edit inside a function.

---

## 5. The filters — four layers, and each one refuses differently

Quant_trading stacks a ConfluenceGate on top of raw signals and then gives a 16-step risk engine
absolute veto. Track C's equivalent is four layers, **ordered cheapest-first**, each with its own
refusal vocabulary so a rejection is always attributable.

```
 LAYER 1 · ADMISSIBILITY          track_c/suggest.py, via fsm.fsm_row
   Is this row even a number? Non-finite anything -> raise, not skip.
   Today this refuses EVERY real row: §7's p_expand is NaN until E4.
        │
        ▼
 LAYER 2 · THE FUNNEL             track_c/funnel.py — §9's 16 conditions
   Ordered, cumulative AND. Four print SKIPPED forever (CVD_z, CVD-rising,
   OFI_z, Hawkes — no tape on spot). Stage 13 is unresolved: see §10.2.
   In backtest mode this layer is also the E2 counter; same code, two uses.
        │
        ▼
 LAYER 3 · SCORE + EXCLUSIONS     fsm.score, fsm.exclusions
   Ten hard exclusions that OVERRIDE the score, then Score >= 0.72.
   A refusal here names the condition: forecast_range, hurst, no_sweep,
   stop_too_wide, slippage, news_lockout, p_e, trade_limit, loss_limit,
   position_open.
        │
        ▼
 LAYER 4 · RISK                   track_c/engine.py, day state
   Two trades a day, two losses a day, one position at a time, internal
   daily loss limit min($1100, 0.75 x DLL_firm), 0.75 x DLL risk-consumed
   ceiling. §11. These are REFUSALS, not sizing adjustments.
```

**The layers never negotiate.** Quant_trading's risk engine has veto power and no override path;
this is the same property, and it is why layer 4 cannot reduce size to make a trade fit — it can only
decline. A rule that can be satisfied by shrinking is a rule someone eventually shrinks to zero.

**Every refusal is recorded.** A run emits a refusal histogram, not just a trade list. The single
most useful artefact this engine can produce in its first month is *"of 40,000 bars, 39,997 were
refused, and here is the stage that refused them"* — the same reasoning as E2's attrition table.

---

## 6. The backtest — its own, and strict on purpose

Modelled on `Quant_trading/backtest.md` §3, which is the strongest part of that system.

### 6.1 Fill model

```
fill = signal_price
     + side · spread_at_bar / 2            cross the spread, always
     + side · 1.5 · measured_slippage      1.5x empirical, as a margin of safety
     + queue_penalty                       see below
cost  = spread + slippage + commission, carried in bp AND usd
```

- **Spread** comes from `spot.py`'s own `spread_bp` column — the mid-derived bars carry it per bar,
  which is better than Quant_trading's hour-of-day median and comes free. **Never a broker's
  "typical spread".** Inside a news window, spread × 3.0 even when the trade is not blocked.
- **Slippage**: no live trade journal exists, so the default is explicit and pessimistic and is
  recorded as an assumption in every report header rather than buried in a config.
- **Limit orders** (this engine's only entry) fill **only if the bar's low ≤ limit** for a long, at
  the limit price, **no positive slippage, last in queue**. §9's 20-second expiry means a limit that
  is not filled inside its life is cancelled and **never converted to market**.
- **Stops** fill at the worse of stop + slippage or the bar's extreme. Gappy stops must hurt.

> **The honest limit of this, stated once.** Bars are 5-minute; §9's event is a 30-second sweep and a
> 20-second limit. **A 5-minute bar cannot resolve a 20-second order life.** Two consequences:
> intra-bar fills are an assumption, not a measurement, and the engine's first-pass results are an
> upper bound on what the tick record would give. `replay.py` already answers the general form of
> this question for Track B — bars carry the MFE/MAE order 95.8% of the time — and **Track C needs
> its own version of that measurement before its backtest numbers mean anything.** Recorded as
> §9.2's task, not waved away.

### 6.2 Walk-forward, from `mathematical.md` §14

```
train 24 months ─► validate 6 ─► roll forward 3 ─► repeat across 5 years
final 12 months: untouched holdout, opened ONCE, at the end
no random splits — they leak time-series information
```

`tuning.folds` and `tuning.independent_folds` already implement the purged roll; `walkforward.py` is
the driver, not the mathematics. `tuning.Trials` counts every parameter setting tried across the
whole programme — **the counter is unresettable on purpose** — and `deflated_sharpe` haircuts the
headline against that count. **A Sharpe quoted without its trial count is not a result.**

---

## 7. The gates — Track C's own pass/fail contract

Quant_trading's G1–G8 are a real contract and most of them transfer. **Two do not, and pretending
otherwise would be the most expensive mistake in this document.**

| | Gate | Threshold | Why this number |
| :--- | :--- | :--- | :--- |
| **C1** | **Events at funnel stage 12** | **≥ 100 over the archive** | E2's kill condition. Below it, no parameter setting makes the spec testable |
| **C2** | **Per-trade EV, after costs** | **> 0 at the `e3_cost` floor** | The gate Track B failed. `ev_bp` uses the same cost model or the comparison is meaningless |
| **C3** | **Profit factor, OOS** | **≥ 1.4** | Quant_trading G3, unchanged. Below 1.4 it cannot survive slippage drift |
| **C4** | **Deflated Sharpe** | **> 0 at the programme's trial count** | This repo's addition, and the one Quant_trading lacks. A raw Sharpe on a tuned strategy is a number about the tuning |
| **C5** | **Max drawdown** | **≤ 12% of starting equity** | Quant_trading G5, unchanged |
| **C6** | **Profitable OOS windows** | **≥ 80% (4 of 5)** | Quant_trading G7, unchanged. The single best overfitting detector here |
| **C7** | **Worst day** | **≥ −2R** | Quant_trading G2, and it is already §11's daily loss limit — the gate just measures what the risk layer promises |
| **C8** | **Holdout agreement** | **Final-year metrics inside the OOS windows' range** | Opened once. If it disagrees, the answer is no, and no re-tune follows |

**Deliberately dropped, with reasons:**

- **G1, "≥ 70% of trading days finish ≥ +0R"** — Track C caps at two trades a day and E2's own draft
  predicts 200–500 trades over *five years*. That is roughly **one trade a week**, so most days have
  no trade and "daily win rate" measures the calendar, not the strategy. **C1 and C6 do the work G1
  was doing.**
- **G6, "≥ 60 trades/year"** — at 40–100 trades a year this is exactly the boundary, and it would
  reject the strategy for the thing E2 is *designed to measure*. **C1 replaces it**, at the funnel
  rather than at the trade, which is where the count is actually diagnostic.
- **G8, regime non-loss** — that is an ensemble gate. One strategy, no ensemble.

**The pre-commitment rule applies to this table.** These thresholds are committed **before** the
first backtest runs, in their own commit, timestamped ahead — discipline rule 6. A gate chosen after
seeing the equity curve is not a gate.

---

## 8. What the engine emits

```python
@dataclass(frozen=True, slots=True)
class Suggestion:
    ts: pd.Timestamp
    side: int                  # +1 long, -1 short
    entry: float               # the §9 limit, P_s + 0.50W
    stop: float                # §10 structural, $2 <= D <= $5
    target: float              # §10, clip(2.5D, $10, $15)
    lots: float                # §11, r = 0.4%
    expires_at: pd.Timestamp   # §9, entry + 20s. Never becomes a market order
    p_e: float                 # §8, calibrated
    score: float               # §13
    refusals: tuple[str, ...]  # empty here; populated on the `None` path
```

It is `fsm.TradeCandidate` plus the three things a *suggestion* needs that a candidate does not: a
size, an expiry, and the audit trail. **`None` is the normal return value** and carries its refusals,
which is what makes the histogram in §5 possible.

**The engine suggests. It does not trade.** No broker, no MT5 bridge, no order router — that is
Quant_trading's `src/connectors/` and it is explicitly out of scope until the gates in §7 are
cleared. Suggestions go to a report and, eventually, to the desktop overlay through the existing S7
route. **The step from `Suggestion` to a live order is a gate, not a sprint.**

---

## 9. Build order

Ordered so that **everything not blocked is built first**, and each step is a commit that runs.

| | Step | Depends on | Owner | Note |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `config.py` — every §-threshold in one typed place | nothing | Varad | Mostly a move: numbers currently live in `fsm`, `e3_cost`, `structure` |
| 2 | ~~`D_MIN_USD` — fix §2.1's missing lower bound~~ | — | — | ✅ **done 18 Sep**, four tests |
| 3 | `levels.py` — Asian range and prior-day extremes | nothing | Prathamesh | Pure clock + OHLC; testable on fixtures today |
| 4 | `funnel.py` — 16 conditions as a counter | 3 | Varad | **This IS E2.** Blocked on §15's prediction, not on code |
| 5 | `fills.py` + `metrics.py` | nothing | Varad | Testable on synthetic paths with no market data at all |
| 6 | `engine.py` — the event loop | 1, 3, 5 | Varad | Imports `first_touch_from`; does not re-spell it |
| 7 | `suggest.py` | 1, `fsm_row` ✅ | Varad | Thin: `fsm_row` → `admit` → `size_lots` → `Suggestion` |
| 8 | **Intra-bar resolution measurement** | 6 | Prathamesh | §6.1's honest limit. `replay.py` is the template |
| 9 | `walkforward.py` + `report.py` + `cli.py` | 6 | Varad | |
| 10 | The first full run, against §7's gates | **E1, E2, E3, E4** | both | Not before |

**Steps 1, 3, 5 have no blockers and no prerequisites** — roughly 400 lines that can be written and
tested against fixtures before a single spot bar is pulled. That is the point of the ordering.

### 9.1 The four things that gate step 10

1. **E1, E2, E3, E4 predictions** — all four now Varad's, all four unwritten. §9's funnel is E2, so
   step 4 literally cannot run first.
2. **E4's verdict on the HMM.** `p_expand` is NaN on every row today, `fsm_row` refuses every row,
   and `s_hmm` carries 0.20 of the score. If E4 says a 3-state HMM is not identifiable on five
   observations, **§13's weights are renormalised a second time and §9 loses conditions 4–6** — that
   is a spec change, and steps 4 and 7 are written against it.
3. **The granularity decision.** Three independent measurements say §6's 15-minute Hurst cannot come
   from 5-minute bars. **If the pull is 5-minute, §9 condition 7 is permanently closed and two S13
   columns are dead on arrival.** This belongs before the pull.
4. **AWS credentials** for the requester-pays bucket. ~$0.06 by Dukascopy's own worked example.

### 9.2 Open questions this plan does not close

- **Stage 13 — "near a prior-day LVN or HVN".** Needs a volume profile; spot XAUUSD has no real
  volume, only tick counts. It is **not** on §15's SKIPPED list beside 8, 9, 10 and 14. Either it
  joins them, or the tick-count proxy is written down as its definition **before** E2 runs. A room
  decision.
- **§9's cancel conditions.** Four of the five reference OFI, CVD or Hawkes and cannot run on spot.
  The fifth — *"the estimated expansion probability falls below 0.55"* — depends on E4. **If E4
  kills the HMM, the limit order has no cancel condition at all** other than its 20-second expiry,
  and whether that is acceptable is a decision nobody has made.
- **Prop-firm rules.** §11's `DLL_internal = min($1100, 0.75 × DLL_firm)` names a firm that has not
  been chosen. Until one is, $1,100 is a placeholder and the report must say so.

---

## 10. What would make this fail, written down in advance

So that it is scored rather than rationalised.

1. **The funnel dies at stage 3.** The $15/oz filter is rarely satisfied and there is no sample. This
   is the outcome E1 and E2's drafts both expect, and it would be **a finding about the spec**, not
   a failure of the engine.
2. **The funnel survives too easily.** A very high survivor count means the conditions condition on
   nothing and §13's `Score ≥ 0.72` carries the whole filter. **This is the outcome that looks good
   and is not**, which is why every stage's count is reported and not only the last.
3. **It passes in-sample and fails C6.** The ordinary way a strategy dies, and the reason the OOS
   window rule is 4 of 5 rather than an average.
4. **It passes everything and the holdout disagrees.** Then the answer is no. **C8 is opened once,
   and no re-tune follows it** — a holdout you re-tune against is a validation set with a better name.
5. **The intra-bar assumption carries it.** If step 8's measurement shows 5-minute bars cannot
   resolve a 20-second order life, the backtest is an upper bound and must be labelled one
   everywhere it is quoted.

**A miss is scored, not rounded** — `REACH.md` §5 and `M4_PATH.md` §2 both record their own
predictions failing, and this document expects to join them.

---

## 11. What is borrowed from Quant_trading, and what is deliberately not

| Borrowed | Why |
| :--- | :--- |
| The gate contract as a **hard table checked before enabling anything** | `backtest.md` §1 is the strongest idea in that repo |
| The **pessimistic fill model** — cross the spread, 1.5× slippage, last in queue | Strategies that need better execution should fail, and that is correct |
| **Walk-forward with an untouched holdout** | Already this repo's §14; the driver shape is theirs |
| **Risk as absolute veto**, no override path | A rule satisfiable by shrinking gets shrunk |
| **One markdown report per run**, gate table first | `reports/` is how that project stays honest across months |
| **Config-as-data**, every parameter annotated with the decision that set it | A parameter with no provenance is a parameter nobody can defend |

| Not borrowed | Why not |
| :--- | :--- |
| 13 strategies and an ensemble | Track C is one strategy. An ensemble of one is a strategy |
| The **ML regime classifier** and RL-lite weight feedback | ~40–100 trades/year cannot support a model that re-weights itself |
| **Live MT5 execution and the connector layer** | Behind §7's gates, not beside them |
| **Daily-win-rate as the primary metric** | One trade a week makes it a measurement of the calendar |
| Telegram/alerting, sentiment, news-content pipelines | Not this engine's question |

---

## 12. The one-paragraph version

**Track C becomes a self-contained mathematical engine** — ten files, ~1,100 lines, under
`services/signal-data/track_c/` — that imports every feature definition it needs rather than forking
them, and owns its event loop, fill model, metrics, walk-forward and gates. **Its filters are four
ordered layers that can only refuse, never negotiate**, and every refusal is counted, because the
first honest artefact this engine can produce is an attrition table and not an equity curve. **Its
gates are committed before its first run**, adapt six of Quant_trading's eight, drop two that a
one-trade-a-week strategy makes meaningless, and add a deflated Sharpe that Quant_trading does not
have. **Roughly 400 of those lines are unblocked today.** The rest waits on four unwritten
predictions, E4's verdict on the HMM, and the granularity decision — and the plan is ordered so that
waiting costs nothing.
