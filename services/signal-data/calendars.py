"""The scheduled-release calendar, transcribed rather than derived.

Clock lane, step 3 (`plans/team/strategy-split.md` §4). Feeds
`features.portable.event_proximity`, which takes the calendar as an argument
and therefore cannot be responsible for where it came from.

**These dates are transcribed from the published schedules, not computed from
a rule, and that is the whole design.** The obvious shortcut is to generate
the Employment Situation from "first Friday of the month, 08:30 ET" -- it is
right most of the time, it needs no file, and on this archive it is wrong:

  * There is **no October 2025 Employment Situation at all.** The rule invents
    one on 2025-10-03. September's report landed on **2025-11-20**, seven weeks
    late, and the rule has nothing there.
  * September 2025 CPI landed on **2025-10-24**, not mid-month, and there is
    **no November 2025 CPI**.

A generated calendar would therefore mark a quiet Friday as a payroll release
and leave the actual release -- the highest-volatility gold bar in that
quarter -- sitting in the non-event null, in both directions at once. That is
the silent degradation `instruments.require_flow` exists to refuse, arriving
through the clock instead of through the tape.

**A missing calendar is not an absence of events.** `event_proximity` on an
uncovered month returns False for every bar and looks exactly like a month
where nothing was scheduled. `require_coverage` is what makes that case raise,
and every driver of M3 calls it before it calls anything else.

Sources, both public, both free, both known in advance -- which is what makes
this feature usable live and not only in a backtest:

  * BLS release schedule -- https://www.bls.gov/schedule/2025/home.htm, /2026/
  * FOMC calendar -- https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

Fetched 2026-09-06. **Extend `reference/us_releases.csv` and `COVERAGE`
together or not at all** -- a row added past the declared window is invisible,
and a window widened past the rows is the exact failure above.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RELEASES = Path(__file__).parent / "reference" / "us_releases.csv"

# The CSV carries wall-clock ET because that is how both sources publish, and
# because 08:30 ET is the fact -- the UTC instant of a payroll release moves by
# an hour across DST while the release itself does not. Converting here means
# it is converted once.
EVENT_TZ = "America/New_York"

# What has actually been transcribed. Not the span of the rows: 2025-01-01 is
# earlier than the first row and that is correct, because January 2025 IS
# covered -- it simply has no release before the 10th.
COVERAGE = (
    pd.Timestamp("2025-01-01T00:00:00Z"),
    pd.Timestamp("2026-12-31T23:59:59Z"),
)

EVENTS = ("employment_situation", "cpi", "fomc")


def load(path: Path = RELEASES) -> pd.DatetimeIndex:
    """Every transcribed release as a sorted, unique, UTC `DatetimeIndex`.

    Unique because the three event types can and do collide -- a CPI print on
    an FOMC morning is one instant, and `event_proximity` asks a distance
    question that would otherwise count it twice for no gain.
    """
    df = pd.read_csv(path)
    missing = sorted({"timestamp_et", "event"} - set(df.columns))
    if missing:
        raise ValueError(f"{path}: not a release calendar, missing {missing}")

    unknown = sorted(set(df["event"]) - set(EVENTS))
    if unknown:
        raise ValueError(f"{path}: unknown event types {unknown}; add to EVENTS deliberately")

    local = pd.to_datetime(df["timestamp_et"]).dt.tz_localize(EVENT_TZ)
    return pd.DatetimeIndex(local.dt.tz_convert("UTC")).unique().sort_values()


def require_coverage(bars: pd.DataFrame, coverage: tuple[pd.Timestamp, pd.Timestamp] = COVERAGE) -> None:
    """Refuse to measure event conditioning over bars the calendar does not cover.

    **This is the guard, and it has to live outside `event_proximity`.** That
    function's signature is frozen to `(bars, calendar, *, window_minutes)`
    (split.md §4), so it receives an index of instants and cannot tell "the
    calendar covers this month and nothing was scheduled" from "the calendar
    has never heard of this month". Both produce all-False. Only one of them
    is a measurement.
    """
    lo, hi = coverage
    first, last = bars.index.min(), bars.index.max()
    if first < lo or last > hi:
        raise ValueError(
            f"bars span {first} .. {last}, calendar covers {lo} .. {hi}. "
            "An uncovered month reads as a month with no releases, which is "
            "the same output as a quiet month and is not the same fact. "
            "Extend reference/us_releases.csv and calendars.COVERAGE together."
        )
