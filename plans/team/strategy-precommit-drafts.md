# Draft predictions for §14–§17 — Claude's, unsigned, for Varad and Prathamesh to edit

**This file is not a pre-commitment and nothing in it counts as one.** `strategy-precommit.md`
§14–§17 carry 🚫 blocking gaps where the predictions go, and they stay blocking until *you* write
into them. This file exists only so that writing one is twenty minutes of disagreeing with a
derivation rather than an hour starting from a blank page.

**How to use it.** Edit a block here until it says what you actually believe, then move it into
`strategy-precommit.md` under your name and delete it from this file. When all four have moved,
delete this file. **A block moved across unedited is the failure mode this file risks** — so every
draft below exposes its arithmetic step by step, and ends with the specific places it is most
likely to be wrong.

⚠️ **None of these were derived by running the experiment.** Every number comes from results already
published in this repo — `BASE_RATES.md`, `strategy-precommit.md` §2, `SPOT_FEED_CHECK.md`,
`regimes_2026-09-02/README.md`. §0's rule, unchanged.

---

## Draft for §14 · E1 — does any cell reach `P(|ΔP₆₀| ≥ $15.00/oz) ≥ 0.60`?

### The derivation, so you can attack a step rather than the number

**Start from the one magnitude number this repo has already pooled.** `strategy-precommit.md` §2
measured `atr_bp` over 109,875 bars and committed its quartiles:

```
q25  6.79 bp      q50  9.65 bp      q75  13.87 bp
```

That is per **5-minute bar**, averaged over a 60-minute trailing window. At gold's $3,400, the
median bar's true range is `9.65e-4 × 3400 = $3.28`.

**Convert a bar range to a bar sigma.** For a driftless walk within a bar,
`E[range] ≈ 1.596 σ`, so `σ_bar ≈ 3.28 / 1.596 = $2.06`.

**Scale to sixty minutes.** Twelve bars, so `σ₆₀ = 2.06 × √12 = $7.13`.

**Read off the threshold.** `$15.00 / $7.13 = 2.10 σ`, and `P(|Z| ≥ 2.10) = 0.036`.

**Now the top bucket, which is where the filter is supposed to live.** §2's fourth bucket is `14+`
bp and holds 24.5% of bars; call its mean 18 bp. Then `σ_bar = $3.84`, `σ₆₀ = $13.29`, and
`$15.00 / $13.29 = 1.13 σ` → **`P ≈ 0.26`**. Fat tails push that up; gold is not Gaussian. Call it
0.30–0.35 in the fattest cell that still has `n ≥ 400`.

### The prediction

**No cell reaches 0.60. I expect `max p` in the range 0.25–0.40, in the highest-`atr_bp` cell, and
I will accept anything below 0.50 as consistent with this prediction. Kill condition 1 fires and
§Objective's threshold has to move.**

**And the number that matters more than the verdict:** solving for the threshold that *is*
achievable at `p = 0.60` in that top cell gives `0.524 × 13.29 ≈ $7.00/oz`. **So I predict the
honest version of §Objective's filter is roughly $7, not $15** — and that halving is not cosmetic,
because §10's target is `max(2.5D, $10.00)` capped at `$15.00`, i.e. the target range was sized
against a move the instrument does not make in an hour.

### Where this is most likely wrong

1. **The `1.596` factor.** True range includes gaps and overnight jumps, so it exceeds within-bar
   range and `σ_bar` is overestimated — which makes my `p` too *high*, strengthening the kill.
2. **√12 scaling assumes independence.** If gold's 5-minute returns are positively autocorrelated
   in the high-vol cells, `σ₆₀` is larger than √12 implies and `p` rises. M1 found a random walk,
   which argues against this — but M1 measured geometry, not autocorrelation directly.
3. **The conditioning cells.** I assumed `reach.py`'s cells are essentially `atr_bp` buckets. If
   E1 conditions on something that concentrates volatility harder — a news-proximity cell, say —
   the top cell could be fatter than the `14+` bucket I used.

---

## Draft for §15 · E2 — stage-12 survivors, and what does the killing

### The derivation

**Population.** Spot runs 24×5, so five years is roughly `1,305 weekdays × 288` five-minute bars
≈ **376,000 bars**.

