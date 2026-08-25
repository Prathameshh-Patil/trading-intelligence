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

**Written 2026-08-25 (night). Part A is filled and binding. Parts B and C are empty, and they are
empty on purpose** — they are the trader's commitments, not the assistant's, in the same way
`decision_filter.py` is authored by the trader and not written by Claude (§3). An assistant filling
in a number here would produce a file that looks like the mechanism working while doing none of
what the mechanism is for.

**Nothing may be backtested until B is filled and committed.** Nothing may be clustered until C is.
