# `plans/team/` — the twelve-week execution path, split three ways

Source: the **Twelve Weeks to Ten Subscribers** artifact. That document says *what* to build and
*why*. This folder says **who does what on which day**, arranged so that no one is ever waiting
on anyone else to finish.

~~**Week 1 starts Monday 31 Aug 2026. Week 12 ends Friday 20 Nov 2026.**~~

⚠️ **The calendar moved one week right on 28 Aug: nobody works 29 Aug – 4 Sep.** Week 1 now runs
**Sat 5 – Fri 11 Sep** and Week 12 ends **Fri 27 Nov**. **Every date in the phase files below is one
week early.** [`week-01.md`](week-01.md) carries the rescheduled Week 1 in full and the shift table
for the rest; it is authoritative on dates until the phase files are rewritten. The gates themselves
are unchanged in content — only when they are held moved.

## The files

| File | Read it when |
| :--- | :--- |
| [`roles.md`](roles.md) | Once, on day 0. Who owns which system, who decides what, how each of you fails |
| [`contracts.md`](contracts.md) | **Before you write any code.** The six frozen seams. This is the file that makes the parallelism work |
| [`gates.md`](gates.md) | Every Friday, 16:00 |
| [`week-00.md`](week-00.md) | Now — 26–30 Aug. Clearing the debt so Week 1 starts from zero |
| [`week-01.md`](week-01.md) | **Fri 28 Aug, before the gap, and again on 5 Sep.** The rescheduled kill week, day by day for both engineers, and the four things Friday has to close so seven idle days cost nothing |
| [`phase-1-kill-week.md`](phase-1-kill-week.md) | Week 1 · ~~31 Aug – 4 Sep~~ **5 – 11 Sep** · *does this project deserve to exist* |
| [`phase-2-month-one.md`](phase-2-month-one.md) | Weeks 2–4 · 7 Sep – 25 Sep · *make it real, locally* |
| [`phase-3-month-two.md`](phase-3-month-two.md) | Weeks 5–8 · 28 Sep – 23 Oct · *make it sellable* |
| [`phase-4-month-three.md`](phase-4-month-three.md) | Weeks 9–12 · 26 Oct – 20 Nov · *ten people who pay* |

`plans/current.md` stays the live status tracker. This folder is the schedule. When a day's work
lands, `current.md` moves and `daily_updates/YYYY-MM-DD.md` records the evidence — same rule as
always, and it applies to Claude too.

## Your folder

**Open your own folder and you have your twelve weeks in one file.** The phase files above stay the
shared source of truth — scope is agreed there, so the two can never disagree about what a day is.

| Folder | What's in it |
| :--- | :--- |
| [`prathamesh/`](prathamesh/README.md) | Your 12 weeks, day by day · [`ramp.md`](prathamesh/ramp.md) — the frontend→backend path, three steps |
| [`varad/`](varad/README.md) | Your 12 weeks, day by day · [`thresholds.md`](varad/thresholds.md) — **due Thursday of Week 1, before you look at any results** |
| [`shreyas/`](shreyas/README.md) | Your 12 weeks, day by day · [`grading.md`](shreyas/grading.md) — learning to read a footprint chart, and the grading protocol · [`review-rubric.md`](shreyas/review-rubric.md) — AI code review, and what it does not catch |

## The calendar

| | Week | Dates | Theme |
| :--- | :--- | :--- | :--- |
| — | 0 | Aug 26 – Aug 30 | Clear the debt from Days 1–3 |
| **Phase 1** | 1 | Aug 31 – Sep 04 | Kill week |
| **Phase 2** | 2 | Sep 07 – Sep 11 | Engine and shell become real code |
| | 3 | Sep 14 – Sep 18 | Live numbers on screen |
| | 4 | Sep 21 – Sep 25 | Rules, journal, dogfood |
| **Phase 3** | 5 | Sep 28 – Oct 02 | Backend |
| | 6 | Oct 05 – Oct 09 | Website — three days, then stop |
| | 7 | Oct 12 – Oct 16 | Private beta |
| | 8 | Oct 19 – Oct 23 | Fix the five things |
| **Phase 4** | 9 | Oct 26 – Oct 30 | Open the doors |
| | 10–11 | Nov 02 – Nov 13 | Founder-led distribution |
| | 12 | Nov 16 – Nov 20 | Count what's true |

## How to read a day

Every day is written as three independent blocks plus two annotations:

```
#### W3D2 · Tue Sep 15
P  what Prathamesh does
V  what Varad does
S  what Shreyas does
Float  work that is divisible today, and who takes it if someone finishes early
Why nobody is blocked  the fixture or contract that makes the three blocks independent
```

**The Float row is the one people skip and shouldn't.** It is where "divide both sections' work"
actually happens. If you finish your block before 16:00, you take the Float item — you do not
start tomorrow's block. Starting tomorrow's block early is how the two lanes drift out of sync
and how one of you ends up waiting on the other in week nine.

## The four rules that hold this together

1. **Nobody waits for a real implementation.** The owner of a seam ships the *type* and a *fake*
   on the first day the seam exists. The consumer builds against the fake. See `contracts.md`.
2. **Gates don't slide.** If Friday's gate isn't met, next week is the same gate. It is not
   "the same gate plus next week's work." Sliding gates is how twelve weeks becomes nine months.
3. **A blocked person switches to Float, not to waiting.** If you are genuinely blocked and the
   Float row is empty, say so in the standup — that is a planning bug and it gets fixed same day.
4. **Shreyas's "no" stops the sprint.** If domain validation says the signal is wrong, that is
   not feedback to be triaged. That is the sprint ending. Neither engineer can grade their own
   homework.

## Daily rhythm

15 minutes, same time every day, all three. Three questions each: what shipped yesterday, what
ships today, what's blocking. Friday 16:00 is the go/no-go against that week's gate in
[`gates.md`](gates.md).

## Two things the artifact decided that everything here assumes

- **Delta cannot come from a screenshot.** It requires the aggressor side of every trade, which a
  rendered candle has already discarded. Capture supplies *context only* — symbol, timeframe,
  drawn levels. Every number comes from the feed.
- **Bring-your-own-feed.** The user connects their own CME entitlement; the overlay computes delta
  on their machine; no market data ever touches our servers. This deletes a $1,750/mo distribution
  licence and a five-figure CME derived-data licence. It also narrows the launch audience to
  futures traders on GC. That trade is deliberate. **NQ was dropped on 25 Aug** — never pulled, and
  one instrument means one set of thresholds and one reference session to validate.