**Then §9's stages, in order, with the cut I expect at each:**

```
stage 1   session windows      08:00-11:30 + 13:30-15:30 NY = 5.5h of 24   ->  ~86,000   (23%)
stage 2   news lockout         ±5 min around high-impact                   ->  ~84,000   (98%)
stage 3   R_hat_60 > $15       from E1's derivation this is the deep tail  ->   ~4,200   (5%)
          + the 1.20x median quality filter                                ->   ~3,000
stage 7   H_15m > 0.58         near-random-walk series                     ->     ~500   (17%)
stage 11  Asian extreme swept  an EVENT, ~1/day inside the windows         ->   ~1,300   (see note)
stage 12  reclaim <= 30s                                                   ->     ~400   (30%)
stages 4-6, 13, 15, 16                                                     ->      ~20
stages 8, 9, 10, 14            SKIPPED -- no tape
```

⚠️ **The accounting changes shape at stage 11 and the table must show that.** Stages 1–7 are
per-bar predicates; stage 11 is an event that happens once or twice a day. Multiplying a bar rate
by an event rate is meaningless, so **the funnel has to switch its unit at stage 11** — candidate
sweep events, then filtered by the bar-level conditions holding at the sweep. If the table does not
say where the unit changed, its later rows are not interpretable.

### The prediction

**Stage-12 survivors land in the low hundreds — I predict 200–500 over five years, and I will
accept 100–800 as consistent. That is outcome 2: testable but underpowered.**

**The single condition doing most of the killing is stage 3, `R̂₆₀ > $15`** — not the sweep, which
is where intuition points. E1's derivation is the reason: a $15 hourly move sits ~2σ out
unconditionally, so the volatility filter alone removes ~95% of bars before any structure condition
runs. **If the funnel instead dies at stage 11 or 12, my model of this strategy is wrong** and the
constraint is structural rather than volatility-based, which changes what to loosen.

### Where this is most likely wrong

1. **Stage 7's 17%.** I have no measurement of `H₁₅ₘ`'s distribution on gold. If Hurst is tightly
   centred on 0.5, `> 0.58` could cut 95% rather than 83% and stage-12 survivors fall below 100 —
   outcome 1, and the funnel needs loosening before it is tuned.
2. **The sweep rate.** "~1 per day inside the active windows" is a guess. Asian high *and* low both
   count, and a range-bound Asia produces sweeps of both in one session.
3. **Order matters and I may have it wrong.** §9 lists conditions but does not mandate evaluation
   order. Putting the cheap volatility filter first is an efficiency choice; the attrition table
   changes meaning if the order changes, so **the committed order belongs in the pre-commitment.**

---

## Draft for §16 · E3 — the per-session spread distribution

### The derivation

The arithmetic half is settled and is not a prediction: at `D = $5.00/oz` and `R = 2.5D`, EV is
positive at a 42% win rate at all three costs, and the `$2.60/oz` D floor follows from
`c / 0.25` at `c = 1.91 bp`. **What needs predicting is the empirical half.**

The one measurement in hand is `SPOT_FEED_CHECK.md` §1: **median 1.91 bp, p10/p90 1.64/2.15, max
3.77** — one hour, 2025-06-18 14:00 UTC, **the London–NY overlap**, which is the tightest hour of
the day. It is a floor for the archive, not a median of it.

### The prediction

**Per-session medians, Dukascopy:**

```
London-NY overlap   ~1.9 bp     the measured hour; the tightest
NY                  ~2.1 bp
London              ~2.2 bp
Asia                ~3.5-4.5 bp
the daily break     >8 bp, and it should be excluded rather than measured
```

**The D floor at the execution hours lands at $2.20–$3.00/oz, near the design's $2.60 estimate, and
outcome 3 fires.** §10's stop range is restated as roughly `$2.60 ≤ D ≤ $5.00`.

**Outcome 2 does not fire, and the reason is worth stating because it looks like it should.** Asia's
wider spread does *not* push the floor above $5.00 for this strategy, because **§9 sweeps a level
*formed* during Asia but executes inside the 08:00–11:30 and 13:30–15:30 NY windows.** Asian spread
governs how precisely the Asian high/low is *known*, not what it costs to trade it. If E3 shows
Asian spread wide enough to blur the swept level by more than `δ = 0.05 × ATR₁₀ₛ`, that is a real
finding — but it lands on §9's sweep definition, not on §10's stop range.

