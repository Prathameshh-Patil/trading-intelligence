"""Track B's feature surface: the intersection of GC and spot, and nothing else.

Contract: `docs/strategy/ARCHITECTURE.md` §4.3. **The admission rule is one
sentence: if it cannot be computed on both instruments, it does not go in this
file.** Order flow fails that test on spot -- no tape, no aggregate volume, no
aggressor -- which is why `features/orderflow.py` is a separate, GC-only module
rather than a section of this one.

**Everything here is in BASIS POINTS of price** (§4.6), and that is not a
presentation choice. GC's tick is 0.10; an MT5 broker may call a XAUUSD pip
0.01 or 0.10, a 10x spread in what "40" means. A mis-scaled display renders
visibly wrong. A mis-scaled *bucket* silently pools two populations and reports
the average as a base rate, which is the error that cannot be seen in the
output. Conversion to whatever the trader's platform calls a pip happens once,
at stage 9, labelled.

Most functions here take no `Instrument` at all, and that is the point: a
quantity in basis points of price is already instrument-free. `atr_bp` is the
exception, because it wraps a tick-denominated function it must not re-derive.

STATUS. `atr_bp` ships with the seam (`plans/team/strategy-split.md` §3), so
the clock lane has its bucket axis on day one. **Every other function here is a
committed SIGNATURE with no body.** Ownership is by function name and is listed
in split.md §4; the order below is that table's order. Never reorder, never
rename, never add a function without standup -- two people fill in disjoint
bodies in this file and none of that works against a moving target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.expansion import atr
from instruments import Instrument

# --------------------------------------------------------------------------
# The two lanes' pre-committed numbers -- split.md §7. Both sets are frozen in
# code, in a commit, AHEAD of the run that reads them, and both are ordered
# here the way §4 splits this file: the vol axis, then the clock axis.
# --------------------------------------------------------------------------

# --- Varad, the vol axis --------------------------------------------------
# The bucket axis of `reach.py`'s key, committed 2026-09-06 BEFORE any surface
# was computed -- `plans/team/strategy-precommit.md` §2, which carries the
# derivation. These are the pooled quartiles of the 19-month archive (6.79 /
# 9.65 / 13.87 over 109,875 bars) rounded to whole basis points.
#
# **Basis points, not ticks, and the archive says why rather than the rule.**
# Track A's fixed tick edges drifted 1.84x in what they meant as gold ran from
# 2,732 to 5,037: 30 ticks is 10.98 bp in 2025-01 and 5.96 bp in 2026-02. One
# labelled bucket, two populations, and the average reported as a base rate.
#
# tests/test_instruments.py fails if this line changes. That is the point --
# editing it means going and amending the commitment, in a commit, with the
# measurement that moved it.
ATR_BP_EDGES = (0.0, 7.0, 10.0, 14.0, float("inf"))

# --- Prathamesh, the clock axis -------------------------------------------
# Argued in `plans/team/prathamesh/clock-lane.md`; frozen here. Same rule as
# the edges above: a number changed after a surface is visible is a fit.

# `strategy-architecture.md` §2 gives the six phases in ET wall clock, and ET
# wall clock is what is frozen -- NOT a fixed UTC offset. split.md §7 asks for
# "the boundaries in UTC" and this is a deliberate departure from its wording:
# the London and NY opens are human working hours and they follow local DST, so
# a frozen UTC number is an hour wrong for the five months of the archive that
# sit in EST (2025-11 .. 2026-03) and would pool two populations in one bucket
# -- the §4.6 error, arriving through the clock. The UTC equivalents under both
# regimes are tabulated in clock-lane.md.
PHASE_TZ = "America/New_York"

# Right-open edges in minutes past ET midnight, and the phase each interval
# closes. **Asia appears twice because it spans midnight** -- 18:00 to 02:00 is
# one liquidity regime on two calendar dates, and cutting it at midnight would
# file the same regime under two bucket keys.
_PHASE_EDGES = (0, 120, 180, 480, 570, 810, 1080, 1440)
_PHASE_CUTS = ("Asia", "Asia-London", "London", "London-NY", "NY", "NY-Asia", "Asia")

# The canonical order, and the categorical's category order, so that
# `groupby(observed=False)` yields all six cells even where a frame is missing
# one. A phase absent from a result table is a fact; a phase silently absent
# from the table's index is a hole nobody sees.
PHASES = ("Asia", "Asia-London", "London", "London-NY", "NY", "NY-Asia")

# The opening range is a band, not an instant, so its length is a threshold and
# is pre-committed like the rest. Thirty minutes is the conventional reading and
# it is one `atr_bp` window, which keeps the two comparable.
OPENING_RANGE = pd.Timedelta(minutes=30)

# What `anchors` knows how to compute. `Instrument.anchors` is the authority on
# which of these are DEFINED for an instrument; this is the authority on which
# are implemented at all, and a name in the first but not the second raises.
_ANCHORS = frozenset(
    {"session_open", "prior_close", "session_high", "session_low", "opening_range", "twap"}
)


def _epoch_ns(idx: pd.DatetimeIndex) -> np.ndarray:
    """A tz-aware index as nanoseconds since the epoch, at a PINNED resolution.

    Spelling the unit out is not decoration. `DatetimeIndex.asi8` returns the
    index's OWN resolution, and pandas infers that from how the index was
    built -- nanoseconds off `read_parquet`, microseconds off `pd.Timestamp`.
    Comparing those integers against a nanosecond window silently divides
    every gap by a thousand, so a bar four hours from a release reads as
    fourteen seconds from it, and the result is still a well-formed boolean
    Series of exactly the right length.
    """
    return idx.to_numpy(dtype="datetime64[ns]").astype("int64")


def to_bp(move: pd.Series, price: pd.Series) -> pd.Series:
    """A price-denominated quantity as basis points of the price it moved from.

    `price` is the bar's own close, contemporaneous. Anything later is
    lookahead, and a fixed reference price would make the bp figure drift with
    the level over 19 months -- which is exactly the pooling error §4.6 names.
    """
    return 1e4 * move / price


# --------------------------------------------------------------------------
# Varad -- the vol axis
# --------------------------------------------------------------------------
def atr_bp(bars: pd.DataFrame, inst: Instrument, *, window: str, min_bars: int) -> pd.Series:
    """ATR as basis points of price. **The bucket axis the whole track keys on.**

    `features.expansion.atr` is imported and rescaled, never re-derived --
    `regime_filter.py`'s rule, which carries double force now that two people
    are writing trailing windows: re-solving session-grouped windows in a
    second file is how the two quietly disagree about the London open.

    That import is also why this is the one function here needing an
    `Instrument`: `atr` answers in ticks, so the tick multiplies back out
    before the close divides in.
    """
    ticks = atr(bars, inst, window=window, min_bars=min_bars)
    return to_bp(ticks * inst.tick, bars["close"])


def range_bp(bars: pd.DataFrame) -> pd.Series:
    """High minus low as basis points of the close. Step 2."""
    raise NotImplementedError("range_bp -- Varad, step 2")


def rv_parkinson(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Parkinson realized volatility over a trailing session-grouped window.

    High-low rather than close-close, because it uses the whole bar and is the
    lower-variance estimator of the two on the same sample -- which matters
    when the claim M2 makes is about scale. Step 4.
    """
    raise NotImplementedError("rv_parkinson -- Varad, step 4")


