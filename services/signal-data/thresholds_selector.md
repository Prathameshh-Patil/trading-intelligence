# The pre-written threshold — GC strategy selector

**Due: before the first backtest runs. Not before you present it. Committed to git.**

Design: [`docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md`](../../docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md) §6.1.
Sibling: [`plans/team/varad/thresholds.md`](../../plans/team/varad/thresholds.md) — same mechanism,
same rules, different subject. Read that one first; this file assumes it.

---

## Why this file is stricter than its sibling

The Week 1 file guards one rule. This guards **a selector choosing between four strategies across
two or three regimes**, and the design says the quiet part out loud: that is **four times the
researcher degrees of freedom of a single rule**, times the regimes, times the horizons. Every
one of those cells is a chance to tell yourself a story about a threshold, and it will be a good
story, told by someone with every reason to believe it.

The failure mode is not laziness. After you have seen a distribution, every threshold you pick is
partly a memory of what you saw. **The only defence is a git commit with a timestamp earlier than
the results.**

There is a second failure mode here that the Week 1 file does not have. A selector can look good
for a reason that has nothing to do with selection: if one strategy is simply the best, a selector
that picks it most of the time inherits its numbers and reads as skill. **Beating "always use the
single best strategy" is table stakes, not a result.** §6.3's second null is what separates them,
and it is the one this whole file exists to protect.

---

## Part A — already committed by the design, binding, nothing to fill in

These are not choices left open. They are commitments the design already made, restated here so
that the file you commit is the whole commitment and not a pointer to one.

| # | Commitment | Where |
| :--- | :--- | :--- |
| A1 | **Walk-forward, never in-sample.** Regimes fitted on the first half, selection tested on the second. With ~22 sessions that is ~11 and ~11 | §6.4 |
| A2 | **Regime definitions are fitted, labelled and committed BEFORE anyone looks at per-strategy performance inside them** | §6.2 |
| A3 | **No clustering input derived from forward returns.** State only. If one is, the design leaks and every number after it is fiction | §2 |
| A4 | **N next to every number.** Any cell under **30** signals is reported and **not acted on**. `backtest.py` sets `thin=True` there, so this one is mechanical rather than remembered | §6.5 |
| A5 | **Every headline result is re-run with delta thresholds moved ±20%.** An edge that does not survive its own known error bar is not an edge | §6.6, §4 |
| A6 | **Pre-filter and post-filter numbers are reported side by side**, always, so it is visible whether `decision_filter.py` helped or merely shrank the sample until the numbers looked better | §3 |
| A7 | **Units are ticks, with $/contract alongside.** GC tick = 0.10 = $10.00. Never pips | §4 |
| A8 | **Entries fill at the close of the bar that signalled them.** A strategy reading anything from the next bar is lookahead, not a strategy | `backtest.py` |

**A5 is the one that will hurt.** Session-total delta is method-dependent at **~15–20%** — the side
field gives +1,842 for 2026-07-16 where the quote rule gives +2,216. A rule that fires at
"delta > 200" is a rule that fires somewhere between roughly 170 and 240 depending on which
classification you believe. That error bar is inherited, not introduced, and it does not go away by
not mentioning it.

---

## Part B — Stage 1 · **FILLED AND COMMITTED 2026-09-04**

**One block per candidate strategy. Copy it 3–4 times.** Nothing below is written by Claude; §9 Q1
of the design says the candidates are authored by the person who trades them, and a threshold
picked by an assistant is not a commitment by the person with the bias. That is the whole
mechanism.

```markdown
# Stage 1 — strategy <n> of <N>, threshold committed before results
Date: <YYYY-MM-DD>   Committed at: <time>
Instrument: GC (GCQ6 and successors)
Data: <start> to <end>, <n> sessions. Walk-forward: fit <range>, test <range>.

## The rule
<entry condition and exit condition, stated precisely enough that someone else
could implement it from this paragraph alone. If it needs a threshold, the
number goes here, not "an outlier" or "elevated delta".>

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.

## The threshold — this is the commitment
- Median move at <N> minutes:                        <value, with sign, in ticks>
- Hit rate:                                          <value>%
- Versus the null (random entry, matched count,
  matched holding period, matched side mix):         beat it by <value> ticks
- Minimum sample size before I believe any of it:     <N> signals   (floor is 30, A4)
- Median MAE I am willing to sit through:            <value> ticks

## What result would make me say no
<Write this. It is the most important line in the file. If you cannot state a
result that would make you abandon this strategy, you are not testing it.>

## What I expect to see
<Your honest prediction, now, before you look. Being wrong here is useful
information about your own calibration and costs nothing to record.>
```

