# The clock lane — pre-commitments, and what is built

**Written 2026-09-06.** Scope: the **clock axis** of the Track B strategy programme —
[`strategy-split.md`](../strategy-split.md) §2, the Prathamesh column. Steps 3, 5 and 6 of
[`docs/strategy/ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6.

This file exists for one reason: **§7 of the split says every threshold in this lane is
pre-committed to Varad, in a commit, before the run.** That is the one genuine methodological
upgrade the two-lane split buys, and it is worth nothing at all if the numbers are written down
after the first surface is visible. So they are here, and they are in the code, and both landed
before any measurement did.

**Status 2026-09-06: step 3 is DONE.** Code built, archive restored and verified, M3 run on all 19
months. Result: [`analysis/M3_CLOCK.md`](../../../services/signal-data/analysis/M3_CLOCK.md).
**The clock conditions volatility; it does not produce edge; no phase clears cost.** Four runs were
needed and three gave wrong answers — two bugs of mine, both recorded in that file §4.

---

## 1. The six session-phase boundaries

**Frozen in ET wall clock, not in UTC.** `strategy-architecture.md` §2 gives them in ET;
`strategy-split.md` §7 asks for them "in UTC". Those are the same table for seven months of the
archive and a different one for the other five, so the difference has to be chosen rather than
inherited.

| Phase | ET (frozen) | UTC under EDT | UTC under EST |
| :--- | :--- | :--- | :--- |
| `Asia` | 18:00 – 02:00 | 22:00 – 06:00 | 23:00 – 07:00 |
| `Asia-London` | 02:00 – 03:00 | 06:00 – 07:00 | 07:00 – 08:00 |
| `London` | 03:00 – 08:00 | 07:00 – 12:00 | 08:00 – 13:00 |
| `London-NY` | 08:00 – 09:30 | 12:00 – 13:30 | 13:00 – 14:30 |
| `NY` | 09:30 – 13:30 | 13:30 – 17:30 | 14:30 – 18:30 |
| `NY-Asia` | 13:30 – 18:00 | 17:30 – 22:00 | 18:30 – 23:00 |

Boundaries are **left-inclusive**: 09:30 ET is the first bar of `NY`, not the last of `London-NY`.

**Why ET and not a frozen UTC number.** The London and New York opens are human working hours and
they follow local DST. A frozen UTC boundary is correct for the seven EDT months and an hour wrong
for the five EST ones (**2025-11 through 2026-03**, which is 5 of the archive's 19). An hour wrong
at 12:00 UTC means every London bar in that window is filed under `London-NY` — two populations
pooled in one bucket, reported as one base rate. That is precisely the §4.6 unit error arriving
through the clock instead of through the tick, and it is invisible in the output for the same
reason: the table still has six rows and every cell still has an N.

`tests/test_clock.py::test_the_same_utc_instant_is_a_different_phase_in_january` asserts the
consequence directly — 12:00 UTC is `London-NY` in July and `London` in January.

**⚠️ This is a departure from §7's literal wording and the room has to sign it.** The
pre-commitment is honoured — the numbers are frozen in a commit before any run — but they are
frozen in the timezone the boundary actually means.

**A known and accepted imprecision.** London and New York change DST on different dates (about
three weeks apart in March, one in November). Inside those windows "London 03:00 ET" is not
London's 08:00 local. Following two zones would mean two calendars and a phase table that is not
one clock; it is not worth it for ~4 weeks of 19 months, and it is written here rather than
discovered later.

## 2. The event window: **±15 minutes**

`features.portable.event_proximity` takes one symmetric `window_minutes`. §2's table is not
symmetric — NFP and CPI run 08:25–08:40 (−5/+10), FOMC 14:00–14:30 (0/+30).

**±15 is the committed number.** It covers the BLS window with margin on both sides and the front
half of FOMC's. What it costs, stated up front: the back fifteen minutes of the FOMC reaction land
in the non-event population. That biases *against* the event arm, which is the right direction for
a number nobody wants to talk themselves into.

Measured on the **bar's own timestamp, which is its open**, while `backtest.py` fills at the close
— so a bar marked near-event has its entry between 14 and 16 minutes of the release. One minute,
smaller than any boundary this draws, noted rather than corrected: correcting it would make the
feature's definition depend on the bar size it is computed at.

## 3. The 2025/2026 split date

**2025-01 … 2025-09 against 2025-10 … 2026-07.** Not a choice — ARCHITECTURE §6 already fixes it,
and it is restated here so all four numbers sit in one place and one commit.

The split is the whole test. M3's profile is only a finding if it survives it, the way the 50+ ATR
bucket held **0.2000 → 0.1989** while the headline moved 2.2×. A phase profile that does not
survive is a description of 2025.

## 4. The opening range: **30 minutes**

A fourth number, which §7 does not list because nothing had been written when §7 was. `anchors`
computes an opening range and an opening range has a length, so it is a threshold and it is
pre-committed like the others. Thirty minutes is the conventional reading and it is one `atr_bp`
window, which keeps the two comparable.

It emits **two** columns for the one `opening_range` anchor name — `opening_range_high` and
`opening_range_low`. An opening range is a band; collapsing it to a midpoint throws away the only
thing it is ever consulted for.

## 5. What gets reported, committed before it is run

**All three cuts, together, every time:**

| Cut | Call |
| :--- | :--- |
| Phase only | `m3_session_event(..., phases=(...), event_window_minutes=0)` |
| Event only | `m3_session_event(..., phases=(), event_window_minutes=15)` |
| Union | `m3_session_event(..., phases=(...), event_window_minutes=15)` |

The two arms are separable by construction so that the union cannot quietly become "the one that
looked best". Each is quoted against a mix- and side-matched null with `mde_rate` and N beside it
(split.md §10.7), on both halves of §3's split.

**And the reading is `|move|`, `mfe` and the reach table — never `move > 0`.** M3 is
non-directional; it returns +1/0 and never −1. A hit rate off the sign of a signed move is
answering a question M3 does not ask.

---

## 6. A finding for the room: the session shift and the Asia open disagree in winter

Not a threshold — a fact found while building this, and it belongs in front of all three of you.

`s1.SESSION_SHIFT` is `+2h`, which rolls the Globex session date at **22:00 UTC**. That is
**18:00 ET in summer — exactly the Asia open — and 17:00 ET in winter, an hour inside `NY-Asia`.**
So for the five EST months there is a one-hour window where a bar's `session` has already rolled to
day D+1 while its `phase` still reads `NY-Asia` of day D.

This is the DST hole `s1.py`'s own docstring already documents, surfacing where two clock-keyed
columns have to agree. It is **not** a defect in the phase table and it is not a reason to freeze
the phases in UTC — freezing them in UTC would make five months of phases wrong to make one hour of
labels agree.

It was tried as a *check* inside `session_phase` — assert the instrument's session boundary falls
inside `Asia` — and rejected, because GC fails it for five months of the archive on the shift, not
on anything about the instrument. Recorded here instead.

**What it means for this lane:** nothing, as long as no analysis groups by `session` and `phase`
and reads the pair as one key. `reach.py`'s bucket key uses `phase`, not `session`, so the rejoin
is unaffected. **It closes when `session_shift: pd.Timedelta` becomes the real calendar S8 drafted
and the seam's amendment (split.md §8) records** — which is the same moment, and the same commit,
as the rest of that hole.

---

## 7. What is built, and what it is waiting on

### Built and green — step 3's code

| Piece | Where |
| :--- | :--- |
| `session_phase` | `features/portable.py` — six phases, ET wall clock, categorical carrying all six whether or not a frame visits them |
| `event_proximity` | `features/portable.py` — nearest release either side, ±`window_minutes`; **empty calendar raises** |
| `anchors` | `features/portable.py` — six names, seven columns, every one causal; an anchor the instrument declares and this does not compute raises |
| `m3_session_event` | `strategies.py` — the two arms, separable, OR'd, +1/0 |
| The calendar | `calendars.py` + `reference/us_releases.csv` — 62 releases, **transcribed from BLS and the Fed, not derived** |
| Tests | `tests/test_clock.py` — 32, all on the four ways this lane can return a plausible wrong number |

**197 tests green** (165 before), `ruff` and `mypy` clean.

**The calendar is transcribed and that is the design, not fastidiousness.** The obvious shortcut —
generate payrolls from "first Friday, 08:30 ET" — is wrong on this exact archive, in both
directions at once. There is **no October 2025 Employment Situation at all**; September's landed
**2025-11-20**, seven weeks late. September CPI landed **2025-10-24**, not mid-month, and there is
**no November 2025 CPI**. A generated calendar marks a quiet Friday as payrolls *and* leaves the
highest-volatility gold bar of that quarter sitting in the null. `test_clock.py` pins all three.

**A bug caught in the building, worth knowing about elsewhere in this repo.**
`DatetimeIndex.asi8` returns the index's **own** resolution, and pandas infers it from how the
index was built — nanoseconds off `read_parquet`, microseconds off `pd.Timestamp`. Comparing those
integers to a nanosecond window divides every gap by a thousand, so a bar four hours from a release
reads as fourteen seconds from it. The event arm fired on **every bar** and still returned a
perfectly well-formed boolean Series of the right length and dtype. `_epoch_ns` pins the unit;
`test_proximity_is_the_same_answer_at_any_index_resolution` pins the fix.

### Cost of the run, measured before launching it

Varad's rule from `strategy-precommit.md` §1 — *"measure one month before launching 19"* — applies
to this lane too, and the answer is the opposite of his:

| | M3 (`m3_profile.py`) | M1's sweep |
| :--- | ---: | ---: |
| `first_touch` iterations | ~110,000 | ~32,000,000 |
| Measured | **4.6 s / month** | not yet |
| Projected, 19 months | **~1.4 minutes** | the open question |

**M3 is cheap and can be re-run freely.** It enters every bar once, at one bracket, and the three
cuts are made by *grouping* rather than by re-running. The vectorisation risk R4 names is M1's
alone, and nothing in this lane argues for touching `first_touch` — which is just as well, since it
is shared spine and Varad's (§2).

### Smoke test — 2026-07, the one month on disk

Plumbing, not a result. Reported here so the next person does not re-run it.

- 31,306 bars, 23 sessions. **Every bar lands in a phase**; none NaN.
- Phase mix `Asia` 10,853 · `Asia-London` 1,379 · `London` 6,900 · `London-NY` 2,070 · `NY` 5,490 ·
  `NY-Asia` 4,614. That is **~1,370 bars per phase-hour across all six** — gold trades nearly every
  minute of the 23-hour session, so bar *count* does not discriminate phases at all and only the
  per-bar outcome can. Worth knowing before anyone reads a count table as a liquidity profile.
- ±15 marks **93 bars, 0.297%**, on exactly three days: **2026-07-02** (payrolls), **2026-07-14**
  (CPI), **2026-07-29** (FOMC). Matches the calendar exactly.
- `anchors`: zero causality violations, `prior_close` NaN through the first session.

### ✅ The run — done 2026-09-06

**All 19 months restored and verified byte-identical against the manifest**, every `sha256` and byte
count. 2025-11 failed mid-download (`Response ended prematurely`) with its trades file already
complete, so the resume re-billed the definition alone — ~$0.01 rather than $3.85. **$64.20 total,
46,034,813 rows.**

**107,359 legs, both sides, both halves. Best phase `Asia` at +0.572 ticks against a 1.40-tick
cost — 41% of it.** Varad's "no cell clears the cost floor" holds. `London-NY` carries a large,
split-surviving reach lift (14 of 16 cells clear MDE) that **does not convert**, because its
`p_target` and `p_stop` rise together: `atr_bp`'s trailing window sizes the bracket off the quiet
hour *before* the 08:30 release. M3 is a bracket-conditioning axis for stage 7, not an entry filter.

**Two things that are not about M3.** The tie band came out empty (0.001–0.010 ATR, zero on most
months), which **removes the tie-resolution argument for `replay.py`** and shrinks step 5's scope.
And a large directional intraday pattern turned up that **this lane is not entitled to claim** —
M3's null controls for side but not for time-of-day drift.

### Not started

- **Step 5, `replay.py`.** split.md §5 requires a time budget written into that file before the
  first line of code. **The blank is still blank**, deliberately, and it stays that way until it is
  filled.
- **Step 6, the spot feed.** Route 2 has not picked a vendor, `XAUUSD` is deliberately absent from
  `instruments.py`, and `mid` / `spread_bp` / `quote_rate_z` are still committed signatures with no
  bodies. Nothing in step 3 needed any of it — which was the design (split.md §8, "the fake").

---

## 8. Still open, and not decided here

**Whether this lane has hours.** `strategy-split.md` §9 names the collision: `roles.md` and
[`README.md`](README.md) have Prathamesh in Week 1 kill-week shell work, and the strategy track is
unscheduled by design. Step 3's code is written either way and cost no product week. **The run,
and steps 5 and 6, are a scheduling decision for all three of you.**
