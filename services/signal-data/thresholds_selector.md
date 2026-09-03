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

## Part B — Stage 1, fill in before the first backtest

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

### The four blocks, scaffolded — 2026-08-26

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

```markdown
# Stage 1 — strategy 1 of 4: delta_outlier
Date: <YYYY-MM-DD>   Committed at: <time>
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 — nothing is fitted.

## The rule
A bar whose delta is <z> standard deviations above its trailing <window> goes
long at that bar's close; <z> below goes short. Trailing statistics only, reset
at each session boundary, minimum <min_bars> bars of context before any signal.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.

## The threshold — this is the commitment
- window:                                            <value>
- min_bars:                                          <value>
- z:                                                 <value>
- Median move at <N> minutes:                        <value, signed, ticks>
- Hit rate:                                          <value>%
- Versus the null:                                   beat it by <value> ticks
- Minimum sample size before I believe any of it:    <N>   (floor is 30, A4)
- Median MAE I am willing to sit through:            <value> ticks

## What result would make me say no
<Write this. Most important line in the file.>

## What I expect to see
<Your honest prediction, before you look.>
```

```markdown
# Stage 1 — strategy 2 of 4: cvd_divergence
Date: <YYYY-MM-DD>   Committed at: <time>
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 — nothing is fitted.

## The rule
Price closes at the high of its trailing <window> while CVD fell by at least
<min_slope> contracts across that same window: short. A new low that buying did
not confirm by the same margin: long. The extreme and the flow are measured
over the SAME window — two windows would be two thresholds pretending to be one.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.

## The threshold — this is the commitment
- window:                                            <value>
- min_bars:                                          <value>
- min_slope (contracts):                             <value>
- Median move at <N> minutes:                        <value, signed, ticks>
- Hit rate:                                          <value>%
- Versus the null:                                   beat it by <value> ticks
- Minimum sample size before I believe any of it:    <N>   (floor is 30, A4)
- Median MAE I am willing to sit through:            <value> ticks
- ...and it must still clear that bar at min_slope x0.8 and x1.2 (A5, and this
  strategy genuinely inherits the error)

## What result would make me say no
<Write this.>

## What I expect to see
<prediction>
```

```markdown
# Stage 1 — strategy 3 of 4: absorption_fade
Date: <YYYY-MM-DD>   Committed at: <time>
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 — nothing is fitted.

## FIRST: the two decisions above
- Fade or continuation?                              <answer>
- Time-bar ratio, or price-level absorption?         <answer>
  If price-level, this block describes a rule that does not exist yet and the
  numbers below are for the wrong thing. Settle it first.

## The rule
A bar trading at least <min_ratio> contracts per tick of range, on at least
<min_delta> contracts of one-sided flow, takes the OPPOSITE side of the delta.
The size floor is load-bearing: the ratio alone is scale-free, and without
min_delta the rule selects for the Globex-open dead zone rather than absorption.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.

## The threshold — this is the commitment
- min_ratio (contracts per tick):                    <value>
- min_delta (contracts):                             <value>
- Median move at <N> minutes:                        <value, signed, ticks>
- Hit rate:                                          <value>%
- Versus the null:                                   beat it by <value> ticks
- Minimum sample size before I believe any of it:    <N>   (floor is 30, A4)
- Median MAE I am willing to sit through:            <value> ticks
- ...and it must still clear that bar at x0.8 and x1.2 on both (A5, and this
  strategy genuinely inherits the error)

## What result would make me say no
<Write this.>

## What I expect to see
<prediction>
```

```markdown
# Stage 1 — strategy 4 of 4: footprint_stack
Date: <YYYY-MM-DD>   Committed at: <time>
Instrument: GC (GCQ6 and successors)
Data: 2026-07-01 to 2026-07-31, 23 sessions, 6,276 five-minute bars.
      Provenance and hash: "The factual fields" above.
      Walk-forward: n/a for Stage 1 — nothing is fitted.

## The rule
At least <min_stack> price levels inside the bar where buy volume is <ratio>
times the sell volume one tick below, and NO level imbalanced the other way:
long. Mirrored for short. Counts levels, not consecutive runs — consecutive
stacking is a stricter rule and would need its own block.

## What I am measuring
Realized move at 5 / 15 / 30 minutes, in ticks, plus MFE and MAE at each.

## The threshold — this is the commitment
- ratio:                                             <value>
- min_stack (levels):                                <value>
- Median move at <N> minutes:                        <value, signed, ticks>
- Hit rate:                                          <value>%
- Versus the null:                                   beat it by <value> ticks
- Minimum sample size before I believe any of it:    <N>   (floor is 30, A4)
- Median MAE I am willing to sit through:            <value> ticks

## What result would make me say no
<Write this.>

## What I expect to see
<prediction>
```

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

**Nothing may be backtested until B is filled and committed.** Nothing may be clustered until C is.
