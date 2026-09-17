"""§1's session windows and §12's news lockout. Prathamesh's lane.

WHY NEW YORK AND NOT UTC. `mathematical.md` §1 states the active windows in
New York time, and New York is UTC-5 for part of the year and UTC-4 for the
rest. A UTC constant is correct for half the archive and wrong by exactly one
hour for the other half -- and an hour-sized error at a session boundary reads
as an off-by-one in the window logic rather than as a timezone bug, which is
how it survives review. `zoneinfo` does the conversion; nothing here does
arithmetic on offsets.

WHY THE WINDOWS ARE HALF-OPEN. `[08:00, 11:30)` and `[13:30, 15:30)`. A closed
upper bound would put a 15:30 bar in both the afternoon window and whatever
follows it, and a bar counted twice is a trade counted twice.

WHY THE WEEKEND CHECK IS HERE AND NOT UPSTREAM. Spot runs 24x5, so a Saturday
instant has a perfectly valid New York clock reading inside the morning window.
Only the calendar knows the market was shut.

⚠️ THIS MODULE DOES NOT KNOW ABOUT HOLIDAYS. Thanksgiving and Good Friday have
weekday clocks and no session. `calendars.require_coverage` is the existing
guard for the release calendar; an exchange-holiday calendar is a separate
thing this repo does not yet have, and E2's funnel will over-count by roughly
nine days a year until it does.
"""

from __future__ import annotations

from datetime import time

import pandas as pd

SESSION_TZ = "America/New_York"

# §1's two active windows, New York time, half-open.
WINDOWS: tuple[tuple[time, time], ...] = (
    (time(8, 0), time(11, 30)),
    (time(13, 30), time(15, 30)),
)

# §12 states two: a 2-minute hard event lock and a wider 5-minute internal
# risk lock. The internal one is what the strategy actually trades against,
# so it is the named constant and the hard one is passed explicitly.
INTERNAL_LOCKOUT_MIN = 5
HARD_LOCKOUT_MIN = 2


def _require_aware(ts: pd.DatetimeIndex, what: str) -> None:
    if ts.tz is None:
        raise ValueError(
            f"{what} must be tz-aware; a naive timestamp guessed as UTC is how a "
            "five-minute lockout lands five hours from the release")


def in_window(ts: pd.DatetimeIndex) -> pd.Series:
    """§1: is each instant inside one of the two active windows?

    Weekends are excluded on the calendar rather than on the clock -- spot
    runs 24x5, so a Saturday morning has a valid New York reading inside the
    morning window and no market behind it.
    """
    _require_aware(ts, "in_window's index")
    local = ts.tz_convert(SESSION_TZ)
    clock = pd.Series(False, index=ts)
    for start, end in WINDOWS:
        clock |= pd.Series(
            (local.time >= start) & (local.time < end), index=ts)
    return clock & pd.Series(local.dayofweek < 5, index=ts)


def news_lockout(ts: pd.DatetimeIndex, events: pd.DatetimeIndex,
                 *, minutes: int = INTERNAL_LOCKOUT_MIN) -> pd.Series:
    """§12: is each instant within `minutes` either side of a release?

    Symmetric and inclusive at both edges. An asymmetric window admits
    entries into the release, which is the one thing §12 exists to stop, and
    an exclusive edge admits the instant a release lands on the boundary.

    Overlapping releases take the UNION of their windows -- a CPI print on an
    FOMC morning must not unlock the gap between them.
    """
    _require_aware(ts, "news_lockout's index")
    if len(events) == 0:
        # An empty index must not broadcast into an all-True mask. Nothing
        # scheduled is a real answer and it is "clear", not "locked".
        return pd.Series(False, index=ts)
    _require_aware(events, "the event calendar")
    span = pd.Timedelta(minutes=minutes)
    # Distance to the NEAREST release: `reindex(method="nearest")` is the
    # union by construction, because each instant is measured against
    # whichever event is closest rather than against one chosen in advance.
    nearest = events[events.get_indexer(ts, method="nearest")]
    gap = (nearest - ts).to_series(index=ts).abs()
    return gap <= span


