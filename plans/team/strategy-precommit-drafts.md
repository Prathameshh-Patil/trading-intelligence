# The four predictions, in final form — for Varad and Prathamesh to review and sign

**Nothing here is a pre-commitment yet.** `strategy-precommit.md` §14–§17 carry 🚫 blocking gaps,
and they stay blocking until one of you moves a block across under your own name. **Editing a block
and moving it is the signature.** When all four have moved, delete this file.

---

## ⚠️ Read this before signing E1 or E2

**Their reasoning is deliberately unrevised, and that is not laziness.**

| | |
| :--- | :--- |
| Drafts written | **2026-09-18 00:15 IST** (`c658c19`) |
| Gate pass rates measured | **2026-09-18 09:46 IST** (`950d186`) |

In between, `pipeline.build` was run on real GC and `daily_updates/2026-09-18.md` §21–§22 recorded
`R̂₆₀ ≥ $15` on **27.5%** of bars and all three volatility/Hurst gates together on **0.4%**. Those
numbers are adjacent to what E1 and E2 measure.

**So E1 and E2 below are the 00:15 text, argued only from what was published before that hour** —
§2's `atr_bp` quartiles, `BASE_RATES.md`, `REACH.md`. Revising them now with the 09:46 numbers would
turn a prediction into a retrodiction wearing a prediction's clothes, and this file's whole purpose
is to make that impossible.

**E3 and E4 are written fresh**, because nothing measured yesterday touches spot spread or the HMM.

**If you think the contamination is disqualifying, the honest remedy is that you write E1 and E2
yourself from the pre-09:46 material, not that I rewrite them.** That call is yours.

---

## §14 · E1 — does any cell reach `P(|ΔP₆₀| ≥ $15.00/oz) ≥ 0.60`?

> *To sign: move everything below the rule into `strategy-precommit.md` §14, replacing the 🚫 block,
> and delete this line. Provenance: written 2026-09-18 00:15, before any gate was measured.*

---

### The pre-committed prediction — Varad, before the run

**No cell reaches 0.60. I expect `max p` in the range 0.25–0.40, in the highest-`atr_bp` cell, and
I will accept anything below 0.50 as consistent with this prediction. Kill condition 1 fires and
§Objective's threshold has to move.**

