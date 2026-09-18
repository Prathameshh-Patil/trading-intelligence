# Strategy workflow — the three tracks, separately, and how each one is actually wired

**Written 2026-09-18.** A companion to [`PROJECT_MAP.md`](PROJECT_MAP.md), narrowed to one question:
**what happens to a strategy, from data to verdict, on each of the three tracks.** The map shows the
whole repo; this shows the strategy lanes and nothing else.

> **Precedence.** [`plans/current.md`](../plans/current.md) is live status,
> [`plans/team/`](../plans/team/README.md) is the plan, [`docs/strategy/ARCHITECTURE.md`](strategy/ARCHITECTURE.md)
> is the research architecture. **If this file disagrees with any of those, they win.**
>
> **How this was built.** Every arrow below was checked against the code on 2026-09-18 — function
> signatures, module imports, constants — not read off prose. Where the code and the documentation
> disagree, the code is what is drawn, and the disagreement is called out. Two such disagreements
> are recorded in §4.1 and §5.4.

---

## 0. The one-line version

| Track | Instrument | Question it asks | State |
| :--- | :--- | :--- | :--- |
| **A — order flow** | GC futures only | Does the aggressor side predict direction? | ⛔ **Parked.** Measured flat against its own null |
| **B — portable** | GC + XAUUSD | Does bracket geometry, vol state or the clock pay? | ✅ **Finished. Negative.** No cell clears the cost floor |
| **C — magnitude expansion** | Spot XAUUSD | When is the next hour *large*? | ◐ **Being built.** Three tested blocks, not yet one chain |

They do **not** share a pipeline. A and B share a measurement spine (`backtest.py` → `reach.py`);
C has its own (`pipeline.py` → `fsm.py` → `e3_cost.py` → `tuning.py`) and does not touch either.

---

## 1. Track A — order flow. GC only. Parked with a measured verdict.

```
Databento GC ticks ── 19 months, 46M trades, on disk
        │
        ▼
  s1.load_ticks ─► minute_bars  (session-reset CVD)
        │
        ▼
  strategies.py primitives:  delta_z · cvd_slope · absorption · bar_imbalance
        │
        ├─► delta_outlier      (|delta_z| > z)
        ├─► cvd_divergence     (price flat, CVD rising)
        ├─► absorption_fade    (size absorbed at a level)
        └─► footprint_stack    (stacked imbalance)
        │
        ▼
  families.py:  conditions() ─► arms() ─► eligible
        │           ▲
        │           └── features/regime_filter.passes + regime_kappa   (κ ≥ 0.75)
        ▼
  measure(entries, rates)  ──vs──  archive_rates()   ← the matched null
                           ──and── horizon.mde_rate  ← the power it actually had
        ▼
  analysis/FAMILIES.md :  −0.0058  and  −0.0003
        at power that would have caught a 30% relative lift
        ▼
  ⛔ PARKED.  regimes.py (786 lines, clusters on cvd_slope / cvd_persistence) parked with it.
```

**Why it matters that this one is the negative result.** Track A is the track with the genuine
information advantage — `delta` and `cvd` are the numbers a screenshot can never contain, because a
rendered candle threw the aggressor side away. That advantage was real, it was validated
independently (quote-rule reclassification agrees with `SIDE_MAP` on 99.65% of 75,578 trades), and
it still produced no edge. **An information advantage that produces no edge is not yet a product**,
and that is logged as open question #1.

**Parked means parked** — discipline rule 11. Nothing is deleted, and no Track B or C work modifies
a Track A module.

---

## 2. Track B — portable geometry, vol and clock. Finished, negative.

Three strategy functions, deliberately disjoint owners, **all non-directional.** They return `+1`
where the rule fires and `0` where it does not — **never `−1`**.

> This is the thing most easily misread. The `move_*` columns `backtest.evaluate` produces are
> signed, but the claim these three make is about **magnitude**: `P(|move| ≥ T within H)`. Reading a
> hit rate off `move > 0` answers a question none of the three asks.