**Stage 1 is a kill gate.** If no strategy clears its own committed bar standalone, **stop** —
there is nothing to select between and Stage 2 is moot. That outcome is worth days, not weeks, and
finding it out cheaply is the entire reason Stage 1 goes first.

---

### The four blocks, scaffolded — 2026-08-26 *(four then; three of them filled 2026-09-04, `absorption_fade` dropped — see below)*

`strategies.py` landed 26 Aug, so the candidates now exist as code and the rules below are
transcribed from their docstrings. **Everything factual is filled in. Every number and every
judgment is blank, and stays blank until Varad writes it.** The `<...>` fields are the commitment;
nothing else here is.

Two things to settle **before** any number, because both change what is being thresholded:

1. **Is `absorption_fade` a fade or a continuation?** The code assumes the aggressor was trapped
   and the resting side won. The same bar reads as continuation if the aggressor was early. One
   sign change, but it is a decision.
2. **Should absorption be measured at the price level rather than over a time bar?** Absorption is
   classically size stacking at one price and failing to break it, and `compute_delta_cvd.py`'s
   `footprint()` already aggregates by price level. `|delta| / bar range` is a proxy, and at a
   median bar range of **15 ticks** it is a loose one. This one may delete the rule rather than
   tune it. *(Measured 3 Sep: 15 ticks is the **minute**-bar figure. The 5-minute median is
   **38 ticks** — see "Scale" below, which makes the proxy looser here, not tighter.)*

**Both settled 2026-09-04, and decision 2 went the way this section warned it might.** Absorption is
**dropped from Week 1** rather than re-specified at the price level — three well-posed candidates
against a thin month beat four with one mis-specified. Decision 1 is **recorded, not taken**: when
the rule returns it returns as *two* blocks, fade and continuation, each measured rather than one of
them assumed. See "`absorption_fade` — deferred out of Week 1" below for what that costs at D3 and at
the gate.

**Which candidates actually inherit the ±15–20% delta error** (measured 26 Aug, asserted in
`tests/test_stage1.py`) — this decides how much A5's output means for each:

| Strategy | Thresholds it needs | Inherits the delta error? |
| :--- | :--- | :--- |
| `delta_outlier` | `window`, `min_bars`, `z` | **No.** A z-score divides by its own σ, so a uniform delta rescale cancels |
| `cvd_divergence` | `window`, `min_bars`, `min_slope` | **Yes** — `min_slope` is in contracts |
| `absorption_fade` | `min_ratio`, `min_delta` | **Yes** — both are in contracts |
| `footprint_stack` | `ratio`, `min_stack` | **No.** A volume ratio scales on both sides |

---

### The factual fields, filled — 2026-09-03

**Every number in this section is provenance or scale.** Not one of them is a threshold, a hit
rate, a realized move, or a delta statistic — those stay blank, because seeing them before you
commit is the exact failure `plans/team/varad/thresholds.md` exists to prevent. What is filled is
only what you need in order to *state* a commitment at all: which bytes it is a commitment about,
how many independent observations they can carry, and how big a tick is next to a bar.

#### Data — identical for all four blocks

| | |
| :--- | :--- |
| Month | **2026-07-01 → 2026-07-31**, **23 sessions** |
| Parquet | `data/2026-07/gc_trades.parquet` — 1,616,772 trades, `sha256` `45947e88eb20f414…`, **re-verified 3 Sep** against `analysis/gc_data_manifest.md` |
| Contract | `GCQ6·GCZ6` — **July is a roll month**, so it carries the roll-month `'N'` rate, not the quiet-month one |
| `'N'` aggressor | **3.89% of the month**, against 2.34% in the S1 fixture session. Roll months average 3.75%, single-contract months 1.92%. Delta is least complete exactly here |
| Bars | **6,276** five-minute bars (`analysis/regimes_2026-09-02/regime_labels_window_5min_k3.csv`, 6,277 lines with header) |
| Regime labels | `analysis/regimes_2026-09-02/` — the 4-feature, straddle-fixed run. **6,023 of 6,276 bars labelled**; the 253 unlabelled are session-opening bars with no trailing window yet |
| Walk-forward | **n/a for Stage 1** — nothing is fitted, so all 23 sessions are one sample. The split exists for Stage 2 and Week 1 D5: **≤ 2026-07-19 → 13 sessions / 3,373 labelled bars; > 2026-07-19 → 10 sessions / 2,650**. `dcbde04` cuts it on the session, not the ET calendar date |
| Tick | 0.10 = **$10.00 per contract**. Units are ticks with $/contract alongside, never pips (A7) |

