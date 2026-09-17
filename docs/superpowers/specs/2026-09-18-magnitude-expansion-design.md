# Magnitude Expansion on Spot XAUUSD — design

**Written 2026-09-17, for the 18–20 Sep block.** Source spec: [`mathematical.md`](../../../mathematical.md).
Prior art: [`vrd07/Quant_Trading`](https://github.com/vrd07/Quant_Trading) — Varad's own repo, 158 commits,
same instrument, same prop-firm framing.

> **Decisions this document implements**, taken 2026-09-17 and not re-opened here:
> `mathematical.md` **supersedes** the Track A/B research programme · execution instrument is
> **spot XAUUSD on a CFD prop firm** · trades-only order-flow proxies are **dropped**, not built ·
> the 18/21/25 Sep scheduled items are **suspended for three days** and recorded as missed ·
> the three days are **Fri 18 – Sun 20 Sep**.

---

## 1. What this supersedes, and what it explicitly does not

`mathematical.md` becomes the strategy of record. `plans/team/strategy-precommit.md` §1–§12 and the
M1/M2/M3/M3b/M4b/REACH programme stop generating new work.

**Superseding the programme does not retract its findings.** They are measurements of the same metal
over the same period and they constrain this spec's priors:

| Finding | Where | What it does to `mathematical.md` |
| :--- | :--- | :--- |
| M1's geometry surface is a random walk minus cost | `M1_SURFACE.md` | **Undercuts §9.** The directional long/short entry inherits a measured negative prior |
| M2 clears, and it is about scale | `M2_MAGNITUDE.md` | **Supports §Objective.** Conditional magnitude is the one axis that has ever cleared here |
| No time-of-day drift; the period's *entire* drift is +0.1878 bp/30m against a 0.3504 bp round trip | `M3B_DRIFT.md` | **Kills any drift-capture reading of §1's session windows.** They survive as *volatility* windows only |
| Path ordering measured, `first_touch` recommendation is *no* | `M4_PATH.md` | Carries into §10's exit modelling unchanged |
| REACH table — 19 months of "does price reach X within H" | `REACH.md` | **Is §Objective's own filter, already computed.** See §6.1 |

**The internal contradiction in the source spec, named once.** §Objective commits to non-directional
magnitude — `M_{t,h} = |P_{t+h} − P_t|` — while §9 is an entirely directional long/short funnel.
These are not the same system. This design keeps **§Objective as the estimand** and treats §9 as a
*conditioning event*, not as a direction forecast. M1 is the reason: we have already measured that
direction does not pay here, and magnitude has.

---

## 2. Instrument, units, and the venue

Execution is **spot XAUUSD at a CFD prop firm**. That voids §1's entire GC-tick economics.

The source spec anticipated this and gave the rule: *"use dollar and price-distance normalization
rather than assuming that every broker defines a pip identically."* Applied:

| §  | As written | As implemented |
| :--- | :--- | :--- |
| Objective | `Q₀.₆₀(M_{t,60}) > 150 ticks` | `P(\|ΔP₆₀\| ≥ $15.00/oz) ≥ 0.60`, and in bp at the prevailing price |
| §10 stop | `20 ≤ D ≤ 50 ticks` | `$2.60 ≤ D ≤ $5.00 /oz` — the floor is raised from $2.00 by §13's own slippage exclusion; see §4 |
| §10 target | `R = max(2.5D, 100 ticks)`, cap 150 | `R = max(2.5D, $10.00)`, cap **$15.00/oz** |
| §11 sizing | `V = 10` (GC), `V = 1` (MGC) | `V = $100` per `$1.00/oz` per standard lot (100 oz); lots fractional to broker minimum |

**No quantity in this system is ever expressed in ticks or pips.** USD/oz and basis points only.
A pip is a broker's opinion; a basis point is not.

**§11's `$1,100` internal daily loss is not carried over.** It was derived against futures-firm
parameters. `DLL_internal = min(0.0075 × A, 0.75 × DLL_firm)` is re-derived against the chosen firm's
**current published** rules, read from the firm's site on the day, exactly as `mathematical.md`'s own
footnotes insist. Firm selection is out of scope here.

---

## 3. Data architecture

### 3.1 The transport finding, and the correction it forces

`analysis/SPOT_FEED_CHECK.md` currently concludes *"Dukascopy is finished as a bulk source from this
address."* **That verdict is wrong about the source and right about the transport**, and it has
gated route 2 since 11 Sep.

Measured 2026-09-17, ~23:20–23:40 IST:

```
hourly tick endpoint, 3 cold probes after 3 days' rest    2 ok / 3      then a wall
budget probe, 6 consecutive                               0 ok / 6
re-probe with retries=3, timeout=20                       0 ok / 2      incl. an hour that worked 10 min earlier
daily candle endpoint, 12 consecutive                     0 ok / 12     HTTP 429, explicit
```

**The 429 is the diagnostic nobody had.** `dukascopy.py` surfaces resets and timeouts, so the wall
read as an IP ban. It is a documented rate limit, and its JSON body names the sanctioned path:

```json
{"error": "Too Many Requests. For instructions, see: https://www.dukascopy.com/wiki/en/development/data-export/"}
```

That page documents an **S3 requester-pays bucket** — `cfg-public-proper-wallaby`, `eu-west-1`,
daily `.bi5` files under `SYMBOL/YEAR/MONTH/`, via AWS CLI or boto3 with `--request-payer requester`.
Worked example in the docs: EUR/USD's full history, **2.6 GB / 26,586 files / ≈ $0.06**.
No rate limit. Pricing is `$0.0004` per 1,000 requests plus `$0.02/GB`.

⚠️ **Unverified.** The bucket name, XAUUSD's coverage and the date range are documentation claims.
**E0 (§6.0) verifies them before anything is built on top.** If S3 fails, the fallback is
`Quant_Trading/scripts/fetch_dukascopy.py`'s **daily candle** endpoint —
`BID_candles_min_1.bi5`, one file per day, ~1,300 requests for five years instead of 43,800.

### 3.2 What the archive gives, and what it cannot

| | XAUUSD spot (Dukascopy) | GC futures (on disk) |
| :--- | :--- | :--- |
| Span | 5+ years, pending E0 | 19 months, 46,034,813 trades, 419 sessions |
| Resolution | tick bid/ask + indicative volumes | trades with `aggressor_side` |
| Traded volume | ❌ none | ✅ |
| Aggressor | ❌ none | ✅ (3.3% unknown) |
| Top-of-book spread | ✅ 1.91 bp median | ❌ degenerate, one tick |
| Session | 24×5, continuous | CME break bisects Asia |

**Indicative volume is not volume, and both repos already say so.** `spot.py`: *"`ticks` is named
`ticks` and never `volume`."* `Quant_Trading/scripts/fetch_dukascopy_ticks.py`: *"Volumes are
Dukascopy's indicative liquidity — proxy weights, NOT true traded size (spot gold has no
consolidated tape)."* `instruments.require_flow` enforces it in code. Nothing downstream aggregates
`bid_vol`/`ask_vol` as size.