```
 ┌─ M1 ──────────────────────┐ ┌─ M2 ─────────────────────┐ ┌─ M3 ───────────────────────┐
 │ strategies.m1_geometry    │ │ strategies.m2_vol_       │ │ strategies.m3_session_     │
 │   (bars, inst, side)      │ │   momentum(window,       │ │   event(phases,            │
 │                           │ │   min_bars, slope_min)   │ │   event_window_minutes)    │
 │ NO entry condition, on    │ │                          │ │                            │
 │ purpose — enters every    │ │ rv_slope ≥ slope_min     │ │ session_phase ∈ phases     │
 │ bar and lets the sweep    │ │ = EXPANDING              │ │        OR                  │
 │ decide. The grid is swept │ │                          │ │ event_proximity ≤ window   │
 │ at the CALL SITE, in      │ │ Train half only — it     │ │ (arms separable; all three │
 │ m1_sweep.py, pre-         │ │ selects, so it costs     │ │  cuts — phase-only, event- │
 │ committed before the run. │ │ out-of-sample data.      │ │  only, union — reported    │
 │                           │ │                          │ │  together, so the union    │
 │                           │ │                          │ │  cannot become the winner  │
 │                           │ │                          │ │  after the fact)           │
 │ Varad                     │ │ Varad                    │ │ Prathamesh                 │
 └───────────┬───────────────┘ └───────────┬──────────────┘ └────────────┬───────────────┘
             │        entries: +1 / 0      │                             │
             └──────────────┬──────────────┴─────────────────────────────┘
                            ▼
        features/portable.py   atr_bp · session_phase · rv_slope · event_proximity
                            ▼
        backtest.evaluate(entries, target, stop, horizon)  ─►  legs
            first_touch · first_touch_from · excursions
            ◄── ONE first-touch convention, and it lives in backtest.py
                            ▼
        base_rates.py (the null) + horizon.mde_rate (power) + replay.py (tick-path check —
                                       bars carry the MFE/MAE order 95.8% of the time)
                            ▼
        m1_sweep.reach_table  ─►  reach.build  ─►  reach_table.csv, 10,368 rows
                            ▼
        reach.cell_of(bars) ─► lookup() ─► reach()
            KEY  = instrument · bucket · phase · vol_state · side
            AXES = phase, vol_state          MIN_SAMPLES = 400 → below it, the answer is null
            *** a LOOKUP, not a chooser ***
                            ▼
        GET /api/v1/forecast/table  ─►  desktop ForecastView
            every p renders as a band (p, pMax) · rows in GRID order, never sorted by p
```

**Verdict.** GC bracket geometry is a random walk minus cost (`M1_SURFACE.md`). `ev_sym` is positive
on 4.4% of served rows with the median sitting *at* the cost floor. The clock conditions volatility
but produces no edge (`M3_CLOCK.md`). 116 of 144 reach cells clear the sample floor — 81% — and
`phase` and `vol_state` are **not independent** (`REACH.md`).

**The one open step.** Build order step 6 — route-2 spot feed and the portable refit — is the last
prerequisite, and it is exactly what Track C's transport unblocks.

### 2.1 Why `reach.py` refuses to choose

Two UI rules enforce this rather than merely documenting it: probabilities render as bands, never a
midpoint; rows render in grid order, never value order. Sorting by `p` would quietly make the UI the
chooser `reach.py` declines to be — **whatever lands on top of a list reads as the recommendation**,
whether or not anything called it one.

---

## 3. Track C — magnitude expansion, spot XAUUSD. Being built.

A different question on a different instrument, with its seam (**S13**) frozen before any feature
code was written. Spec: [`superpowers/specs/2026-09-18-magnitude-expansion-design.md`](superpowers/specs/2026-09-18-magnitude-expansion-design.md).