⚠️ **Both regime READMEs still print `--parquet data/gc_trades.parquet`.** That path has not existed
since the 28 Aug 19-month reorg moved every month under `data/<YYYY-MM>/`. The command as written
does not run; the file it means is the one in the table above, and its hash matches. Left uncorrected
here on purpose — what the 2 Sep run actually read is Prathamesh's to confirm, not mine to assert.

#### Scale — and it changes whether Day 4 is well-posed

**The median 5-minute bar range is 38 ticks** (p25 27, p75 55, mean 45.4), measured over all 6,276
bars of the month. This file's **15 ticks is a *minute*-bar figure**, and §"the two decisions"
above reasons about `absorption_fade` with it — at 5-minute bars the proxy is looser than that note
assumes, not tighter.

Against 38 ticks, `planfortoday.md`'s pair sits like this:

| | ticks | vs median 5-min bar |
| :--- | ---: | ---: |
| Stop | 20 | **0.53×** — half a bar |
| Target | 70 | 1.8× |

**A stop at half the median bar is inside the bar it is measured on.** Target and stop will both be
touched within a single bar often enough that OHLC cannot order them, which is exactly the intra-bar
ambiguity Week 1 D4 flags. This settles the "is Day 4 even well-posed" question D1 was told to ask,
and the answer is **not at bar resolution** — D4's tick-resolution run on the fixture session is
mandatory, and the bar-vs-tick gap it measures is a real error bar, not a formality.

*(Note for the sample-size line below: the fixture session **2026-07-16** — the free absorption test
case — falls in the **training** half of the 19 Jul split.)*

#### What a sample size has to be to prove anything

From [`week-01.md`](../../plans/team/week-01.md) §2, against a **random-walk** null of 22.22%
(`P(hit +70 before −20) = 20/(70+20)`, which is also break-even at 3.5:1 — necessarily the same
number). **The null you commit against is the *measured* one from `backtest.random_entries`, not
this**; the table is here so the floor you write is not wishful.

| Signals | 1 s.e. | Smallest hit rate provable at 2σ |
| ---: | ---: | ---: |
| 50 | 5.88 pp | **34.0%** |
| 100 | 4.16 pp | **30.5%** |
| 150 | 3.39 pp | **29.0%** |
| 250 | 2.63 pp | 27.5% |
| 500 | 1.86 pp | 25.9% |
| 900 | 1.39 pp | 25.0% |

A4's floor of 30 is the *reporting* floor. **At 50–150 signals — what `planfortoday.md` targets —
nothing below ~29% is provable**, so a "minimum sample size before I believe any of it" of 30 and a
hit-rate commitment of 26% are not compatible commitments. Pick both lines together.

---

### FILLED — 2026-09-04, 00:38 IST, before anything was run

**Every number below was chosen by Varad on 2026-09-04 and transcribed, not authored.** The
selections were made against the arithmetic in "The factual fields" above — the separable-edge
floor, the power table, the 38-tick bar range — and each was put as an explicit choice with its
consequence stated. Claude wrote no threshold, no kill criterion and no prediction of its own; where
a field required a belief rather than a number, it was asked for. **The git timestamp on this commit
is the mechanism, and nothing ran before it.**

Two structural decisions came first, because both change what is being thresholded:

- **`absorption_fade` is out for Week 1.** Decision 2 above resolved as *drop*, not *tune* — exactly
  the outcome that section said was possible. Three candidates, not four.
- **When it returns it returns as two blocks, fade *and* continuation**, each with its own
  commitment and its own kill line, rather than one signed guess. Decision 1 is recorded, not taken.