# --------------------------------------------------------------------------
# §9's sweep and reclaim. Task 11.

# §9: the reclaim must clear the level by delta = max(2 ticks, 0.05 * ATR).
# On spot the "2 ticks" leg is unusable -- `XAUUSD.tick` is Dukascopy's 0.001
# PRICE QUANTUM and `instruments.py` says in terms that it must not be used
# for costing. So the floor is stated in USD/oz directly: two cents, which is
# a real broker's minimum increment rather than a feed's encoding precision.
RECLAIM_FLOOR_USD = 0.02
RECLAIM_ATR_FRACTION = 0.05

# §9: "The sweep must not be accepted if price remains below the level for
# more than 30 seconds. That is more likely acceptance than rejection."
MAX_RECLAIM_S = 30.0


def reclaim_delta(atr: float) -> float:
    """§9's delta, in USD per ounce. See `RECLAIM_FLOOR_USD` for the tick leg."""
    if atr <= 0:
        raise ValueError(
            f"atr must be positive, got {atr}; a zero ATR collapses delta to the "
            "floor and silently produces a different detector than §9 specifies")
    return max(RECLAIM_FLOOR_USD, RECLAIM_ATR_FRACTION * atr)


def sweeps(ticks: pd.DataFrame, *, level: float, side: int, atr: float,
           max_reclaim_s: float = MAX_RECLAIM_S) -> pd.DataFrame:
    """§9's sweep-and-reclaim events against one level.

    `side = +1` sweeps a low (price breaks below `level` and reclaims it);
    `side = -1` sweeps a high. Returns one row per completed event with
    `swept_level` (the extreme reached), `reclaim_dt_s` and `wick_w`.

    THE EXTREME, NOT THE FIRST BREACH. `wick_w` is measured from the furthest
    point reached, because §9's limit sits at `P_s + 0.50W` -- measuring from
    the first tick through the level moves every entry price in the backtest.

    THE 30-SECOND RULE IS A REJECTION, NOT A TIMEOUT. An excursion that
    reclaims late is not a slower sweep; §9 reads it as acceptance of the
    level, which is the opposite signal. So it yields no row at all.
    """
    if side not in (1, -1):
        raise ValueError(f"side must be +1 or -1, got {side}")
    d = reclaim_delta(atr)
    t, mid = ticks["timestamp"], ticks["mid"]
    if not t.is_monotonic_increasing:
        raise ValueError(
            "ticks must be sorted by timestamp; out of order, a reclaim duration "
            "comes back negative and compares as within the limit")

    # Work in "signed depth beyond the level" so one loop serves both sides.
    beyond = (level - mid) * side          # > 0 while price is through the level
    back = -beyond                          # > 0 once price is back the other way

    rows, i, n = [], 0, len(ticks)
    while i < n:
        if beyond.iloc[i] <= 0:
            i += 1
            continue
        start, extreme, j = i, beyond.iloc[i], i
        while j < n and beyond.iloc[j] > 0:
            extreme = max(extreme, beyond.iloc[j])
            j += 1
        if j >= n:
            break                           # never came back; not a sweep
        # j is the first tick back through the level. It counts only if it
        # clears by delta -- a touch is not a reclaim.
        if back.iloc[j] >= d:
            dt = (t.iloc[j] - t.iloc[start]).total_seconds()
            if dt <= max_reclaim_s:
                rows.append({
                    "ts": t.iloc[j],
                    "swept_level": level - extreme * side,
                    "reclaim_dt_s": dt,
                    "wick_w": extreme + back.iloc[j],
                })
        i = j + 1
    return pd.DataFrame(rows, columns=["ts", "swept_level", "reclaim_dt_s", "wick_w"])