def rv_slope(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Signed change in `rv_parkinson` across the window: the vol_state axis.

    **Signed, so the three states are EXPANDING / CONTRACTING / STABLE.** An
    absolute slope collapses the first two into one bucket, and compression
    before a move and decay after one are not the same regime. Step 4.
    """
    raise NotImplementedError("rv_slope -- Varad, step 4")


def efficiency_ratio(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Net directional move over total path travelled across the window.

    Near 1 the window went one way; near 0 it covered the same ground twice.
    This is the shape half of the vol axis -- `rv_parkinson` cannot tell a
    trend from a fight, and the two want different geometry. Step 4.
    """
    raise NotImplementedError("efficiency_ratio -- Varad, step 4")


# --------------------------------------------------------------------------
# Prathamesh -- the clock axis
# --------------------------------------------------------------------------
def session_phase(bars: pd.DataFrame, inst: Instrument) -> pd.Series:
    """Which of the six phases each bar sits in. `strategy-architecture.md` §2.

    **The six boundaries are pre-committed to Varad, in a commit, before M3
    runs** (split.md §7) and were reviewed and signed off on 6 Sep. A boundary
    moved after the EV surface is visible is a fit, and `reach.py` is written
    against this column exactly as delivered. Step 3.

    **Frozen in ET wall clock, not in UTC** -- see `PHASE_TZ` for why, and
    `clock-lane.md` for both UTC mappings. The consequence is visible and
    intended: 12:00 UTC is London-NY in July and London in January, because
    08:00 in New York is what the boundary means.

    Returns a categorical carrying all six `PHASES` whether or not the frame
    exercises them, so a bucket table has a row for a phase that never fired.

    **`inst` is unused today and the signature keeps it anyway.** Two reasons,
    and neither is signature inertia. The boundaries are ET wall clock and
    identical on GC and spot -- which is precisely what admits this feature to
    a file whose entry rule is "computable on both instruments". And the
    reference zone becomes a property of the instrument the moment S8's
    recorded amendment is undone and `session_shift: pd.Timedelta` grows into
    a real calendar; that is where it will be read from.

    Using `inst.session_shift` to *check* the phases against the instrument's
    own session boundary was tried and rejected: GC's +2h rolls the session
    date at 22:00 UTC, which is 18:00 ET in summer -- exactly the Asia open --
    but 17:00 ET in winter, an hour inside NY-Asia. The check fails for five
    months of the archive on the DST hole `s1.SESSION_SHIFT` already
    documents, which is a fact about that shift and not about any instrument.
    It is recorded in clock-lane.md as a finding for the room instead.
    """
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is None:
        raise ValueError(
            f"{inst.name}: bars are indexed by a naive timestamp. A phase is a wall-clock "
            "fact, and reading a naive index as UTC is a guess that mislabels every bar "
            "by however much the guess was wrong."
        )
    et = idx.tz_convert(PHASE_TZ)
    cut = pd.cut(
        et.hour * 60 + et.minute,
        bins=_PHASE_EDGES,
        labels=_PHASE_CUTS,
        right=False,
        ordered=False,
    )
    return pd.Series(pd.Categorical(cut, categories=PHASES), index=bars.index, name="phase")


def event_proximity(
    bars: pd.DataFrame, calendar: pd.DatetimeIndex, *, window_minutes: int
) -> pd.Series:
    """Whether a bar falls within `window_minutes` either side of a release.

    `calendar` is the BLS release schedule and the Fed's FOMC dates -- both
    public, both free, and both known in advance, which is what makes this
    usable live rather than only in a backtest. The window is pre-committed
    (split.md §7). Step 3.

    Symmetric, because the signature carries one number. §2's table is not:
    NFP and CPI run 08:25-08:40 (-5/+10) and FOMC 14:00-14:30 (0/+30). The
    pre-committed ±15 covers the first with margin and the front half of the
    second; clock-lane.md carries the argument and what it costs.

    **Measured on the bar's own timestamp, which is its OPEN.** `backtest.py`
    fills at the bar's CLOSE, so a bar marked True is one whose entry lands
    between `window_minutes - 1` before and `window_minutes + 1` after. That
    one minute is smaller than any boundary this is used to draw and is noted
    rather than corrected, because correcting it would make the feature's
    definition depend on the bar size it is computed at.

    **An empty calendar raises rather than returning all-False.** Every bar
    "far from an event" and "no calendar loaded" are the same output and
    different facts -- and the second silently moves every release bar into
    the null. `calendars.require_coverage` is the other half of that guard and
    catches the harder case, a calendar that is real but does not reach these
    months.
    """
    if window_minutes <= 0:
        raise ValueError(f"window_minutes must be positive, got {window_minutes}")

    cal = pd.DatetimeIndex(calendar)
    if cal.empty:
        raise ValueError(
            "empty release calendar. Every bar would read as far from an event, which is "
            "indistinguishable from a genuinely quiet stretch and puts every release in "
            "the null. See calendars.py."
        )
    idx = pd.DatetimeIndex(bars.index)
    if cal.tz is None or idx.tz is None:
        raise ValueError("both the calendar and the bar index must be tz-aware")

    # Both sides through `_epoch_ns`, and read its docstring before changing
    # either -- the resolution trap it describes is silent and total.
    events = np.sort(_epoch_ns(cal))
    stamps = _epoch_ns(idx)
    after = np.searchsorted(events, stamps)

    # Distance to the nearest release on either side. The sentinel is the int64
    # ceiling so an index with nothing before or after it loses the minimum
    # cleanly, without a NaN turning the comparison into a silent False.
    ceiling = np.iinfo(np.int64).max
    before = np.where(after > 0, stamps - events[np.maximum(after - 1, 0)], ceiling)
    ahead = np.where(after < len(events), events[np.minimum(after, len(events) - 1)] - stamps, ceiling)

    gap = np.minimum(before, ahead)
    return pd.Series(
        gap <= window_minutes * 60 * 1_000_000_000, index=bars.index, name="near_event"
    )


def anchors(bars: pd.DataFrame, inst: Instrument) -> pd.DataFrame:
    """The reference prices of `inst.anchors`, one column each, aligned to bars.

    Session open, prior close, session high/low, opening range, TWAP. Every one
    is causal by construction -- a cumulative or a completed extreme over bars
    that have already closed. **`inst.anchors` is the authority on which are
    defined**: a 24x5 spot instrument's "session open" is a named boundary
    somebody chose, not a bell, and an anchor that means something different on
    the second instrument is worse than one that is absent. Step 3.

    **Causality here is a cumulative, not a shift.** `session_high` at bar k is
    the highest high of bars 0..k INCLUSIVE, which is what a trader watching
    the tape has; `bars.groupby(...)["high"].max()` broadcast back is the
    session's final high on every bar of the session, and it is the same shape,
    the same dtype and a perfect forecast. The two differ only in a result
    table, and only by being right.

    **`opening_range` is one name and two columns**, `opening_range_high` and
    `opening_range_low`, which is the one place this departs from the "one
    column each" the signature implies. An opening range is a band; collapsing
    it to a midpoint discards the only thing it is consulted for. It is NaN
    until the band has closed -- a bar twelve minutes into the session cannot
    know the thirty-minute range, and a session shorter than `OPENING_RANGE`
    has none at all rather than a partial one.

    **An anchor `inst.anchors` names and this function does not implement
    raises.** Returning the frame short a column is how a downstream `.get`
    turns a missing anchor into a default and reports it as a measurement.
    """
    unknown = [a for a in inst.anchors if a not in _ANCHORS]
    if unknown:
        raise ValueError(
            f"{inst.name} declares anchors this function does not compute: {unknown}. "
            f"Known: {sorted(_ANCHORS)}. An anchor that means something different on the "
            "second instrument is worse than one that is absent -- so add it deliberately."
        )

    by_session = bars.groupby("session", sort=False)
    stamps = pd.Series(bars.index, index=bars.index)
    opened = stamps.groupby(bars["session"], sort=False).transform("first")
    # Right-open, so the bar exactly at open+30m is the first one that can see
    # the completed band -- and is therefore the first with a value.
    forming = stamps < opened + OPENING_RANGE

    out: dict[str, pd.Series] = {}
    for name in inst.anchors:
        if name == "session_open":
            out[name] = by_session["open"].transform("first")
        elif name == "prior_close":
            # NaN through the first session, which is correct: there is no
            # prior close on the first day of the archive, and carrying the
            # session's own close backwards would be a perfect one.
            out[name] = bars["session"].map(by_session["close"].last().shift(1)).astype("float64")
        elif name == "session_high":
            out[name] = by_session["high"].cummax()
        elif name == "session_low":
            out[name] = by_session["low"].cummin()
        elif name == "opening_range":
            out["opening_range_high"] = (
                bars["high"].where(forming).groupby(bars["session"], sort=False).transform("max").where(~forming)
            )
            out["opening_range_low"] = (
                bars["low"].where(forming).groupby(bars["session"], sort=False).transform("min").where(~forming)
            )
        elif name == "twap":
            # Time-weighted over the bars that EXIST. `minute_bars` drops
            # minutes with no trades, so every present bar is exactly one
            # minute and the expanding mean is already time-weighted -- but a
            # minute with no trade has no price to weight, and inventing the
            # previous close for it would weight a dead market as though it
            # had traded there.
            out[name] = by_session["close"].cumsum() / (by_session.cumcount() + 1)

    return pd.DataFrame(out, index=bars.index)


def mid(quotes: pd.DataFrame) -> pd.Series:
    """(bid + ask) / 2. Spot-native; GC has no quote data in this repo. Step 6."""
    raise NotImplementedError("mid -- Prathamesh, step 6")


def spread_bp(quotes: pd.DataFrame) -> pd.Series:
    """(ask - bid) as basis points of the mid.

    **Read the result with §7's caveat attached.** Spot spread is a broker
    pricing decision, not a market outcome: a dealer widens on its own risk
    policy and its own client flow, so two brokers disagree about the same
    instant. This yields a legitimate yes/no on whether spread structure
    predicts anything. It is never a threshold that transfers. Step 6.
    """
    raise NotImplementedError("spread_bp -- Prathamesh, step 6")


def quote_rate_z(quotes: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Quote updates per interval, z-scored on a trailing window.

    **Within instrument AND within vendor, never a raw threshold.** An
    absolute quote rate measures the vendor's throttling and aggregation as
    much as the market's activity, so a level that transfers between two feeds
    does not exist. A trailing z within one feed does. Step 6.
    """
    raise NotImplementedError("quote_rate_z -- Prathamesh, step 6")
