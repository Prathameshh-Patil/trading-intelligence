"""§1's session windows and §12's news lockout, tested on the clock traps.

`mathematical.md` §1 states the active windows in **New York time**, and the
whole difficulty is that New York is UTC-5 for part of the year and UTC-4 for
the rest. A UTC constant is right for half the archive and wrong by exactly
one hour for the other half -- an error that looks like a boundary bug rather
than a timezone bug, which is why it survives review.

§12's lockout is symmetric by specification. An asymmetric window silently
admits entries into a release, which is the one thing it exists to stop.
"""

from __future__ import annotations

import pandas as pd
import pytest

from features import structure


def ts(*stamps: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([pd.Timestamp(s, tz="UTC") for s in stamps])


# ------------------------------------------------------------ §1 the windows

def test_the_windows_are_new_york_time_not_a_utc_constant() -> None:
    # 12:00 UTC is 07:00 in New York in January (EST, UTC-5) and 08:00 in
    # July (EDT, UTC-4). One is outside the morning window and one is its
    # first minute. A fixed UTC offset cannot get both right.
    out = structure.in_window(ts("2025-01-15T12:00", "2025-07-15T12:00"))
    assert list(out) == [False, True]


def test_the_morning_window_runs_0800_to_1130_new_york() -> None:
    # EDT, so New York is UTC-4: 12:00 UTC = 08:00, 15:30 UTC = 11:30.
    inside = ts("2025-07-15T12:00", "2025-07-15T14:00", "2025-07-15T15:29")
    assert structure.in_window(inside).all()
    outside = ts("2025-07-15T11:59", "2025-07-15T15:31")
    assert not structure.in_window(outside).any()


def test_the_afternoon_window_runs_1330_to_1530_new_york() -> None:
    inside = ts("2025-07-15T17:30", "2025-07-15T19:29")
    assert structure.in_window(inside).all()
    assert not structure.in_window(ts("2025-07-15T17:29")).any()


def test_the_gap_between_the_two_windows_is_excluded() -> None:
    # 16:00 UTC is 12:00 New York -- after the morning window and before the
    # afternoon one. §1 permits no entries there.
    assert not structure.in_window(ts("2025-07-15T16:00")).any()


def test_the_window_end_is_exclusive_so_1130_itself_is_out() -> None:
    # A half-open window is the only one that cannot double-count a boundary
    # bar against the afternoon session's start.
    assert not structure.in_window(ts("2025-07-15T15:30")).any()


def test_a_weekend_instant_is_outside_every_window() -> None:
    # 2025-07-19 is a Saturday. The clock says 09:00 New York; the market
    # says closed, and a window that only checks the clock would admit it.
    assert not structure.in_window(ts("2025-07-19T13:00")).any()


# ----------------------------------------------------------- §12 the lockout

def test_the_lockout_is_symmetric_around_the_release() -> None:
    ev = ts("2025-07-15T12:30")
    before = structure.news_lockout(ts("2025-07-15T12:26"), ev, minutes=5)
    after = structure.news_lockout(ts("2025-07-15T12:34"), ev, minutes=5)
    assert bool(before.iloc[0]) is True
    assert bool(after.iloc[0]) is True


def test_the_edges_are_inclusive_so_a_release_at_the_boundary_locks_out() -> None:
    ev = ts("2025-07-15T12:30")
    edges = ts("2025-07-15T12:25", "2025-07-15T12:35")
    assert structure.news_lockout(edges, ev, minutes=5).all()


def test_one_minute_outside_the_window_is_clear() -> None:
    ev = ts("2025-07-15T12:30")
    clear = ts("2025-07-15T12:24", "2025-07-15T12:36")
    assert not structure.news_lockout(clear, ev, minutes=5).any()


def test_the_release_instant_itself_is_locked_out() -> None:
    ev = ts("2025-07-15T12:30")
    assert structure.news_lockout(ev, ev, minutes=5).all()


def test_overlapping_releases_do_not_unlock_each_other() -> None:
    # A CPI print on an FOMC morning is two events close together. The union
    # of their windows must be locked, not the intersection.
    ev = ts("2025-07-15T12:30", "2025-07-15T12:40")
    assert structure.news_lockout(ts("2025-07-15T12:35"), ev, minutes=5).all()


def test_an_empty_calendar_locks_nothing_rather_than_everything() -> None:
    # An empty index must not broadcast into an all-True mask.
    empty = pd.DatetimeIndex([], tz="UTC")
    assert not structure.news_lockout(ts("2025-07-15T12:30"), empty, minutes=5).any()


def test_a_naive_timestamp_is_refused_rather_than_assumed_to_be_utc() -> None:
    # Guessing the zone is how a five-minute lockout lands five hours away.
    with pytest.raises(ValueError, match="tz-aware"):
        structure.in_window(pd.DatetimeIndex(["2025-07-15T12:00"]))


def test_the_internal_lockout_is_wider_than_the_hard_one() -> None:
    # §12: a 2-minute hard event lock, a 5-minute internal risk lock. The
    # internal one is the one the strategy trades against.
    ev = ts("2025-07-15T12:30")
    at = ts("2025-07-15T12:27")
    assert not structure.news_lockout(at, ev, minutes=2).any()
    assert structure.news_lockout(at, ev, minutes=structure.INTERNAL_LOCKOUT_MIN).all()


# --------------------------------------------- §9 sweep and reclaim, Task 11

def tick_frame(rows: list[tuple[int, float]]) -> pd.DataFrame:
    """(second offset, mid) ticks from a fixed base instant."""
    base = pd.Timestamp("2025-07-15T13:00:00Z")
    return pd.DataFrame({
        "timestamp": [base + pd.Timedelta(seconds=s) for s, _ in rows],
        "mid": [m for _, m in rows],
    })


def test_a_sweep_that_reclaims_inside_the_limit_is_a_candidate() -> None:
    # Price breaks 3000 by a dollar, then reclaims it ten seconds later.
    t = tick_frame([(0, 3001.0), (5, 2999.0), (15, 3001.5), (25, 3002.0)])
    out = structure.sweeps(t, level=3000.0, side=1, atr=2.0)
    assert len(out) == 1
    assert out.iloc[0]["reclaim_dt_s"] == 10.0


def test_price_staying_below_the_level_past_the_limit_is_acceptance_not_a_sweep() -> None:
    # §9: "The sweep must not be accepted if price remains below the level for
    # more than 30 seconds. That is more likely acceptance than rejection."
    t = tick_frame([(0, 3001.0), (5, 2999.0), (40, 3001.5)])
    assert structure.sweeps(t, level=3000.0, side=1, atr=2.0).empty


def test_the_reclaim_must_clear_the_level_by_delta_not_merely_touch_it() -> None:
    # delta = max(2 ticks, 0.05 * ATR). At ATR 2.0 that is 0.10, so a return
    # to exactly 3000.0 is a touch and 3000.2 is a reclaim.
    touch = tick_frame([(0, 3001.0), (5, 2999.0), (10, 3000.0)])
    assert structure.sweeps(touch, level=3000.0, side=1, atr=2.0).empty
    clear = tick_frame([(0, 3001.0), (5, 2999.0), (10, 3000.2)])
    assert len(structure.sweeps(clear, level=3000.0, side=1, atr=2.0)) == 1


def test_delta_takes_the_atr_leg_when_it_is_the_larger() -> None:
    # At ATR 20 the ATR leg is 1.00, well above any tick floor, so a 0.5
    # reclaim is not enough.
    t = tick_frame([(0, 3001.0), (5, 2999.0), (10, 3000.5)])
    assert structure.sweeps(t, level=3000.0, side=1, atr=20.0).empty
    assert len(structure.sweeps(t, level=3000.0, side=1, atr=2.0)) == 1


def test_wick_is_measured_from_the_sweep_extreme_not_the_first_breach() -> None:
    # §9's limit sits at P_s + 0.50W. Measuring W from the first tick below
    # the level rather than from the extreme moves every entry price.
    t = tick_frame([(0, 3001.0), (5, 2999.5), (8, 2998.0), (15, 3001.0)])
    out = structure.sweeps(t, level=3000.0, side=1, atr=2.0)
    assert out.iloc[0]["swept_level"] == 2998.0
    assert out.iloc[0]["wick_w"] == pytest.approx(3.0)


def test_a_short_sweep_inverts_the_conditions() -> None:
    # Sweep of an Asian HIGH: price breaks above and is rejected back below.
    t = tick_frame([(0, 2999.0), (5, 3001.0), (15, 2998.5)])
    out = structure.sweeps(t, level=3000.0, side=-1, atr=2.0)
    assert len(out) == 1
    assert out.iloc[0]["swept_level"] == 3001.0


def test_price_never_reaching_the_level_produces_nothing() -> None:
    t = tick_frame([(0, 3001.0), (5, 3002.0), (10, 3003.0)])
    assert structure.sweeps(t, level=3000.0, side=1, atr=2.0).empty


def test_a_sweep_with_no_reclaim_at_all_produces_nothing() -> None:
    t = tick_frame([(0, 3001.0), (5, 2999.0), (10, 2998.0), (20, 2997.0)])
    assert structure.sweeps(t, level=3000.0, side=1, atr=2.0).empty


def test_two_separate_sweeps_are_two_candidates() -> None:
    t = tick_frame([(0, 3001.0), (5, 2999.0), (10, 3001.0),
                    (100, 2999.0), (110, 3001.0)])
    assert len(structure.sweeps(t, level=3000.0, side=1, atr=2.0)) == 2


def test_a_non_positive_atr_is_refused_rather_than_collapsing_delta() -> None:
    # ATR 0 would make the ATR leg 0 and silently fall back to the tick
    # floor, which is a different detector than the one §9 specifies.
    t = tick_frame([(0, 3001.0), (5, 2999.0), (10, 3001.0)])
    with pytest.raises(ValueError, match="atr"):
        structure.sweeps(t, level=3000.0, side=1, atr=0.0)


def test_an_unsorted_tick_frame_is_refused() -> None:
    # Reclaim timing is measured as a difference between rows. Out of order,
    # it returns a negative duration that compares as "within 30 seconds".
    t = tick_frame([(0, 3001.0), (20, 2999.0), (5, 3001.0)])
    with pytest.raises(ValueError, match="sorted"):
        structure.sweeps(t, level=3000.0, side=1, atr=2.0)
