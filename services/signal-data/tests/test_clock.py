"""The clock axis: phase, event proximity, anchors, and M3 over them.

`plans/team/strategy-split.md` §4, the Prathamesh column. What is tested here
is not arithmetic -- a cumulative maximum needs no defence -- but the four
places this lane can produce a plausible number that is wrong:

  * a phase boundary that does not move with DST, pooling London and
    London-NY for five months of the archive;
  * an event calendar derived from a rule instead of transcribed, which on
    this archive marks a quiet Friday as payrolls and files the actual release
    in the null;
  * an anchor that reads the session's own future, which is invisible in every
    dtype and shape check and perfect in every result;
  * a phase name that never matches, which reports as a phase with no edge.

Every one of those returns a full, correctly-typed, entirely reasonable Series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import bars_at

import backtest as bt
import calendars as cal
import strategies as st
from features import portable as pt
from instruments import GC, Instrument


def utc_bars(stamps: list[str], closes: list[float] | None = None, session: str = "s") -> pd.DataFrame:
    """Bars at explicit UTC instants -- conftest's builder is pinned to one July
    session, and half of what is tested here is what happens in January."""
    idx = pd.DatetimeIndex([pd.Timestamp(s) for s in stamps])
    c = pd.Series(closes if closes is not None else [100.0] * len(idx), index=idx, dtype="float64")
    return pd.DataFrame(
        {"open": c, "high": c, "low": c, "close": c, "volume": 100, "delta": 0,
         "trades": 10, "session": session},
        index=idx,
    )


# --------------------------------------------------------------------------
# session_phase -- the boundaries, and the DST decision
# --------------------------------------------------------------------------
def test_each_of_the_six_phases_is_reachable_at_its_own_et_time() -> None:
    # One bar per phase, mid-interval, in July so ET is EDT (UTC-4).
    got = pt.session_phase(
        utc_bars([
            "2026-07-16T04:00:00Z",  # 00:00 ET -- Asia, after midnight
            "2026-07-16T06:30:00Z",  # 02:30 ET -- Asia-London
            "2026-07-16T09:00:00Z",  # 05:00 ET -- London
            "2026-07-16T12:30:00Z",  # 08:30 ET -- London-NY
            "2026-07-16T15:00:00Z",  # 11:00 ET -- NY
            "2026-07-16T19:00:00Z",  # 15:00 ET -- NY-Asia
            "2026-07-16T23:00:00Z",  # 19:00 ET -- Asia, before midnight
        ]),
        GC,
    )
    assert list(got) == ["Asia", "Asia-London", "London", "London-NY", "NY", "NY-Asia", "Asia"]


def test_asia_spans_midnight_as_one_phase_not_two() -> None:
    # 19:00 and 00:00 ET are the same liquidity regime on two calendar dates.
    # Cutting at midnight would file one regime under two bucket keys and make
    # reach.py report each half on half the sample.
    got = pt.session_phase(utc_bars(["2026-07-16T23:59:00Z", "2026-07-17T00:01:00Z"]), GC)
    assert list(got) == ["Asia", "Asia"]


def test_the_boundaries_are_inclusive_on_the_left() -> None:
    # 09:30 ET belongs to NY, not to London-NY. An off-by-one at a boundary is
    # a handful of bars per session and it is exactly the opening bars.
    edges = pt.session_phase(
        utc_bars([
            "2026-07-16T13:29:00Z",  # 09:29 ET
            "2026-07-16T13:30:00Z",  # 09:30 ET
            "2026-07-16T17:29:00Z",  # 13:29 ET
            "2026-07-16T17:30:00Z",  # 13:30 ET
        ]),
        GC,
    )
    assert list(edges) == ["London-NY", "NY", "NY", "NY-Asia"]


def test_the_same_utc_instant_is_a_different_phase_in_january() -> None:
    # **This is the pre-commitment, asserted.** The boundary is 08:00 in New
    # York, and New York moves. Freezing the UTC number instead would call this
    # January bar London-NY on both sides of the year and pool the London hour
    # into the NY-open bucket for 2025-11..2026-03.
    july = pt.session_phase(utc_bars(["2026-07-16T12:00:00Z"]), GC)
    january = pt.session_phase(utc_bars(["2026-01-15T12:00:00Z"]), GC)
    assert july.iloc[0] == "London-NY", "12:00 UTC is 08:00 EDT"
    assert january.iloc[0] == "London", "12:00 UTC is 07:00 EST -- and 07:00 is not the NY handoff"


def test_every_phase_is_a_category_even_when_the_frame_never_visits_it() -> None:
    # A phase missing from a result table is a finding. A phase missing from
    # the table's INDEX is a hole, and nothing downstream can tell that the
    # question was never asked.
    got = pt.session_phase(utc_bars(["2026-07-16T15:00:00Z"]), GC)
    assert list(got.cat.categories) == list(pt.PHASES)
    assert got.groupby(got, observed=False).size().sum() == 1
    assert len(got.groupby(got, observed=False).size()) == 6


def test_a_naive_index_raises_rather_than_being_read_as_utc() -> None:
    naive = utc_bars(["2026-07-16T15:00:00Z"])
    naive.index = pd.DatetimeIndex(naive.index).tz_localize(None)
    with pytest.raises(ValueError, match="naive"):
        pt.session_phase(naive, GC)


def test_the_phase_column_is_the_same_on_a_second_instrument() -> None:
    # The admission rule for portable.py: computable on both, and the same on
    # both. The phases are a fact about gold's global liquidity, not about a
    # venue -- which is the whole reason this feature is allowed in this file.
    spot = Instrument("XAUUSD-fixture", 0.01, None, pd.Timedelta(0), ("prior_close",), False)
    bars = utc_bars(["2026-07-16T12:00:00Z", "2026-01-15T12:00:00Z"])
    pd.testing.assert_series_equal(pt.session_phase(bars, GC), pt.session_phase(bars, spot))


# --------------------------------------------------------------------------
# The calendar -- transcribed, and the shutdown proves it
# --------------------------------------------------------------------------
def test_the_calendar_loads_sorted_unique_and_in_utc() -> None:
    idx = cal.load()
    assert idx.tz is not None and str(idx.tz) == "UTC"
    assert idx.is_monotonic_increasing
    assert idx.is_unique


def test_the_release_times_follow_et_across_dst_not_a_fixed_utc_hour() -> None:
    # 08:30 in Washington is 12:30 UTC in summer and 13:30 UTC in winter. A
    # calendar stored in UTC would put the winter releases an hour early, which
    # at +/-15 minutes misses the release bar entirely.
    idx = cal.load()
    summer = idx[idx.strftime("%Y-%m-%d") == "2025-07-03"]
    winter = idx[idx.strftime("%Y-%m-%d") == "2026-01-09"]
    assert summer[0].strftime("%H:%M") == "12:30"
    assert winter[0].strftime("%H:%M") == "13:30"


def test_the_2025_shutdown_gap_is_present_because_the_dates_are_transcribed() -> None:
    # **The single most valuable assertion in this file.** A first-Friday rule
    # invents an Employment Situation on 2025-10-03 -- a quiet Friday -- and
    # has nothing on 2025-11-20, where September's report actually landed.
    # Both errors are silent and they run in opposite directions: a null
    # polluted with a real release, and an event cell built on a normal day.
    days = set(cal.load().strftime("%Y-%m-%d"))
    assert "2025-10-03" not in days, "the rule's phantom payroll; the schedule has none"
    assert "2025-11-20" in days, "September 2025's Employment Situation, seven weeks late"
    assert "2025-10-24" in days, "September 2025 CPI, out of its usual mid-month slot"


def test_coverage_refuses_bars_the_calendar_has_never_heard_of() -> None:
    # The failure this exists for: an uncovered month returns all-False from
    # event_proximity, which is byte-identical to a month where nothing was
    # scheduled. Only one of those is a measurement.
    cal.require_coverage(utc_bars(["2026-07-16T12:00:00Z"]))
    with pytest.raises(ValueError, match="calendar covers"):
        cal.require_coverage(utc_bars(["2024-07-16T12:00:00Z"]))
    with pytest.raises(ValueError, match="calendar covers"):
        cal.require_coverage(utc_bars(["2027-07-16T12:00:00Z"]))


def test_an_unknown_event_type_raises_rather_than_being_carried(tmp_path) -> None:
    bad = tmp_path / "us_releases.csv"
    bad.write_text("timestamp_et,event,source\n2025-01-10T08:30:00,nonfarm_whisper,rumour\n")
    with pytest.raises(ValueError, match="unknown event types"):
        cal.load(bad)


# --------------------------------------------------------------------------
# event_proximity -- the window, and the two ways it can be silently empty
# --------------------------------------------------------------------------
def test_the_window_is_symmetric_and_closed_at_its_edges() -> None:
    release = pd.DatetimeIndex([pd.Timestamp("2026-07-16T12:30:00Z")])
    bars = utc_bars([
        "2026-07-16T12:14:00Z",  # -16 min
        "2026-07-16T12:15:00Z",  # -15, the edge
        "2026-07-16T12:30:00Z",  # the release
        "2026-07-16T12:45:00Z",  # +15, the edge
        "2026-07-16T12:46:00Z",  # +16
    ])
    got = pt.event_proximity(bars, release, window_minutes=15)
    assert list(got) == [False, True, True, True, False]


def test_proximity_takes_the_nearest_release_on_either_side() -> None:
    # A bar between two releases is near the closer one. Scanning forward only
    # would call the ten minutes after a payroll print "quiet".
    two = pd.DatetimeIndex([pd.Timestamp("2026-07-16T12:30:00Z"), pd.Timestamp("2026-07-16T18:00:00Z")])
    got = pt.event_proximity(utc_bars(["2026-07-16T12:40:00Z", "2026-07-16T15:00:00Z"]), two, window_minutes=15)
    assert list(got) == [True, False]


def test_an_empty_calendar_raises_rather_than_marking_everything_quiet() -> None:
    with pytest.raises(ValueError, match="empty release calendar"):
        pt.event_proximity(
            utc_bars(["2026-07-16T12:30:00Z"]), pd.DatetimeIndex([], dtype="datetime64[ns, UTC]"), window_minutes=15
        )


def test_a_zero_or_negative_window_raises() -> None:
    release = pd.DatetimeIndex([pd.Timestamp("2026-07-16T12:30:00Z")])
    for bad in (0, -15):
        with pytest.raises(ValueError, match="must be positive"):
            pt.event_proximity(utc_bars(["2026-07-16T12:30:00Z"]), release, window_minutes=bad)


def test_proximity_is_the_same_answer_at_any_index_resolution() -> None:
    # **A caught bug, pinned.** `DatetimeIndex.asi8` returns the index's OWN
    # unit, and pandas infers that from how the index was built: microseconds
    # from `pd.Timestamp`, nanoseconds off `read_parquet`. Comparing those
    # integers to a nanosecond window divides every gap by a thousand, so a bar
    # four hours from a release reads as fourteen seconds from it -- and the
    # event arm fires on every bar in the archive while still returning a
    # perfectly well-formed boolean Series.
    release = pd.DatetimeIndex([pd.Timestamp("2026-07-16T12:30:00Z")])
    far = ["2026-07-16T12:30:00Z", "2026-07-16T16:30:00Z"]
    answers = set()
    for unit in ("s", "ms", "us", "ns"):
        bars = utc_bars(far)
        bars.index = pd.DatetimeIndex(bars.index).as_unit(unit)
        answers.add(tuple(pt.event_proximity(bars, release.as_unit(unit), window_minutes=15)))
    assert answers == {(True, False)}, "the window is 15 minutes at every resolution or none"


def test_the_real_calendar_marks_a_real_payroll_bar() -> None:
    # End to end on the shipped CSV: 2026-07-02 08:30 ET is 12:30 UTC.
    got = pt.event_proximity(
        utc_bars(["2026-07-02T12:31:00Z", "2026-07-02T16:00:00Z"]), cal.load(), window_minutes=15
    )
    assert list(got) == [True, False]


# --------------------------------------------------------------------------
# anchors -- every one of these is causal or it is a forecast
# --------------------------------------------------------------------------
def test_session_extremes_are_cumulative_not_the_sessions_final_answer() -> None:
    # The bug this is here for: groupby().max() broadcast back is the session's
    # closing high on every bar, same dtype, same shape, and a perfect predictor.
    bars = bars_at([0, 1, 2, 3], [100.0, 103.0, 101.0, 99.0], ranges=[0.0] * 4)
    got = pt.anchors(bars, GC)
    assert list(got["session_high"]) == [100.0, 103.0, 103.0, 103.0]
    assert list(got["session_low"]) == [100.0, 100.0, 100.0, 99.0]
    assert got["session_high"].iloc[0] != bars["high"].max(), "bar 0 cannot know bar 1's high"


def test_session_open_is_the_first_bars_open_and_prior_close_is_yesterdays_last() -> None:
    bars = bars_at(
        [0, 1, 2, 3],
        [100.0, 101.0, 200.0, 202.0],
        session=["d1", "d1", "d2", "d2"],
    )
    got = pt.anchors(bars, GC)
    assert list(got["session_open"]) == [100.0, 100.0, 200.0, 200.0]
    # NaN through the first session: there is no prior close on the archive's
    # first day, and reaching for the session's own close would be a perfect one.
    assert got["prior_close"].iloc[:2].isna().all()
    assert list(got["prior_close"].iloc[2:]) == [101.0, 101.0]


def test_the_opening_range_is_absent_until_it_has_closed() -> None:
    # A bar twelve minutes into the session cannot know the thirty-minute band.
    bars = bars_at([0, 12, 29, 30, 45], [100.0, 104.0, 98.0, 101.0, 107.0], ranges=[0.0] * 5)
    got = pt.anchors(bars, GC)
    assert got["opening_range_high"].iloc[:3].isna().all(), "still forming"
    assert list(got["opening_range_high"].iloc[3:]) == [104.0, 104.0]
    assert list(got["opening_range_low"].iloc[3:]) == [98.0, 98.0]
    assert 107.0 not in set(got["opening_range_high"].dropna()), "45m is outside the band"


def test_a_session_shorter_than_the_opening_range_has_no_opening_range() -> None:
    # Not a partial band. A thin holiday session that never completed thirty
    # minutes has no answer, and a 12-minute range reported as a 30-minute one
    # is a different quantity in the same column.
    got = pt.anchors(bars_at([0, 5, 12], [100.0, 104.0, 98.0]), GC)
    assert got["opening_range_high"].isna().all()


def test_twap_is_the_running_mean_over_the_bars_that_exist() -> None:
    # Minute 3 is missing -- no trades, so no price to weight. Filling it with
    # the previous close would weight a dead market as though it had traded.
    bars = bars_at([0, 1, 2, 4], [100.0, 102.0, 104.0, 110.0])
    got = pt.anchors(bars, GC)
    assert list(got["twap"]) == [100.0, 101.0, 102.0, 104.0]


def test_an_anchor_the_instrument_declares_but_nothing_computes_raises() -> None:
    # Silently returning the frame one column short is how a downstream .get()
    # turns a missing anchor into a default and reports it as a measurement.
    odd = Instrument("fixture", 0.10, None, pd.Timedelta(0), ("session_open", "london_fix"), False)
    with pytest.raises(ValueError, match="london_fix"):
        pt.anchors(bars_at([0, 1], [100.0, 101.0]), odd)


def test_anchors_returns_exactly_what_the_instrument_declares() -> None:
    lean = Instrument("fixture", 0.10, None, pd.Timedelta(0), ("prior_close", "twap"), False)
    got = pt.anchors(bars_at([0, 1], [100.0, 101.0]), lean)
    assert list(got.columns) == ["prior_close", "twap"]


# --------------------------------------------------------------------------
# M3 -- the two arms, separately and together
# --------------------------------------------------------------------------
NY_MORNING = ["2026-07-02T14:00:00Z", "2026-07-02T15:00:00Z"]  # 10:00, 11:00 ET -- both NY
PAYROLL = "2026-07-02T12:31:00Z"                               # 08:31 ET, on the release


def test_the_phase_arm_fires_only_inside_the_named_phases() -> None:
    bars = utc_bars(["2026-07-02T09:00:00Z", *NY_MORNING])  # London, then NY
    got = st.m3_session_event(bars, GC, phases=("NY",), event_window_minutes=0)
    assert list(got) == [0, 1, 1]


def test_the_signal_is_non_directional_and_never_short() -> None:
    # §4.4: all three Track B strategies return +1/0. A -1 here would make
    # backtest.evaluate produce a signed move for an unsigned claim.
    bars = utc_bars([*NY_MORNING, "2026-07-02T09:00:00Z"])
    got = st.m3_session_event(bars, GC, phases=("NY",), event_window_minutes=0)
    assert set(got.unique()) <= {0, 1}
    assert got.dtype == np.dtype("int64")


def test_the_event_arm_runs_alone_when_no_phase_is_named() -> None:
    bars = utc_bars([PAYROLL, "2026-07-02T16:00:00Z"])
    got = st.m3_session_event(bars, GC, phases=(), event_window_minutes=15)
    assert list(got) == [1, 0]


def test_the_two_arms_are_a_union() -> None:
    # 08:31 ET is London-NY and on the payroll release; 10:00 ET is NY and
    # quiet. Naming NY only, the event arm is what picks up the first bar.
    bars = utc_bars([PAYROLL, NY_MORNING[1]])
    assert list(st.m3_session_event(bars, GC, phases=("NY",), event_window_minutes=0)) == [0, 1]
    assert list(st.m3_session_event(bars, GC, phases=("NY",), event_window_minutes=15)) == [1, 1]


def test_a_misspelled_phase_raises_rather_than_never_firing() -> None:
    # A phase that never matches returns all zeros, which reads as "this phase
    # has no edge" -- a negative result manufactured by a typo.
    with pytest.raises(ValueError, match="unknown phases"):
        st.m3_session_event(utc_bars(NY_MORNING), GC, phases=("London-NY ",), event_window_minutes=0)
    with pytest.raises(ValueError, match="unknown phases"):
        st.m3_session_event(utc_bars(NY_MORNING), GC, phases=("Tokyo",), event_window_minutes=0)


def test_both_arms_off_raises() -> None:
    with pytest.raises(ValueError, match="both arms are off"):
        st.m3_session_event(utc_bars(NY_MORNING), GC, phases=(), event_window_minutes=0)


def test_m3_feeds_the_existing_backtest_unchanged() -> None:
    # The point of matching `(bars, *, thresholds) -> Series`: stages 5, 6, 8
    # do not change for this track (ARCHITECTURE §4.5), and that is the case
    # for the whole thing being cheap.
    stamps = [f"2026-07-02T{13 + m // 60:02d}:{m % 60:02d}:00Z" for m in range(60)]
    bars = utc_bars(stamps, [100.0 + i * 0.1 for i in range(60)])
    entries = st.m3_session_event(bars, GC, phases=("NY",), event_window_minutes=0)

    trades = bt.evaluate(bars, entries, GC, horizons=(5,))
    assert len(trades) > 0
    assert (trades["side"] == 1).all()
    assert bt.summarize(trades, GC, 5)["n"] > 0


# --------------------------------------------------------------------------
# The measurement path and the signal path must agree
# --------------------------------------------------------------------------
def test_m3_fires_on_exactly_the_bars_the_profile_groups_into_that_cell() -> None:
    # `m3_profile.py` measures by labelling every bar and GROUPING; M3 the
    # strategy selects by FIRING. If those two ever disagree, the archive
    # profile is describing a population the live signal does not take, and
    # nothing in either output would say so -- both are well-formed, both have
    # an N, and only one of them is the thing that gets traded.
    stamps = [f"2026-07-02T{h:02d}:{m:02d}:00Z" for h in range(6, 22) for m in (0, 30)]
    bars = utc_bars(stamps)
    phase = pt.session_phase(bars, GC)
    near = pt.event_proximity(bars, cal.load(), window_minutes=15)

    for phases in [("NY",), ("London", "London-NY"), pt.PHASES]:
        fired = st.m3_session_event(bars, GC, phases=phases, event_window_minutes=0) == 1
        pd.testing.assert_series_equal(
            fired, phase.isin(phases), check_names=False
        )
        both = st.m3_session_event(bars, GC, phases=phases, event_window_minutes=15) == 1
        pd.testing.assert_series_equal(
            both, phase.isin(phases) | near, check_names=False
        )