**What every block shares** — stated once here rather than repeated three times:

| | commitment |
| :--- | :--- |
| Horizon | **5 minutes.** 15 and 30 descriptive only. ⚠️ **Contingent on gate item 3**, which is drafted and unvoted — `current.md` flags it "not Varad's alone to take, it changes what Part B's thresholds are written against." **If the room picks another horizon, these blocks are re-committed before anything runs, not reinterpreted after.** |
| Derived on | **The training half only** — sessions ≤ 2026-07-19: 13 sessions, 3,373 labelled bars. The held-out 10 sessions / 2,650 bars are not looked at |
| Median move @ 5m | **≥ +14 ticks** ($140), in the signal's favour. Chosen against the separable floor of **13.68 ticks at N=100** — i.e. deliberately set so the commitment is provable at the sample size floored below, and knowingly far larger than a real order-flow edge (1–3 ticks) is expected to be |
| Hit rate | **The gate formula, not a flat number:** held-out `hit_70_rate` beats the **measured** random-entry null `p₀` by at least `2 × sqrt(p₀(1−p₀)/N)`, with **N ≥ 100**. Identical to `week-01.md` §2's pre-written threshold, so Part B and the D5 gate cannot disagree. `backtest.random_entries` measures `p₀`; a second null must not be written |
| Minimum N | **100.** Below it the result is **inconclusive** — reported, not acted on. A4's floor of 30 is the reporting floor and is not this |
| Median MAE tolerated | **20 ticks** — equal to the hard stop, so a rule whose median MAE reaches it is stopping out at the median. Note this is **0.53× a median 5-minute bar**, which is why D4 must measure it at tick resolution before the number means anything |
| Kill line | **Fails the gate formula on held-out data → the strategy is dead.** Not "promising but underpowered", not "worth another month". The same line D5 already measures, so there is no second standard to argue about |

**The prediction, recorded before any of it runs:** *none of the three clears its bar, and
`delta_outlier` comes in **under 100 signals** because entries cluster into a handful of volatile
sessions.* Both were chosen deliberately over the more optimistic options offered.

**Read what that means honestly:** by his own prediction the study is underpowered *before* the hit
rate matters — N fails first, so the outcome is `inconclusive` and the kill line is never reached.
That is §6's recorded prediction, Day 5's power arithmetic and this pre-registration all agreeing in
advance. **It is a real result and the cheapest possible one** — the response written down for it is
already on record: buy months, do not add modelling.

```markdown
# Stage 1 — strategy 1 of 3: delta_outlier
Date: 2026-09-04   Committed at: 00:38 IST
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Derived on the TRAINING half only: <= 2026-07-19, 13 sessions, 3,373 labelled bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 -- nothing is fitted.

## The rule
A bar whose delta is 2.0 standard deviations above its trailing 120min window
goes long at that bar's close; 2.0 below goes short. Trailing statistics only,
reset at each session boundary, minimum 12 bars of context before any signal.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.
The 5-minute figure is the commitment; 15 and 30 are descriptive.

## The threshold -- this is the commitment
- window:                                            "120min"   (24 x 5-min bars)
- min_bars:                                          12
- z:                                                 2.0
- Median move at 5 minutes:                          >= +14 ticks ($140)
- Hit rate:                                          beats the measured null p0 by
                                                     >= 2*sqrt(p0*(1-p0)/N)
- Versus the null:                                   the margin above IS the bar;
                                                     no separate tick figure
- Minimum sample size before I believe any of it:    100          (floor is 30, A4)
- Median MAE I am willing to sit through:            20 ticks
- A5 note: this rule does NOT inherit the +/-15-20% delta error. A z-score
  divides by its own sigma, so a uniform delta rescale cancels. The perturbation
  is still run; it is expected to move nothing, and that is the check.

## What result would make me say no
Held-out hit_70_rate fails to clear the measured null by 2 standard errors at
N >= 100. Then it is dead -- not "promising but underpowered", not "worth
another month". Below N = 100 the result is inconclusive and is reported, not
acted on, and inconclusive is not a soft no that gets argued into a yes.

## What I expect to see
It does not clear. I expect N under 100 on the training half despite the
Gaussian estimate of ~150, because entries will cluster into a handful of
volatile sessions and the raw count will overstate the independent
observations. If that is what happens, N fails before the hit rate is even
reached, and the honest response is more months, not more modelling.
```