```
Dukascopy S3 (.bi5, requester-pays, ticks back to 1997)
   │  spot_s3.py  ── the S3 transport that replaced the throttled HTTP path
   ▼
 dukascopy.decode ─► spot.bars  (bars off the MID; spread_bp in its own column)
   │
   ▼
 pipeline.build(bars, events)  ── assembles the S13 frame, 20 columns exactly
   │
   ├ §2  volatility.yang_zhang  n = 12 / 48 / 288 ──┐
   ├ §2  volatility.garch_fit ─► σ_garch ───────────┴─► combine_sigma ─► r_hat_60
   │                                                     └─► r_hat_60_usd · r_ratio
   ├ §6  hurst.hurst_dfa + hurst_vt ──► h_dfa_15m · h_vt_15m · h_agree
   ├ §1  structure.in_window  ──► phase · session
   ├ §12 structure.news_lockout ──► news_lockout
   ├ §7  p_build · p_expand ............... NaN   ← E4 decides whether a 3-state HMM is
   │                                                identifiable on 5 observations
   └ §9  swept_level · reclaim_dt_s · wick_w  NaN  ← Prathamesh's; structure.sweeps()
   │                                                exists, but runs on TICKS
   ▼
 features/frame.require(df)   ── missing AND extra columns both raise, and both name names
   ▼
   ╎  ◄══ ⚠ THE ADAPTER THAT DOES NOT EXIST YET — §5.4
   ▼
 classifier.fit / predict  on (h_dfa_15m, r_hat_60_usd, s_sweep, s_reclaim)
        ─► logistic ─► fit_isotonic ─► calibrated p_E
           scored by brier() and bucket_rate() over the 0.60–0.64 band
   ▼
 fsm.score(row)       §13's weights, renormalised over the six that survive on spot:
                      s_vol .30 · s_sweep .30 · s_hurst .20 · s_hmm .20
                      s_spread −.10 · s_news −.10
                      (S_OFI, S_CVD and S_Hawkes went with the tape; a missing
                       component RAISES rather than defaulting to zero, because a
                       score over fewer terms is a different threshold wearing the
                       same number)
   ▼
 fsm.exclusions(row, day)   ten hard kills that OVERRIDE the score outright:
       r̂₆₀ ≤ $15 · h_agree ≤ 0.58 · no sweep · stop > $5 · slippage > 25% of stop
       · news lockout · p_E < 0.62 · 2 trades today · 2 losses today · position open
   ▼
 fsm.admit ─► TradeCandidate | None        None is no trade, and the reason is in exclusions()
   │            stop   = entry − d·side
   │            target = entry + clip(2.5·d, $10, $15)·side
   │            d_bp, r_bp, cost_bp are CARRIED, not recomputed downstream, so a backtest
   │            and a live path cannot disagree about the price they divided by
   ▼
 fsm.limit_price = P_sweep + 0.5·W  ─► place_limit ─► expire (20s) ─► move_stop
   ▼
 fsm.size_lots(equity, risk_frac = 0.4%, d_usd, day)
   ▼
 e3_cost.ev_bp · breakeven · d_floor_usd     ◄── E3: where §10's stop range can even start
 tuning.folds · Trials · deflated_sharpe     ◄── purged walk-forward, unresettable trial
                                                 counter, and the haircut
```

### 3.1 What the §7 NaNs mean

`pipeline.build` writes `p_build`, `p_expand`, `swept_level`, `reclaim_dt_s` and `wick_w` as **NaN,
never zero** — the module says so in a comment, and it is the right call. Zero is a value; NaN is an
admission. Dropping the columns instead would be a seam change and would need both lanes, so they
stay and carry NaN.

**§7 lost three of its eight observations with the tape** — `OFI_z`, `CVD_z` and `λ_t`. Five remain,
and **E4 exists to test whether a 3-state HMM is identifiable on five observations before it is
wired in at all.**

---

## 4. The experiment programme — separate from the strategy lanes

Each experiment carries a prediction committed **before** its code exists, in its own commit,
timestamped ahead. That is discipline rule 6, and it is why four of these are blocked on a person
rather than on a machine.