### 3.3 What dies, and what is newly alive

| | §  | Status |
| :--- | :--- | :--- |
| ❌ | §3 volume clock (1,000-contract bars), §3 OFI | **Dead.** No traded volume |
| ❌ | §4 aggressive delta, CVD, delta divergence | **Dead.** No aggressor, no tape |
| ❌ | §5 marked Hawkes trade arrivals | **Dead.** Quote updates are not trades |
| ✅ | §7's `spread` observation | **Alive, and only on spot.** GC cannot see it |
| ✅ | §14's five-year walk-forward | **Alive.** The 19-month ceiling was a GC-archive limit, not a gold limit |

Cost: **4 of §9's 16 entry conditions (8, 9, 10, 14), 3 of §13's 9 score weights, 3 of §7's 8
observation components.** What remains is the magnitude/volatility engine plus the sweep geometry —
the mathematical core.

### 3.4 The GC archive gets a better job

The 46M-trade archive becomes the **control for a question the spot data cannot ask**: *does order
flow add anything to a conditional magnitude forecast?* Fit §2/§6 on GC bars, then on GC bars plus
CVD/OFI, measure the delta. If flow adds nothing, trading spot costs nothing structural **and it
will have been proven rather than assumed**. This is E5 (§6.5), optional, Day 3.