```markdown
# Stage 1 — strategy 2 of 3: cvd_divergence
Date: 2026-09-04   Committed at: 00:38 IST
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Derived on the TRAINING half only: <= 2026-07-19, 13 sessions, 3,373 labelled bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 -- nothing is fitted.

## The rule
Price closes at the high of its trailing 60min window while CVD fell by at
least 200 contracts across that same window: short. A new low that buying did
not confirm by the same margin: long. The extreme and the flow are measured
over the SAME window -- two windows would be two thresholds pretending to be
one. Minimum 6 bars of context before any signal.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.
The 5-minute figure is the commitment; 15 and 30 are descriptive.

## The threshold -- this is the commitment
- window:                                            "60min"    (12 x 5-min bars)
- min_bars:                                          6
- min_slope (contracts):                             200
- Median move at 5 minutes:                          >= +14 ticks ($140)
- Hit rate:                                          beats the measured null p0 by
                                                     >= 2*sqrt(p0*(1-p0)/N)
- Versus the null:                                   the margin above IS the bar
- Minimum sample size before I believe any of it:    100          (floor is 30, A4)
- Median MAE I am willing to sit through:            20 ticks
- ...and it must still clear that bar at min_slope 160 and 240 (A5 +/-20%).
  This rule genuinely inherits the error: min_slope is denominated in contracts,
  and session delta is method-dependent at ~15-20%. If the edge dies inside its
  own known error bar, it was never an edge.

## What result would make me say no
Held-out hit_70_rate fails to clear the measured null by 2 standard errors at
N >= 100 -- or it clears at min_slope 200 and fails at 160 or 240. Either one
kills it. The second is not a caveat to note in the write-up; it is a kill.

## What I expect to see
It does not clear. This is the one with a real mechanism story behind it, which
is exactly why I do not trust my own read of it -- a story is what makes a thin
result look like an edge. I expect the A5 perturbation to be where it dies if
the raw number looks good.
```

```markdown
# Stage 1 — strategy 3 of 3: footprint_stack
Date: 2026-09-04   Committed at: 00:38 IST
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Derived on the TRAINING half only: <= 2026-07-19, 13 sessions, 3,373 labelled bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 -- nothing is fitted.

## The rule
At least 3 price levels inside the bar where buy volume is 3.0 times the sell
volume one tick below, and NO level imbalanced the other way: long. Mirrored
for short. Counts levels, not consecutive runs -- consecutive stacking is a
stricter rule and would need its own block. Reads TICKS, not bars: price levels
within a bar do not survive OHLC.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.
The 5-minute figure is the commitment; 15 and 30 are descriptive.

## The threshold -- this is the commitment
- ratio:                                             3.0
- min_stack (levels):                                3
- Median move at 5 minutes:                          >= +14 ticks ($140)
- Hit rate:                                          beats the measured null p0 by
                                                     >= 2*sqrt(p0*(1-p0)/N)
- Versus the null:                                   the margin above IS the bar
- Minimum sample size before I believe any of it:    100          (floor is 30, A4)
- Median MAE I am willing to sit through:            20 ticks
- A5 note: this rule does NOT inherit the +/-15-20% delta error. A volume ratio
  scales on both sides. Run the perturbation anyway; expect it to move nothing.

## What result would make me say no
Held-out hit_70_rate fails to clear the measured null by 2 standard errors at
N >= 100. Dead, on the same terms as the other two.

## What I expect to see
It does not clear, and I expect this one to be the thinnest of the three -- a
bar with three levels stacked 3:1 and nothing imbalanced against it is rare.
If N comes in under 30 this is reported and not acted on under A4, which is a
different outcome from failing, and I will not blur the two.
```

### `absorption_fade` — deferred out of Week 1, 2026-09-04

**Not a failed candidate and not an unfilled block. A decision.** Decision 2 above asked whether
absorption should be measured at the price level rather than as a time-bar ratio, and warned the
answer "may delete the rule rather than tune it." It did.