| | Question | Owner | State |
| :--- | :--- | :--- | :--- |
| **E0** | The transport — S3 coverage, earliest date, cost | Prathamesh | ✅ ticks back to **1997**, cross-check exact |
| **E1** | Is the spec's own $15/oz filter ever satisfied? | Varad | ⛔ prediction unwritten |
| **E2** | Does the 16-condition funnel produce ≥ 100 events? | Varad *(delegated from Prathamesh, 18 Sep)* | ⛔ prediction unwritten |
| **E3** | The cost floor, and where §10's stop range starts | Varad | ◐ arithmetic half built; empirical half blocked |
| **E4** | Is a 3-state HMM identifiable on 5 observations? | Varad | ⛔ Day 3 |
| **E5** | Does order flow add anything? (GC control) | either | optional — prices what the spot decision costs |

### 4.1 E2's funnel, drawn

E2 is **not** a strategy run. It **counts and never trades** — no P&L, no fills, no position. An
attrition table is immune to the failure mode a backtest has, which is that a promising equity curve
stops anyone asking how many trades it rests on.

```
  the longest archive available on the day
        │  applied IN ORDER, cumulative AND, 16 rows printed always
        ▼
   1  active session window                       Prathamesh   structure.in_window
   2  no high-impact news lockout                 Prathamesh   structure.news_lockout
  ─────────────────────────────────────────────────────────────────────────────────
   3  R̂₆₀ > 150 ticks                             VARAD ◄── the draft says THIS kills
   4  HMM Build / elevated transition             VARAD  §7   (NaN today)
   5  P(B_t) > 0.60                               VARAD  §7   (NaN today)
   6  P(E_{t+1}) > 0.60                           VARAD  §7   (NaN today)
   7  H₁₅ₘ > 0.58                                 VARAD  §6
  ─────────────────────────────────────────────────────────────────────────────────
   8  CVD_z > 1.0                                 ░ SKIPPED — no tape on spot
   9  price flat while CVD rises                  ░ SKIPPED — no tape on spot
  10  OFI_z > 2.5 for 3 × 10s                     ░ SKIPPED — no tape on spot
  ─────────────────────────────────────────────────────────────────────────────────
  11  prior Asian high / low swept                Prathamesh   §9
  12  reclaimed within 30s                        Prathamesh   §9   ◄══ DECIDE HERE
  ─────────────────────────────────────────────────────────────────────────────────
  13  near prior-day LVN / HVN                    ⚠ see below
  14  Hawkes clustered initiation                 ░ SKIPPED — no tape on spot
  15  calibrated p_E ≥ 0.62                       VARAD  §8
  16  stop distance gives acceptable size         §10 / §11

        < 100 survivors → the spec cannot be validated on this archive at ANY parameter
                          setting. The funnel is loosened before it is tuned, and which
                          condition was loosened is recorded.
        100 – 400       → testable but underpowered. §7.3's three-parameters-per-fold cap
                          becomes load-bearing, and the deflated-Sharpe haircut does real work.
        > 400           → proceed as designed.
        VERY high       → the outcome that looks good and is not. The funnel is conditioning
                          on nothing and §13's Score ≥ 0.72 is carrying the whole filter.
```

**⚠ Stage 13 is a question this document is raising, not answering.** "Near a prior-day LVN or HVN
rejection zone" needs a **volume profile**, and spot XAUUSD has no real volume — only tick counts.
Stage 13 is **not** on the SKIPPED list alongside 8, 9, 10 and 14, and either it should be, or the
tick-count proxy needs to be written down as the definition before E2 runs. Flagging it rather than
deciding it: the funnel's stage list is `mathematical.md` §9, and changing it is not a solo call.

**Why §15 moved to Varad.** Stages 3–7 are the magnitude columns, and the draft's own argument is
that stage 3 does the killing — so the owner of that model writes the number. Prathamesh keeps
stages 1, 2, 11 and 12 as consumer and will read the result rather than predict it.