---

## 4. The cost model, and where it actually binds

`Quant_Trading/src/backtest/fill_model.py` carries a measured venue spread:

```python
DEFAULT_BASE_SPREAD_PRICE_UNITS = {"XAUUSD": Decimal("0.30")}   # "typical Goat Funded XAU"
```

Thirty cents. At $3,400 gold, the three venues in play:

| Venue | Round-trip spread | In bp at $3,400 |
| :--- | ---: | ---: |
| GC front month | 1 tick = $0.10 | **0.29** (`M3B_DRIFT.md`'s floor: 0.3504 incl. commission) |
| CFD prop firm | $0.30 | **0.88** |
| Dukascopy spot | $0.65 | **1.91** (`SPOT_FEED_CHECK.md` §1, median) |

**Spot execution costs roughly 3× GC's floor, and the data source is wider than the venue.** That
second clause is the one that matters for the protocol: the archive we will validate on quotes a
*wider* spread than the account we intend to trade, so a result measured on Dukascopy ticks is
conservative rather than optimistic. It is still not transferable — `spot.py` and `ARCHITECTURE.md`
§7 both record that spot spread is a broker pricing decision, not a market outcome.

Run `mathematical.md`'s own parameters through each. Using §10's **widest** stop, `D = $5.00/oz`
(14.71 bp), `R = 2.5D = $12.50/oz` (36.76 bp), and the spec's stated 42% win rate:

| Cost | EV per trade | Break-even win rate `p* = (D+c)/(R+D)` |
| :--- | ---: | ---: |
| GC, 0.35 bp | **+6.56 bp** | 29.3% |
| Prop firm, 0.88 bp | **+6.03 bp** | 30.3% |
| Dukascopy, 1.91 bp | **+5.00 bp** | 32.3% |

**The spread is not what kills this strategy.** At §10's wide stop, 42% clears break-even with ~10
points to spare at every venue considered. The cost question moves from "is the venue viable" to
"which part of §10's stop range is viable", and there the answer is sharper:

1. **§13's own exclusion binds at the tight end of §10's stop range.** §13 rejects a trade when
   estimated slippage exceeds 25% of intended risk. At `D = $2.00/oz` (5.88 bp), the Dukascopy-width
   spread alone is **32% of risk** — the trade is excluded before slippage is even added. The
   break-even is `D = c/0.25` = **$2.60/oz**, so **the bottom ~20% of §10's stated `$2.00–$5.00`
   range is unreachable under the spec's own rule.** §10's stop range should be restated as
   `$2.60 ≤ D ≤ $5.00` — and that is a consequence of the spec, not an override of it.
2. **The tight end is also where the payoff claim stops being credible.** At `D = $2.00`,
   `R = max(2.5D, $10.00)` is `$10.00` — a 5:1 payoff. A 42% win rate at 5:1 is a much stronger claim
   than 42% at 2.5:1, and nothing in the source spec argues for it. E3 reports EV across the whole
   `(D, R)` rectangle precisely so this is visible rather than assumed.

`Quant_Trading` flags the same gap: *"we have no per-bar spread series and the live trade journal has
<100 fills today."* **Spot data fixes exactly this** — `spread_bp` is a real per-bar series.

**The design rule that follows is not a choice:** *validate on the data source's spread, design
against the execution venue's.* Spread is a config input, never a constant, and **every reported
result carries a sensitivity band at 0.9 / 1.9 / 4.0 bp.** A result quoted at one spread is not a
result.

---

## 5. Architecture

### 5.1 The seam — `S13 · ExpansionFeatures`

Frozen in the first 45 minutes of Day 1, one file, both engineers, committed before any feature code.
Same discipline as S2 (30 min, *"the most valuable half hour of the week"*), S8 and S9.

```
ExpansionFeatures        per bar, both lanes write, the scorer reads
  ts, mid, spread_bp                      frame identity  (Prathamesh)
  r_hat_60_bp, r_ratio                    §2 ensemble     (Varad)
  sigma_yz_12/48/288, sigma_garch         §2 components   (Varad)
  h_dfa_15m, h_vt_15m, h_agree            §6              (Varad)
  p_build, p_expand                       §7 HMM          (Varad)
  session, phase, news_lockout            §1 §12          (Prathamesh)
  swept_level, reclaim_dt_s, wick_w       §9              (Prathamesh)

TradeCandidate           emitted by the FSM, consumed by risk
  side, p_e, score, entry, stop, target, d_bp, r_bp, cost_bp
```

Neither lane imports the other's module. The scorer imports both and neither imports the scorer.

### 5.2 Lane split

| | **Varad** — magnitude axis | **Prathamesh** — clock, structure, execution |
| :--- | :--- | :--- |
| Spec | §2, §6, §7, §8, §10, §11 | §1, §9, §12, §15, and the data layer |
| Files | `features/expansion.py`, `calibration.py`, new `risk.py`, new `tuning.py` | new `spot_s3.py`, `windows.py`, `calendars.py`, `features/structure.py`, new `fsm.py` |
| Mandate | *"what counts as a signal, what the thresholds are, whether a measurement is honest"* | Owns the clock axis and step-5 replay already |

### 5.3 Model stack

```
bars(5m) ──► §2  Yang-Zhang σ at 12 / 48 / 288        ─┐
             §2  GARCH(1,1)-t, m-step variance        ─┴─► R̂₆₀  ──► filter: R̂₆₀ > $15/oz
                                                                     quality: R̂₆₀ / median > 1.20
             §6  Hurst — DFA and variance-time, 6 scales ──► H₁₅ₘ, agreement
             §7  3-state HMM  {Chop, Build, Expansion}  ──► P(B_t), P(E_{t+1})
                 observation: [R̂₆₀, H, spread, range-compression, σ-ratio]   (5 of 8; 3 died with the tape)
             §9  sweep of Asian extreme → reclaim ≤ 30s ──► event
                                                              │
             §8  logistic on the survivors ──► p_E ────────────┤
             §13 deterministic score ───────────────────────────┤
                                                              ▼
             §15 FSM ──► limit at 50% of reclaim wick, 20s expiry ──► §10 stop/target ──► §11 size
```

**§7's observation vector loses `OFI_z`, `CVD_z` and `λ_t`.** Five components remain. Whether a
three-state HMM is identifiable on five observations is an empirical question, and **E4 (§6.4)
answers it before the HMM is wired into the score.**

---

## 6. The experiment programme

Each experiment has a pre-commitment — prediction and kill condition — **written and committed
before its code exists**, per `strategy-precommit.md`'s closing rule. They land as §13–§18 of that
file, in one commit, before Day 1's first feature line.

### 6.0 · E0 — the transport. *Prathamesh, Day 1, first.*
Verify the S3 bucket for XAUUSD: coverage, earliest date, cost of a one-month pull. Cross-check one
hour against the already-validated sample — **2025-06-18 14:00 UTC, 20,654 quotes, median spread
1.91 bp** — byte-for-byte where possible.
**Kill:** no S3 and no working daily-candle path ⇒ five-year history is unavailable, §14 reverts to
the 19-month GC protocol, and the whole design is re-scoped on Day 1 rather than Day 3.

### 6.1 · E1 — is §Objective's own filter ever satisfied? *Varad, Day 1.*
`P(|ΔP₆₀| ≥ $15.00/oz)`, unconditional and per regime cell, straight off `reach.py` and
`reach_table.csv`. The spec's minimum volatility filter is a quantity this repo has already computed
under another name.
**Kill:** if no conditioning cell reaches 0.60, §Objective's trade-quality filter is unsatisfiable as
written, and the threshold moves **before** anything is built on it.

### 6.2 · E2 — does the funnel produce a testable number of events? *Prathamesh, Day 1.*
§9's sixteen conditions as a **counter, not a strategy**. Survivors printed at each stage, over the
longest span available. No P&L.
**Kill:** fewer than 100 candidates surviving to stage 12 ⇒ the spec cannot be validated at any
parameter setting, and the funnel must be loosened before it is tuned.

### 6.3 · E3 — the cost floor, and where §10's stop range actually starts. *Varad, Day 1.*
§4's table computed rather than quoted. Three outputs: the realised `spread_bp` distribution from the
spot ticks — **by session, not pooled**, since the 1.91 bp figure is one London–NY hour and Asian
spreads are wider; the break-even win rate surface over §10's full `(D, R)` rectangle; and the
`D` floor at which §13's 25%-of-risk slippage exclusion stops firing.
**Kill:** if the surviving `(D, R)` region requires a win rate above anything E1's magnitude base
rates support, §10's stop and target ranges are wrong for this instrument and are re-derived before
Day 2 builds against them.

### 6.4 · E4 — is a 3-state HMM identifiable on 5 observations? *Varad, Day 3.*
Fit on the reduced vector; check state persistence, transition-matrix conditioning, and whether
`P(B_t) > 0.60 → P(E_{t+1}) > 0.60` separates anything a two-state model does not.
**Kill:** states not distinguishable ⇒ drop §7 and let §2's `R̂₆₀` carry the regime signal alone.

### 6.5 · E5 — does order flow add anything? *Either, Day 3, optional.*
The GC control of §3.4.
**Outcome, not a kill:** it prices what the spot decision costs.

---

## 7. Fine-tuning protocol

§14 as written becomes **possible** with five years, and this section implements it plus the four
guards it omits.

### 7.1 Split

```
60 months total
├─ 48 months  cross-validation sample
│    walk-forward: 24 train / 6 validate / roll 3   →  7 folds
└─ 12 months  HOLDOUT, untouched
```

The holdout is committed as a **sha256 manifest before fold 1 runs**, the way
`analysis/gc_data_manifest.md` pins the GC parquets. Untouched becomes provable rather than asserted.

⚠️ **If E0 returns less than 60 months**, the protocol degrades by a stated rule rather than by
improvisation: hold out the final 25% of whatever exists, and size train/validate at 4:1 with a
1-month roll. **Fewer than 24 usable months ⇒ no tuning at all**, only the §6 experiments.

### 7.2 Guard 1 — purging and embargo

§14 says avoid random splits. It does not mention label overlap, which is the larger leak here: a
90-minute label at 15:00 on the last day of a training fold resolves inside the validation fold.

- **Purge:** drop any training sample whose label horizon crosses a fold boundary.
- **Embargo:** drop one further trading day after each boundary.

Both are tested by mutation — removing either must turn a test red.

### 7.3 Guard 2 — parameter tiers and a hard search budget

`mathematical.md` exposes ~18 knobs. E2 will likely return a few hundred trades. Roughly 20 trades
per parameter is not a budget that can be searched freely.

| Tier | Contents | Treatment |
| :--- | :--- | :--- |
| **Structural** | tick/lot value, session windows (§1), news lockout (§12), holdout boundary | **Never tuned.** Changing one is a new experiment |
| **Definitional** | the `Q₀.₃₅ / Q₀.₇₀ / Q₀.₇₅` quantiles (§5, §9), z-score buckets (§3) | **Derived from the training fold.** Not searched |
| **Tuned** | `w_YZ`/`w_G`, `p_E` threshold, `Score` threshold, `H₁₅ₘ` threshold, `D` range, `R` multiple | **At most 3 per fold**, each with a pre-committed monotonicity expectation |

**The monotonicity rule is the real guard.** Before a parameter is searched, the direction
performance should move in across its plausible range is written down. A parameter whose profile
comes back non-monotone and jagged is **being fit to noise, and that is a finding, not a setting** —
it gets frozen at the spec's stated value and recorded.

### 7.4 Guard 3 — multiple-testing haircut

Every configuration evaluated increments a counter **inside the tuner**, so the trial count cannot be
under-reported by whoever writes the summary. Reported Sharpe is deflated for that count. A
configuration that does not survive the haircut is not reported as a result.

### 7.5 Guard 4 — calibration held to its name

§8 says *"calibrated classifier"*. That is a testable claim, not an adjective:

- **Brier score** and a **reliability diagram** on `p_E`, per fold.
- **Isotonic recalibration fitted on the inner fold only**, never on validation.
- **The check:** if the `p_E ∈ [0.60, 0.64]` bucket does not fire near 62% of the time, the 0.62
  threshold means nothing and §8's entry condition is void until it does.

### 7.6 Costs and nulls

- Every result net of spread + commission + slippage, at **0.9 / 1.9 / 4.0 bp** — venue, archive, and a
  stress well beyond either. No single-spread
  numbers.
- **Slippage stress at 1× / 2× / 3×**, per §14.
- **Both nulls this repo already uses** — side-shuffled and time-shifted. Non-negotiable, and
  mutation-tested the way M3b's two guards were.
- **Limit-fill realism:** §9 forbids converting an unfilled limit to a market order, so the fill rate
  is itself a reported metric. A strategy whose edge lives in unfilled orders has no edge.

### 7.7 Deploy gate — adopted from `Quant_Trading`

Its walk-forward retired six strategies, and the criteria transfer wholesale:

```
OOS Sharpe        ≥ 0.5 × IS Sharpe
OOS profit factor ≥ 1.0
OOS win rate      within 10pp of IS
```

Plus this design's own: **positive EV at 4.0 bp**, not merely at the venue's 0.9.

---

## 8. What is deliberately not built

- **No 13-strategy ensemble.** `Quant_Trading`'s confluence gate, nightly RandomForest regime
  classifier and per-strategy weights are a portfolio philosophy. This is one strategy behind a hard
  funnel. Merging them dissolves the funnel into a vote.
- **No live execution, no MT5 bridge, no EA.** Three days produce measurements and a tuning harness.
- **No order-flow reconstruction from indicative volumes.** §3.2.
- **No new UI.** `apps/desktop` is untouched.

---

## 9. Two corrections this work forces on the repo

Both contradict what is currently recorded and go into `daily_updates/` with their evidence:

1. **`analysis/SPOT_FEED_CHECK.md`'s "finished as a bulk source" is wrong about the source.** The
   429, its JSON body, and the S3 path supersede it. The transport conclusion stands; the source
   conclusion does not.
2. **`Quant_Trading/scripts/download_historical_data.py` maps `XAUUSD → GC=F`** and calls the two
   *"within ~$5"*. The 2025-06-18 cross-check in `SPOT_FEED_CHECK.md` §3 measured the basis at
   **≈ +19**. That file labels futures as spot. One-line fix, different repo, recorded here so it is
   not lost.

---

## 10. Open questions this document does not answer

| | Why it is left open |
| :--- | :--- |
| Which prop firm | Determines the real spread and the real `DLL_firm`. §4 handles it as a sensitivity band until the answer exists |
| Whether §7's HMM survives at 5 observations | E4's job. Wiring it in before E4 would be assuming the answer |
| Whether `arch` enters the lockfile | Varad's call on Day 2. A lockfile change earns its own reviewed commit in this repo |
| The Hawkes branching ratio | §5 is dead on spot. It reopens only if a tape-bearing venue is chosen |

---

## 11. What would make us abandon this

Stated now, before any result:

- **E1 returns no cell at 0.60** and no loosened threshold produces one with a positive EV at 4.0 bp.
- **E2 returns fewer than 100 candidates** and loosening the funnel to reach 100 destroys the
  conditioning that justified it.
- **E3 shows break-even win rate above anything E1's base rates support.**
- **The deploy gate fails on 5 of 7 folds** after the haircut.

Any one of these is a written negative result in `analysis/`, not a reason to retune. This repo has
retired M1, M3b's drift pattern and six of `Quant_Trading`'s strategies on exactly that basis.
