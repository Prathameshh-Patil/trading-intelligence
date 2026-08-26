"""Stage 2's two load-bearing guarantees, plus the arithmetic underneath them.

The guarantees are the reason regimes.py is allowed to produce labels that
select.py will later trust:

  * every feature reads BACKWARD only -- a bar's row cannot move when a later
    bar changes, or the whole design leaks (module docstring, §2);
  * the walk-forward split cuts on the SESSION, not the ET calendar date.

Nothing here reads data/gc_trades.parquet -- it is gitignored and lives on
Prathamesh's machine, not in this working copy. Frames are built by hand from
conftest, where the answer is known by construction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import bars_at, noise

import regimes

# OPEN is 22:00Z = 18:00 ET on 15 Jul, the Globex open of session 2026-07-16.
# One day later, minute 1440, is 18:00 ET on 16 Jul -- already session 07-17
# while the ET calendar still reads 07-16. That gap is the whole point below.
ROLL = 1440
SPLIT = pd.Timestamp("2026-07-17").date()


def frame(minutes: list[int]) -> pd.DataFrame:
    closes = [4000.0 + i for i in range(len(minutes))]
    return bars_at(minutes, closes, deltas=noise(len(minutes)), ranges=[2.0] * len(minutes))


# --------------------------------------------------------------------------
# The walk-forward split (§6.4)
# --------------------------------------------------------------------------
def test_the_split_cuts_on_the_session_not_the_calendar_date() -> None:
    # Two bars in session 07-16, three after the 18:00 ET roll into 07-17 but
    # still dated 07-16 in ET, one plainly inside 07-17.
    minutes = [0, 1380, ROLL, ROLL + 60, ROLL + 120, ROLL + 360]
    feat = regimes.resample_bars(frame(minutes), "5min")
    mask = regimes.fit_mask_before(feat, "window", SPLIT)

    assert list(feat["session"]) == [
        pd.Timestamp("2026-07-16").date(),
        pd.Timestamp("2026-07-16").date(),
        SPLIT, SPLIT, SPLIT, SPLIT,
    ]
    assert mask.tolist() == [True, True, False, False, False, False]


def test_the_calendar_date_rule_it_replaced_would_have_leaked() -> None:
    # Pins the bug rather than the fix: three bars belong to the split session
    # yet carry the previous ET date, so a calendar cut fits on them.
    minutes = [0, 1380, ROLL, ROLL + 60, ROLL + 120, ROLL + 360]
    feat = regimes.resample_bars(frame(minutes), "5min")
    et_date = pd.DatetimeIndex(feat.index).tz_convert(regimes.DISPLAY_TZ).date

    leaked = (et_date < SPLIT) & ~regimes.fit_mask_before(feat, "window", SPLIT).to_numpy()
    assert leaked.sum() == 3


def test_a_session_level_split_reads_the_index() -> None:
    feat = pd.DataFrame(
        {"realized_vol": [1.0, 2.0, 3.0]},
        index=pd.Index([pd.Timestamp(d).date() for d in ("2026-07-15", "2026-07-16", "2026-07-17")],
                       name="session"),
    )
    assert regimes.fit_mask_before(feat, "session", SPLIT).tolist() == [True, True, False]


# --------------------------------------------------------------------------
# Trailing-only features (§2's leakage rule)
# --------------------------------------------------------------------------
def test_no_feature_can_see_a_later_bar() -> None:
    """Truncating the frame must not move a single surviving row.

    If it does, some feature is reading forward -- a rolling window that
    became center=True, or a slice that ran past `i`.
    """
    bars_1min = frame(list(range(200)))
    regime_bars = regimes.resample_bars(bars_1min, "5min")
    cut = len(regime_bars) - 6

    full = regimes.window_features(bars_1min, regime_bars, window=3, vol_window_min=15)
    end = regime_bars.index[cut - 1]
    part = regimes.window_features(
        bars_1min.loc[:end], regime_bars.iloc[:cut], window=3, vol_window_min=15
    )
    pd.testing.assert_frame_equal(full.iloc[:cut], part)


def test_a_window_may_not_straddle_the_session_reset() -> None:
    """CVD restarts at ~0 each session, so a window holding both sides reads
    the reset as a move. In the committed July labels this produced the eight
    largest cvd_slope values in the month -- up to +505 on bars whose CVD was
    negative. The rows are dropped, not fudged.
    """
    bars_1min = frame(list(range(40)) + list(range(ROLL, ROLL + 40)))
    regime_bars = regimes.resample_bars(bars_1min, "5min")
    feat = regimes.window_features(bars_1min, regime_bars, window=4, vol_window_min=15)

    first_of_new = int(np.flatnonzero(feat["session"].to_numpy() == SPLIT)[0])
    # The new session needs 4 of its own bars before a window closes.
    assert feat["cvd_slope"].iloc[first_of_new:first_of_new + 3].isna().all()
    assert not np.isnan(feat["cvd_slope"].iloc[first_of_new + 3])


def test_the_first_bars_of_a_window_have_no_features_yet() -> None:
    bars_1min = frame(list(range(60)))
    regime_bars = regimes.resample_bars(bars_1min, "5min")
    feat = regimes.window_features(bars_1min, regime_bars, window=4, vol_window_min=15)
    # A trailing window of 4 cannot be filled before the 4th bar.
    assert feat["cvd_slope"].iloc[:3].isna().all()
    assert feat["cvd_slope"].iloc[3:].notna().all()


# --------------------------------------------------------------------------
# Resampling -- CVD must agree with the delta of the bars it was built from
# --------------------------------------------------------------------------
def test_resampled_cvd_is_rederived_not_downsampled() -> None:
    bars_1min = frame([0, 1, 2, 6, 7, 12])
    agg = regimes.resample_bars(bars_1min, "5min")
    assert len(agg) == 3
    assert agg["delta"].sum() == bars_1min["delta"].sum()
    assert agg["cvd"].iloc[-1] == agg["delta"].sum()  # one session, so cumsum ends at the total


def test_cvd_resets_at_the_session_boundary() -> None:
    agg = regimes.resample_bars(frame([0, 60, ROLL, ROLL + 60]), "5min")
    assert agg["cvd"].iloc[2] == agg["delta"].iloc[2]  # first bar of session 07-17


def test_empty_bins_are_dropped_so_row_offsets_are_not_minutes() -> None:
    # The trap s1.minute_bars documents, inherited here: bar N+1 is not
    # bar_size after bar N. Anything measuring a horizon must slice on time.
    agg = regimes.resample_bars(frame([0, 600]), "5min")
    assert len(agg) == 2
    assert (agg.index[1] - agg.index[0]) == pd.Timedelta(minutes=600)


# --------------------------------------------------------------------------
# Session phase -- boundaries, on the 18:00 ET open used everywhere else
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("et_hour", "phase"),
    [(18, "asia"), (23, "asia"), (2, "asia"), (3, "london"), (7, "london"),
     (8, "ny"), (16, "ny")],
)
def test_session_phase_boundaries(et_hour: int, phase: str) -> None:
    ts = pd.Timestamp(f"2026-07-16T{et_hour:02d}:00:00", tz=regimes.DISPLAY_TZ)
    assert regimes.session_phase(pd.DatetimeIndex([ts])).iloc[0] == phase


# --------------------------------------------------------------------------
# The arithmetic, at the edges where it is allowed to give up
# --------------------------------------------------------------------------
def test_persistence_is_one_when_every_trade_pushed_the_same_way() -> None:
    assert regimes._cvd_persistence(np.array([5, 7, 3])) == pytest.approx(1.0)


def test_persistence_is_zero_when_the_pushes_cancelled() -> None:
    assert regimes._cvd_persistence(np.array([5, -5])) == pytest.approx(0.0)


def test_persistence_is_nan_rather_than_zero_when_nothing_traded() -> None:
    # 0/0. Returning 0.0 here would read as "perfectly balanced flow" and put
    # a dead bar in the same cluster as a genuinely two-sided one.
    assert np.isnan(regimes._cvd_persistence(np.array([0, 0])))


def test_efficiency_is_nan_on_a_bar_with_no_range() -> None:
    flat = np.array([4000.0, 4000.0])
    assert np.isnan(regimes._efficiency(flat, flat, flat))


def test_efficiency_is_one_when_the_move_kept_the_whole_range() -> None:
    straight = np.array([4000.0, 4001.0, 4002.0])
    assert regimes._efficiency(straight, straight, straight) == pytest.approx(1.0)


def test_efficiency_is_zero_when_price_came_back() -> None:
    trip = np.array([4000.0, 4002.0, 4000.0])
    assert regimes._efficiency(trip, trip, trip) == pytest.approx(0.0)


def test_efficiency_is_the_move_over_the_range_it_travelled() -> None:
    close = np.array([4000.0, 4001.0])
    high, low = np.array([4000.0, 4002.0]), np.array([4000.0, 4001.0])
    assert regimes._efficiency(close, high, low) == pytest.approx(0.5)


def test_the_spec_formula_is_not_a_feature() -> None:
    """Pins Varad's 26 Aug call, not just its consequence.

    abs(CVD)/range was dropped as a redundancy: its order-flow counterpart is
    cvd_persistence, with which it correlated at r = 0.803 over the July
    labels. It does not come back without that being revisited.
    """
    assert regimes.FEATURE_COLS == [
        "realized_vol", "cvd_slope", "cvd_persistence", "price_efficiency",
    ]


def test_slope_needs_two_points() -> None:
    assert np.isnan(regimes._slope(np.array([1.0])))
    assert regimes._slope(np.array([0.0, 2.0, 4.0])) == pytest.approx(2.0)


# --------------------------------------------------------------------------
# The dwell penalty -- regimes that outlive the trade they selected
# --------------------------------------------------------------------------
# Three bars that clearly want cluster 0, one that mildly wants cluster 1,
# three more that want 0. The middle bar is the one-bar blip a dwell penalty
# is supposed to absorb.
BLIP = np.array([[0.0, 5.0]] * 3 + [[1.0, 0.0]] + [[0.0, 5.0]] * 3)
ONE_SESSION = np.array([SPLIT] * 7)


def test_lambda_zero_is_exactly_plain_kmeans() -> None:
    """The escape hatch has to be free, or nobody can compare against it."""
    rng = np.random.default_rng(0)
    dist = rng.random((200, 3))
    got = regimes.dwell_labels(dist, np.array([SPLIT] * 200), 0.0)
    assert (got == dist.argmin(axis=1)).all()


def test_a_penalty_absorbs_a_one_bar_blip() -> None:
    assert regimes.dwell_labels(BLIP, ONE_SESSION, 0.0).tolist() == [0, 0, 0, 1, 0, 0, 0]
    assert regimes.dwell_labels(BLIP, ONE_SESSION, 2.0).tolist() == [0] * 7


def test_the_penalty_does_not_carry_across_a_session() -> None:
    """A switching cost across the overnight halt asserts a continuity the
    tape does not have -- and it showed: carried, the label changed across a
    boundary 4.5% of the time against plain KMeans's 45.5%.
    """
    split_at_blip = np.array([SPLIT] * 3 + [pd.Timestamp("2026-07-18").date()] * 4)
    got = regimes.dwell_labels(BLIP, split_at_blip, 2.0)
    assert got[3] == 1, "the first bar of a session is free to pick any regime"


def test_the_labels_are_causal() -> None:
    """The whole reason this is a forward pass and not a Viterbi decode.

    Truncate the tape and every bar that survives must keep its label -- a
    full-sequence decode fails this, which is why one is not used.
    """
    rng = np.random.default_rng(1)
    dist = rng.random((300, 3))
    sess = np.array([SPLIT] * 300)
    full = regimes.dwell_labels(dist, sess, 0.5)
    for cut in (17, 128, 299):
        assert (regimes.dwell_labels(dist[:cut], sess[:cut], 0.5) == full[:cut]).all()


def test_a_bigger_penalty_never_means_more_switching() -> None:
    rng = np.random.default_rng(2)
    dist = rng.random((500, 3))
    sess = np.array([SPLIT] * 500)
    switches = [
        int((np.diff(regimes.dwell_labels(dist, sess, lam)) != 0).sum())
        for lam in (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
    ]
    assert switches == sorted(switches, reverse=True), switches
    assert switches[-1] < switches[0]


def test_the_default_is_the_measured_one() -> None:
    # 0.5 buys 30min regime survival 46.2% -> 54.0% for a silhouette cost of
    # 0.305 -> 0.290. Past it the clusters dissolve into the smoothing.
    assert regimes.DEFAULT_DWELL_LAMBDA == 0.5


def test_run_lengths_counts_what_the_penalty_moves() -> None:
    labels = pd.Series([0.0, 0.0, 1.0, 1.0, 1.0, 0.0])
    valid = pd.Series([True] * 6)
    assert regimes.run_lengths(labels, valid) == {
        "n_runs": 3, "median_bars": 2.0, "longest_bars": 3, "flip_pct": 33.3,
    }


def test_fit_regimes_carries_the_penalty_and_records_it() -> None:
    bars_1min = frame(list(range(200)) + list(range(ROLL, ROLL + 200)))
    regime_bars = regimes.resample_bars(bars_1min, "5min")
    feat = regimes.window_features(bars_1min, regime_bars, window=3, vol_window_min=15)
    mask = regimes.fit_mask_before(feat, "window", SPLIT)

    plain = regimes.fit_regimes(feat, "window", 2, mask, 0, False, dwell_lambda=0.0)
    sticky = regimes.fit_regimes(feat, "window", 2, mask, 0, False, dwell_lambda=2.0)

    assert plain["dwell_lambda"] == 0.0 and sticky["dwell_lambda"] == 2.0
    v = plain["valid"]
    assert regimes.run_lengths(sticky["labels"], v)["n_runs"] <= \
        regimes.run_lengths(plain["labels"], v)["n_runs"]


# --------------------------------------------------------------------------
# Clustering -- the flag that exists because session dummies dominate
# --------------------------------------------------------------------------
def test_session_dummies_enter_the_matrix_only_when_asked() -> None:
    bars_1min = frame(list(range(200)))
    feat = regimes.window_features(bars_1min, regimes.resample_bars(bars_1min, "5min"), 3, 15)

    with_phase = regimes.build_feature_matrix(feat, "window", include_session_phase=True)
    without = regimes.build_feature_matrix(feat, "window", include_session_phase=False)

    assert list(without.columns) == regimes.FEATURE_COLS
    assert set(with_phase.columns) - set(without.columns) == {
        "session_asia", "session_london", "session_ny",
    }


def test_an_absent_session_phase_still_gets_its_column() -> None:
    # One session of Asia-only bars must not produce a narrower matrix than a
    # month does, or a scaler fitted on one frame cannot transform the other.
    bars_1min = frame(list(range(100)))
    feat = regimes.window_features(bars_1min, regimes.resample_bars(bars_1min, "5min"), 3, 15)
    assert set(feat["session_phase"]) == {"asia"}
    X = regimes.build_feature_matrix(feat, "window", include_session_phase=True)
    assert {"session_asia", "session_london", "session_ny"} <= set(X.columns)


def test_only_pre_split_rows_reach_the_scaler() -> None:
    """The §6.4 promise end to end: everything is labelled, nothing after the
    split moves where the cluster boundaries sit."""
    bars_1min = frame(list(range(200)) + list(range(ROLL, ROLL + 200)))
    regime_bars = regimes.resample_bars(bars_1min, "5min")
    feat = regimes.window_features(bars_1min, regime_bars, window=3, vol_window_min=15)
    mask = regimes.fit_mask_before(feat, "window", SPLIT)

    result = regimes.fit_regimes(feat, "window", k=2, fit_mask=mask, random_state=0,
                                 include_session_phase=False)

    assert result["walk_forward_safe"]
    assert not (result["fit_rows"] & ~mask).any()
    assert result["labels"][result["valid"]].notna().all()
    # Labelled on both sides of the split, fitted on only one.
    assert result["fit_rows"].sum() < result["valid"].sum()