**One thing to notice before writing the number:** stages 4–6 are NaN today. If the HMM stages are
skipped or pass through in the first run, **stage 3 is the only magnitude condition doing any work**,
and the §15 prediction is effectively a prediction about the $15/oz filter — which is E1's question.
The two predictions are less independent than the section numbering suggests.

---

## 5. What is actually connected — checked against imports, not prose

### 5.1 Track A

`families.py` imports `backtest`, `signals.engine`, `features.expansion.atr`,
`features.regime_filter`, `horizon.mde_rate`, `instruments.GC`. Complete and run. Parked.

### 5.2 Track B

`m1_sweep` imports `backtest`, `features.portable`, `horizon`, `instruments`, `m2_magnitude.vol_state`,
`regimes.resample_bars`, `s1`, `strategies.m1_geometry`. `m2_magnitude` and `m3_profile` import the
same spine. `reach` imports `m1_sweep`, `features.portable`, `instruments`, `m2_magnitude.vol_state`.
`replay` imports `backtest.excursions`, `instruments`, `s1`. Complete and run.

### 5.3 Track C, block by block

| Block | Imports | Tested | Wired to its neighbours |
| :--- | :--- | :--- | :--- |
| `spot_s3` → `spot` | — | ✅ | ✅ |
| `pipeline.build` | `volatility`, `hurst`, `structure`, `frame` | ✅ | ✅ upstream |
| `classifier` | sklearn only | ✅ | ❌ |
| `fsm` | `e3_cost`, `features.frame.TradeCandidate` | ✅ | ❌ |
| `e3_cost` | stdlib only | ✅ | ✅ (into `fsm`) |
| `tuning` | numpy/scipy only | ✅ | ❌ |

### 5.4 The missing wire, stated plainly

**`fsm.py` imports exactly two things from this repo: `e3_cost` and `frame.TradeCandidate`.** It does
not import `pipeline` and it does not import `classifier`.

It consumes a plain `row: dict[str, float]`, and the keys it reads are **not** S13 column names:

| `fsm` reads | S13 frame supplies | Gap |
| :--- | :--- | :--- |
| `r_hat_60_usd` | `r_hat_60_usd` | ✅ same name |
| `news_lockout` | `news_lockout` | ✅ same name |
| `h_agree_value` | `h_agree` | ✏️ renamed |
| `has_sweep` | `swept_level`, `reclaim_dt_s`, `wick_w` | 🔧 derived |
| `p_e` | — | 🔧 from `classifier` |
| `d_usd`, `slippage_usd` | — | 🔧 from `e3_cost` / §10 |
| `s_vol`, `s_sweep`, `s_hurst`, `s_hmm`, `s_spread`, `s_news` | — | 🔧 §13 components, underived |

So the three blocks are each real and each tested, and **the adapter from an S13 frame row to an FSM
row is the missing piece.** It is small, and it is the next thing to write. It is recorded here
rather than discovered later, because the failure mode of not recording it is somebody assuming the
chain runs end to end because each of its parts does.

---

## 6. The discipline that explains why the lanes look like this

The full list is [`PROJECT_MAP.md`](PROJECT_MAP.md) §11. The four that shape the strategy code
specifically:

1. **Portable or it does not belong in `features/portable.py`.** Both instruments, or neither. That
   is why Track A's `orderflow.py` and `regimes.py` are separate modules and not options inside the
   portable surface.
2. **`has_flow: False` raises.** It does not degrade, fall back, or substitute a proxy — a degraded
   number looks exactly like a real one. Same reason `fsm.score` raises on a missing component and
   `pipeline.build` writes NaN rather than zero.
3. **A prediction is committed before the run that reads it**, in its own commit, timestamped ahead.
   Four of these are why E1–E4 are blocked on a person.
4. **A miss is scored, not rounded.** `REACH.md` §5 and `M4_PATH.md` §2 both record their own
   predictions failing. E2's prediction will be scored the same way.