### Where this is most likely wrong

1. **Dukascopy is one broker and an ECN-style one.** Every number here is a statement about the
   archive, not about the venue. `ARCHITECTURE.md` §7's standing warning applies and no threshold
   derived here transfers to the prop firm.
2. **2025-06-18 is one day.** Spread widens structurally around FOMC and CPI, and §12's lockout is
   ±5 minutes while the widening lasts far longer.
3. **The daily-break exclusion is an assumption.** If the break's quotes are not excluded, a pooled
   median is meaningless and the per-session table hides it.

---

## Draft for §17 · E4 — do three states survive on five observations?

### The derivation, and it is the strongest prior of the four

`analysis/regimes_2026-09-02/README.md` already fit `k=3` on this instrument. **Look at what
actually separated the states:**

| regime | n | pct | realized_vol (med) | cvd_slope (med) | cvd_persistence (med) | price_efficiency (med) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 930 | 15.4% | 0.000357 | **+27.566** | 0.612 | 0.540 |
| 1 | 1,296 | 21.5% | 0.000316 | **−26.668** | 0.613 | 0.539 |
| 2 | 3,797 | 63.0% | 0.000275 | −0.199 | 0.206 | 0.341 |

**Regimes 0 and 1 are identical on every feature except the sign of `cvd_slope`.** Their
`realized_vol` differs by 13%, their `cvd_persistence` by 0.001, their `price_efficiency` by 0.001.
`realized_vol` spans 0.000275–0.000357 across all three states — it is doing almost no separating
work. **Two of the four fitted features were CVD, and the states resolved on CVD.**

E4 removes CVD. What remains — `r_hat_60_bp`, `h_*`, `spread_bp`, range-compression, sigma-ratio —
is four volatility proxies and one Hurst estimate, and the four are collinear by construction.

### The prediction

**Three states will not separate into Chop / Build / Expansion. `k=3` will fit and will produce an
ordered volatility ladder — low, mid, high — and `k=2` will explain nearly as much. I expect
outcome 3, and I expect §7 to be dropped.**

The mechanism, stated so a miss can be diagnosed: **§7's "Build" state is defined by accumulation —
aggressive buying without price displacement — and accumulation *is* the tape.** `regimes_2026-09-02`
is the evidence that on this instrument the flow features are what carried the state separation.
Removing them does not weaken the third state; it removes the thing that made it a third state
rather than a volatility level.

**What that costs, and why it is not a disaster.** If §7 dies, §9's conditions 4, 5 and 6 go with
it, and `P(B_t) > 0.60 → P(E_{t+1}) > 0.60` was going to mean "volatility is rising" — which
`r_ratio` already says more directly and with one parameter instead of nine.

### Where this is most likely wrong

1. **`spread_bp` is genuinely new and GC never had it.** It is the one observation in the reduced
   vector that is not a volatility proxy and not available in the prior. If spread carries
   independent structure, it could do the separating work CVD did — and `SPOT_FEED_CHECK.md` §1
   already showed it is non-degenerate (1.64→2.15 bp p10–p90), which is the precondition.
2. **The prior is one month of GC**, July 2026, 6,023 labelled windows. Five years of spot is a
   different sample in a different instrument.
3. **Hurst may be more orthogonal than I credit.** If `h_dfa_15m` genuinely separates persistent
   from anti-persistent stretches independently of volatility, a real third state could survive on
   it alone.

---

## One thing that falls out of drafting all four together

**Three of the four drafts predict their kill condition fires.** E1 says the $15 threshold is
roughly double what the instrument supports; E4 says §7 does not survive losing the tape; E2 says
the sample is testable but underpowered. Only E3 predicts a clean pass.

**If you broadly agree with these, Day 2's shape changes before Day 2 starts** — Task 12 (the HMM)
becomes a half-hour confirmation rather than a build, and §Objective's threshold wants re-deriving
on Friday rather than being carried into Saturday's feature work at a value E1 is about to reject.

**If you disagree with these, that disagreement is worth more than the drafts are**, and it should
go into `strategy-precommit.md` in your words with your reasoning. That is the artifact that
matters; this file is scaffolding.