**The derivation, so a step can be attacked rather than the number.** `strategy-precommit.md` §2
committed `atr_bp`'s quartiles over 109,875 bars: `q25 6.79 · q50 9.65 · q75 13.87`, per 5-minute
bar over a 60-minute trailing window. At $3,400 the median bar's true range is `9.65e-4 × 3400 =
$3.28`. For a driftless walk within a bar `E[range] ≈ 1.596 σ`, so `σ_bar ≈ $2.06`; over twelve bars
`σ₆₀ = 2.06 × √12 = $7.13`; and `$15.00 / $7.13 = 2.10 σ`, which is `P ≈ 0.036`.

In §2's fourth bucket — `14+` bp, 24.5% of bars, call its mean 18 bp — `σ_bar = $3.84`,
`σ₆₀ = $13.29`, `$15.00 / $13.29 = 1.13 σ`, so **`P ≈ 0.26`**. Gold is not Gaussian, so fat tails
push that up; call it 0.30–0.35 in the fattest cell that still has `n ≥ 400`.

**The number that matters more than the verdict.** Solving for the threshold achievable at
`p = 0.60` in that top cell gives `0.524 × 13.29 ≈ $7.00/oz`. **So I predict the honest version of
§Objective's filter is roughly $7, not $15** — and that halving is not cosmetic, because §10's
target is `max(2.5D, $10.00)` capped at `$15.00`. The target range was sized against a move the
instrument does not make in an hour.

### Where this is most likely wrong

1. **The `1.596` factor.** True range includes gaps, so it exceeds within-bar range and `σ_bar` is
   overestimated — which makes my `p` too *high* and strengthens the kill rather than weakening it.
2. **`√12` assumes independence.** If 5-minute returns are positively autocorrelated in the high-vol
   cells, `σ₆₀` is larger and `p` rises. M1 found a random walk, which argues against it, but M1
   measured geometry rather than autocorrelation directly.
3. **The conditioning cells.** I assumed `reach.py`'s cells are essentially `atr_bp` buckets. A cell
   that concentrates volatility harder — news proximity, say — could be fatter than the `14+`
   bucket I used.

---

## §15 · E2 — stage-12 survivors, and what does the killing

> *To sign: move everything below the rule into `strategy-precommit.md` §15, replacing the 🚫 block,
> and delete this line. Provenance: written 2026-09-18 00:15, before any gate was measured.*

---

### The pre-committed prediction — Prathamesh, before the run

**Stage-12 survivors land in the low hundreds. I predict 200–500 over five years, and I will accept
100–800 as consistent. That is outcome 2: testable but underpowered.**

**The single condition doing most of the killing is stage 3, `R̂₆₀ > $15` — not the sweep**, which
is where intuition points. E1's derivation is the reason: a $15 hourly move sits ~2σ out
unconditionally, so the volatility filter alone removes most bars before any structure condition
runs. **If the funnel instead dies at stage 11 or 12, my model of this strategy is wrong** and the
constraint is structural rather than volatility-based, which changes what to loosen.

**The rough accounting**, from ~376,000 five-minute bars over five weekday years:

```
stage 1   session windows      5.5h of 24                    ->  ~86,000
stage 2   news lockout                                       ->  ~84,000
stage 3   R_hat_60 > $15       + the 1.20x quality filter    ->   ~3,000
stage 7   H_15m > 0.58                                       ->     ~500
stage 11  Asian extreme swept  an EVENT, ~1/day in-window    ->   ~1,300
stage 12  reclaim <= 30s                                     ->     ~400
```

⚠️ **The table's unit changes at stage 11 and the report must say so.** Stages 1–7 are per-bar
predicates; stage 11 is an event that happens once or twice a day. Multiplying a bar rate by an
event rate is meaningless, so the funnel switches to candidate sweep events there. **A table that
does not mark where the unit changed has uninterpretable later rows.**

### Where this is most likely wrong

1. **Stage 7's cut.** There is no measurement of `H₁₅ₘ`'s distribution on gold. If Hurst is tightly
   centred on 0.5, `> 0.58` could cut 95% rather than 83% and survivors fall below 100 — outcome 1,
   and the funnel needs loosening before it is tuned. **This is the weakest assumption here.**
2. **The sweep rate.** "~1 per day in-window" is a guess. Asian high *and* low both count, and a
   range-bound Asia produces sweeps of both in one session.
3. **Evaluation order.** §9 lists conditions but does not mandate an order, and the attrition table
   changes meaning if the order changes. **The committed order belongs in the pre-commitment**, and
   putting the cheap volatility filter first is an efficiency choice rather than a neutral one.

---

## §16 · E3 — the per-session spread, and where §10's stop range starts

> *To sign: move everything below the rule into `strategy-precommit.md` §16, replacing the 🚫 block,
> and delete this line. Written 2026-09-18 09:57; nothing measured to date touches spot spread.*

---

### The pre-committed prediction — Varad, before the run

**The arithmetic half is settled and is not a prediction.** At `D = $5.00/oz` and `R = 2.5D`, EV is
positive at a 42% win rate at all three costs, and the `$2.598/oz` D floor follows from `c / 0.25`
at `c = 1.91 bp` — `e3_cost.d_floor_usd` derives it and a test pins it. What needs predicting is the
empirical half.

**Per-session median spread, Dukascopy, and I will accept any ordering that keeps Asia widest and
the overlap tightest:**

```
London-NY overlap   ~1.9 bp      the one measured hour, and the tightest of the day
NY                  ~2.1 bp
London              ~2.2 bp
Asia                ~3.5-4.5 bp
the daily break     >8 bp, and it should be EXCLUDED rather than measured
```

**The D floor at the execution hours lands at $2.20–$3.00/oz, near the design's $2.60, and outcome 3
fires.** §10's stop range is restated as roughly `$2.60 ≤ D ≤ $5.00`.

**Outcome 2 does not fire, and the reason is worth stating because it looks like it should.** Asia's
wider spread does **not** push the floor above $5.00 for this strategy, because **§9 sweeps a level
*formed* during Asia but *executes* inside the 08:00–11:30 and 13:30–15:30 New York windows.**
Asian spread governs how precisely the Asian high and low are *known*, not what it costs to trade
them.

⚠️ **The genuinely new risk this opens, and it is not about cost.** If Asian spread is wide enough
to blur the swept level by more than `δ = max($0.02, 0.05 × ATR₁₀ₛ)`, the level itself is uncertain
by more than the reclaim threshold — and then §9's sweep detection is measuring broker noise rather
than structure. **That lands on §9's sweep definition, not on §10's stop range**, and if it fires it
is a bigger finding than the cost question.

### Where this is most likely wrong

1. **Dukascopy is one broker and an ECN-style one.** Every number here describes the archive, not
   the venue. `ARCHITECTURE.md` §7's standing warning applies: **no threshold derived here
   transfers** to the prop firm.
2. **2025-06-18 is one day.** Spread widens structurally around FOMC and CPI, and §12's lockout is
   ±5 minutes while the widening lasts considerably longer.
3. **The break exclusion is an assumption.** If the daily break's quotes are not excluded, a pooled
   median is meaningless and the per-session table hides it rather than showing it.

---

## §17 · E4 — do three states survive on five observations?

> *To sign: move everything below the rule into `strategy-precommit.md` §17, replacing the 🚫 block,
> and delete this line. Written 2026-09-18 09:57; no HMM has been fitted on this data.*

---

### The pre-committed prediction — Varad, before the run

**Three states will not separate into Chop / Build / Expansion. `k=3` will fit and will produce an
ordered volatility ladder — low, mid, high — and `k=2` will explain nearly as much. I expect
outcome 3, and I expect §7 to be dropped.**

**The strongest prior in this file is `analysis/regimes_2026-09-02/README.md`, which already fit
`k=3` on this instrument. Look at what actually separated the states:**

| regime | n | pct | realized_vol (med) | cvd_slope (med) | cvd_persistence (med) | price_efficiency (med) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 930 | 15.4% | 0.000357 | **+27.566** | 0.612 | 0.540 |
| 1 | 1,296 | 21.5% | 0.000316 | **−26.668** | 0.613 | 0.539 |
| 2 | 3,797 | 63.0% | 0.000275 | −0.199 | 0.206 | 0.341 |

**Regimes 0 and 1 are identical on every feature except the SIGN of `cvd_slope`.** Their
`realized_vol` differs by 13%, their `cvd_persistence` by 0.001, their `price_efficiency` by 0.001.
`realized_vol` spans 0.000275–0.000357 across all three states — it is doing almost no separating
work. **Two of the four fitted features were CVD, and the states resolved on CVD.**

E4 removes CVD. What remains — `r_hat_60_usd`, `h_dfa_15m`, `h_vt_15m`, `spread_bp`,
range-compression, sigma-ratio — is four collinear volatility proxies plus Hurst.

**And Hurst, the one non-volatility observation, was measured unreliable yesterday.**
`daily_updates/2026-09-18.md` §21: on a rolling window the two estimators disagree by **0.0849**
against a 0.05 tolerance, and `h_agree` is True on only **25.3%** of bars. So the reduced
observation vector is, in practice, **four correlated volatility measures and one noisy one.**

**The mechanism, stated so a miss can be diagnosed:** §7's "Build" state is defined by accumulation
— aggressive buying without price displacement — and **accumulation *is* the tape.** Removing the
flow features does not weaken the third state; it removes the thing that made it a third state
rather than a volatility level.

**What it costs, and why it is not a disaster.** If §7 dies, §9's conditions 4, 5 and 6 go with it,
and `P(B_t) > 0.60 → P(E_{t+1}) > 0.60` was going to mean "volatility is rising" — which `r_ratio`
already says more directly, with one parameter instead of nine.

### Where this is most likely wrong

1. **`spread_bp` is genuinely new and GC never had it.** It is the one observation in the reduced
   vector that is neither a volatility proxy nor Hurst, and `SPOT_FEED_CHECK.md` §1 already showed
   it is non-degenerate (1.64→2.15 bp p10–p90), which is the precondition for it carrying
   structure. **If anything rescues §7, it is spread.**
2. **The prior is one month of GC** — July 2026, 6,023 labelled windows — against five years of
   spot in a different instrument.
3. **Hurst may separate despite the estimator disagreement.** `h_agree` being False three times in
   four is a statement about the two estimators, not about whether `h_dfa_15m` alone tracks a real
   persistent/anti-persistent distinction the HMM could use.