- **The proxy is looser than the file assumed.** `|delta| / bar range` was reasoned about against a
  15-tick median bar. That is the *minute*-bar figure; the 5-minute median is **38 ticks**, so the
  denominator is 2.5× wider than the note that endorsed the proxy had in mind.
- **The classical form needs code that does not exist.** `compute_delta_cvd.py`'s `footprint()`
  aggregates by price level already, but no rule reads it that way, and writing one before a first
  backtest is new machinery on the critical path in a week that has none to spare.
- **Three well-posed candidates beat four where one is mis-specified**, against a month this thin.

**When it returns, it returns as two blocks** — fade *and* continuation, each with its own threshold,
kill line and prediction. The code currently hard-codes the fade reading in a docstring; the same bar
is a continuation if the aggressor was early, and that is a question to be *measured*, not settled by
whoever wrote the function first.

⚠️ **This has a consequence at D3 and one at the gate, and neither is closed here:**

- `week-01.md` D3's signal engine is a **3-of-4 checker** whose condition A is absorption. With the
  rule out, A is stubbed `return False` — which D3 already sanctions ("if a condition is genuinely
  hard — absorption is the likely one — stub it, commit that, and move on") — and the combiner is
  effectively 3-of-3. **That is a stricter gate than designed**, not a looser one, and it should be
  reported as such rather than quietly relabelled.
- **The Week 1 gate line "the outlier detector flags the 2026-07-16 08:00 ET absorption hour" still
  stands.** That hour — delta **+1,083** against a **47.7-point drop** — is textbook absorption, and
  the rule named for it is now out. It has to be caught by `delta_outlier` instead, which is a real
  test rather than a formality: **if nothing flags that hour, Stage 1 does not work**, and dropping
  `absorption_fade` does not dissolve that line.

---

## Part C — Stage 2, fill in before the clustering is fitted

Not before it is *interpreted*. Before it is **fitted**. A2 is only worth something if the labels
exist before the performance table does.

```markdown
# Stage 2 — regime selection, threshold committed before results
Date: <YYYY-MM-DD>   Committed at: <time>

## Regimes
Count: <2 or 3 — the design caps this at 3 and the cap is the point>
Features: <from §2's table, state only. list them.>
Unit of labelling: <session-level or rolling-window — decide it, do not fall
  into it. A session gives ~22 very thin labels; a window gives more labels that
  are autocorrelated, which inflates apparent sample size. This choice changes
  how much the walk-forward split can support.>
Bar size for the features: <1 / 5 / 15 min — cheap to test, so test>

## The threshold — this is the commitment
- Learned regime selection beats RANDOM regime assignment
  with the same regime proportions by:               <value> ticks expectancy
- ...and beats ALWAYS USING THE SINGLE BEST STRATEGY by: <value> ticks expectancy
- Minimum signals per regime-strategy cell:           <N>   (floor is 30, A4)
- Number of cells I require above that floor:         <N> of <total>

## What result would make me say no
<Again, and it is a different sentence than Stage 1's. The likeliest honest
outcome is that the two nulls above are indistinguishable from the selector.
Write what that looks like numerically, now, so you cannot reinterpret it as
"promising but underpowered" in three weeks.>

## What I expect to see
<prediction>
```

---

## The prediction that is already on record

The design wrote this down before the work, precisely so it could not be quietly reinterpreted
afterwards:

> With ~22 sessions split walk-forward into ~11 and ~11, **the most likely honest result is
> _inconclusive_** — too few signals per regime-strategy cell to distinguish skill from noise.

**That is a real result, not a failure.** And the cheapest fix is more data, not more modelling:
one GC month cost **$2.52** and six months is roughly **$15** at Databento's measured rate, which
buys more for Stage 2 than any modelling choice available. If the answer comes back inconclusive,
the response is to buy months, not to add a feature to the clustering.

Note the interaction with §5: the feed vendor may change what a month costs, and quantfeed is
entirely unconfirmed.

---

## Part D — the decision filter, commit before the first FILTERED backtest

`features/regime_filter.py`, Week 1 D1. Four gates, ANDed, deciding which bars are eligible to signal
on at all. Everything downstream is measured on the sample this file defines, which is why it needs
the same discipline as Part B and did not have it.

### ⚠️ Read this before treating it as a pre-commitment

**It is not one, and it must not be presented as one.** Part B's mechanism is a git timestamp earlier
than any result. These five numbers were arrived at on 2026-09-04 **while looking at the month's
distributions**, some of them off a pass-rate sweep. No timestamp can undo that.

What this block can honestly commit to is narrower, and still worth having:

1. **The values are frozen here, before any *filtered backtest*** — before a signal, a return, an MFE
   or a hit rate has been computed through them. That boundary has not been crossed yet.
2. **The held-out half has not been looked at through this filter.** Every number below was derived on
   the training half (≤ 2026-07-19, 13 sessions) or on scale statistics that use no outcomes.
3. **The provenance of each number is stated exactly**, including which ones were first read off a
   sweep and only later given an argument. That distinction is the point of the table.

### The five numbers, and where each came from

| gate | value | provenance | independent of the pass rate? |
| :--- | ---: | :--- | :--- |
| `kappa_min` | **0.75** | Chosen by Varad from options. **All three regimes clear it (0.842 / 0.833 / 0.798), so on this labelling the gate filters nothing** — that is the finding, not a failure | Yes — and it selects nothing, so it cannot be tuning |
| `persistence_min` | **0.40** | Midpoint of the two populations the labelling found: chop at **0.206**, flow at **0.612 / 0.613**, midpoint **0.409** | **Yes** — derived from the population separation. The pass-rate sweep was visible at the time and is not what produced the number |
| `atr_min` | **40** | The floor at which the 70-tick target is reachable in D4's 6-bar window: median best one-way move crosses 70 at **ATR 39.4** (training half), 40.1 (full month) | **Partly. Say it plainly: 40 was first read off a pass-rate sweep on 2026-09-04, and the derivation came afterwards.** It is a genuine derivation that independently lands on the same number, but it is post-hoc and should be read that way |
| `ema_span` | **15** | `week-01.md` D1's specification, never tuned | Yes |
| `edge_minutes` | **5** | `week-01.md` D1's specification, never tuned | Yes |

Windows, which are shape rather than threshold: `persistence_window` `"60min"` / `min_bars` 6 (matching
`cvd_divergence`'s committed window); `atr_window` `"70min"` / `min_bars` 14 (ATR(14) at 5-minute bars).

**What was retired, and why it matters here:** D1 specified `survival >= 0.92`. Reviewed against the
plot on 2026-09-04, raw survival turned out to select on *prevalence* — a regime holding 63% of bars
scores 0.63 by shuffling alone — so the gate kept the one regime with no directional flow. See
[`analysis/regimes_2026-09-02/README.md`](analysis/regimes_2026-09-02/README.md). **A threshold that
looked principled for a week was measuring the wrong quantity**, which is the argument for this block
existing at all.

### The measured pass rate, on the training half

**1,043 of 6,276 bars — 16.6%** of the month at these values, inside D1's 15–25% target band. Gate by
gate, in isolation: `kappa` 100% of labelled bars, `cvd_persistence >= 0.40` ~45%, `atr >= 40` ~55%,
`EMA(15)` 67.8%, session interior 99.3%.

### The commitment — Varad's, and blank until he writes it

```markdown
# Decision filter — thresholds frozen before the first filtered backtest
Date: <YYYY-MM-DD>   Committed at: <time>
Filter: features/regime_filter.py, five values as tabled above

## Do I ratify these five numbers as they stand?
<yes / no per gate. A "no" here is cheaper than a "no" after Layer 4 has run.
The one most worth arguing with is atr_min, because its derivation is post-hoc.>

## What I expect the HELD-OUT pass rate to be
<value>%   (training half is 16.6%. A held-out rate far from it means the
filter is fitted to the training half's volatility, not to the market.)

## What result would make me say the filter is not helping
<Write this. A6 already requires pre-filter and post-filter numbers side by
side, so the comparison will exist whether or not it is committed to. The
question is what gap, in which direction, retires the filter -- and note that
a filter which merely shrinks the sample until the numbers look better is the
specific failure A6 exists to catch.>

## What I expect the filter to do to hit_70_rate
<Your honest prediction, before Layer 4 runs. If filtered and unfiltered come
back the same, the filter cost 83% of the sample for nothing, and Stage 1 is
underpowered enough already -- that outcome should be written down now so it
cannot be reinterpreted as "at least it did not hurt".>
```

**Nothing may be backtested THROUGH this filter until the block above is filled**, on the same terms
as §6.1 for Part B. Running the strategies unfiltered is not blocked by it.

---

## The rules that make this mean something

**Commit before you run, not before you present.** The git timestamp is the whole mechanism and it
is worth nothing if the file appears the same evening as the results.

**One threshold, not a range.** "Somewhere around 8–20 ticks" is not a commitment. It is a hedge
that will retroactively accommodate whatever you find.

**Both nulls, and the second one is the one that matters.** Random entry catches a strategy that is
just measuring the month. Random regime assignment catches a selector that is just fitting noise —
and that is the failure this project is actually exposed to.

**Report the distribution you committed to, not the best-looking cut of it.** If you find yourself
wanting to move the horizon from 15 minutes to 22 because 22 looks much better, that is the exact
moment this file is for. 22 may well be right. It is not right *this run*; it is a hypothesis with
its own committed threshold, next time.

**A cell under 30 is reported and not acted on.** Twelve signals that look wonderful are twelve
signals. `backtest.py` flags it; the flag only works if you do not argue with it.

---

## Status

**Written 2026-08-25 (night). Part A is filled and binding. Parts B and C carry no numbers, and
that is on purpose** — they are the trader's commitments, not the assistant's, in the same way
`decision_filter.py` is authored by the trader and not written by Claude (§3). An assistant filling
in a number here would produce a file that looks like the mechanism working while doing none of
what the mechanism is for.

**Updated 2026-08-26: Part B is scaffolded, not filled.** `strategies.py` landed, so the four rules
are transcribed from their docstrings, each block names exactly which thresholds its function
requires, and the table records which two candidates actually inherit the ±15–20% delta error.
Asked to fill Part B in, Claude declined the numbers and wrote the scaffold instead. **Every
`<...>` field is still empty and still Varad's.**

**Updated 2026-09-03: Part B's factual fields are filled; every commitment field is still empty.**
The month, its hash, the session and bar counts, the label coverage, the walk-forward split, the
tick value and the 5-minute bar-range scale are now written down, and the sample-size table from
`week-01.md` §2 sits next to the line it constrains. **No threshold, hit rate, realized move, delta
statistic, kill criterion or prediction was written** — the same line two prior sessions drew, drawn
again: those are commitments by the person with the bias, and provenance is not.

One measured number changed a plan assumption rather than merely recording it: **the median 5-minute
bar range is 38 ticks, not the 15 this file carried from minute bars.** A 20-tick stop is half a
median bar, so D4's tick-resolution check is load-bearing rather than a formality.

**Updated 2026-09-04: Part B is FILLED and committed. Part C is not.** Three blocks — `delta_outlier`,
`cvd_divergence`, `footprint_stack` — carry parameters, a shared horizon and sample floor, a median-move
bar, a hit-rate rule, an MAE tolerance, a kill line and a prediction. **Every one of those was chosen by
Varad on 2026-09-04 and transcribed**; each was put as an explicit choice with its consequence stated
(the separable-edge floor, the power table, the 38-tick bar range), and where a field needed a belief
rather than a number it was asked for rather than invented. `absorption_fade` was **dropped from Week 1
by decision**, not left blank.

**The pre-registered expectation is failure by underpowering:** none of the three clears, and
`delta_outlier` lands under N=100 on clustering. So `N` fails before the hit rate is reached and the
outcome is `inconclusive` — the same thing §6 predicted in writing, Day 5 confirmed with arithmetic,
and this file now records *before* the run rather than after. The response to that outcome is already
written down: **buy months, do not add modelling.**

**Added 2026-09-04: Part D, the decision filter.** `regime_filter.py`'s five thresholds now have their
provenance written down, including which one was read off a pass-rate sweep before it was derived
(`atr_min`). **It is explicitly not a pre-commitment** — the numbers were arrived at while looking at
the month, and no timestamp undoes that. What it freezes is the values before any *filtered* backtest,
and it records that the held-out half has not been looked at through the filter. Its four commitment
fields are blank and Varad's.

**Backtesting the strategies unfiltered is unblocked. Backtesting THROUGH the filter needs Part D
filled. Clustering needs Part C, which is still empty.**
