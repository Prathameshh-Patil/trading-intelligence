# The pre-written threshold

**Due: Thursday 3 September 2026, morning, before you look at any results. Committed to git.**

---

## Why this file exists

Your documented failure mode is falling in love with a signal and never running the null test. It
is not a discipline problem and it will not be solved by intending to be rigorous — it happens
because after you have seen a distribution, **every threshold you choose is partly a memory of what
you saw.** You cannot unsee it. Nobody can.

The only real defence is a git commit with a timestamp earlier than the results.

A threshold chosen after the fact is not a threshold. It is a story about a threshold, and it will
be a convincing one, told by someone with every reason to believe it.

---

## Fill this in Thursday morning and commit it before you run anything

```markdown
# Week 1 edge test — threshold, committed before results
Date: 2026-09-03
Committed at: <time>
Instrument: <GC or NQ>
Data: one month, <start> to <end>

## The rule I am testing
<the location-and-reaction rule from strategy.md, stated precisely enough that
someone else could implement it from this paragraph alone>

## What I am measuring
Forward returns at 5, 15 and 30 minutes from each outlier print that meets the rule.

## The threshold — this is the commitment
For this to be a real edge, I require:

- Median forward return at <N> minutes:            <value, with sign>
- Hit rate (share of signals in the right direction): <value>%
- Versus the null (random entry, same month, same
  count of trades, same holding period):            beat it by <value>
- Minimum sample size for me to believe any of it:  <N> signals

## What result would make me say no
<write this. it is the most important line in the file. if you cannot write a
result that would make you abandon the rule, you are not testing anything.>

## What I expect to see
<your honest prediction, now, before you look. compare afterwards — being
wrong here is useful information about your own calibration.>
```

---

## The rules that make it mean something

**Commit it before you run the test.** Not before you present it — before you *run* it. The git
timestamp is the whole mechanism and it is worthless if the file appears at 6pm.

**One threshold, not a range.** "Somewhere around 0.1–0.4%" is not a commitment; it is a hedge that
will retroactively accommodate whatever you find.

**Include the null.** What does a random entry, same month, same trade count, same holding period,
actually return? Markets trend. A rule that produces positive returns in a month that went up has
told you about the month, not about the rule. **If your signal doesn't beat the null, you don't
have one** — and this is the single most common way a backtest lies to the person who wrote it.

**Include the minimum sample size.** Twelve signals that look wonderful are twelve signals.

**Write the disconfirming result.** If you cannot describe an outcome that would make you abandon
the rule, the test cannot fail, and a test that cannot fail is not a test.

---

## Friday

You present **the distribution you committed to**, not the best-looking cut of it. If you find
yourself on Thursday evening wanting to change the horizon from 15 minutes to 22 because 22 looks
much better — that is the exact moment this file is for. 22 minutes may well be right. It is not
right *this week*, and it is a hypothesis for next week's test, with its own committed threshold.

Shreyas asks the uncomfortable questions on Friday. That is his job and you should make it easy for
him: hand him this file before you show him anything else.

---

## If it comes back flat

**Week 2 is testing a second formulation from `strategy.md`, not building.**

Say it out loud on Friday, because on Monday it will feel like giving up and it isn't. Two weeks of
research beats six months of building the wrong thing, and everything else in the plan shifts one
week right — nothing is lost except the week you were going to waste anyway.

This is the entire reason Week 1 is called kill week and the entire reason its code is throwaway.
The plan was built expecting this outcome to be possible. Taking it is the plan working, not the
plan failing.
