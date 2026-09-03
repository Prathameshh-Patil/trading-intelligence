"""D2's Layer 3 features, on bars where the answer is arithmetic.

The ATR tests moved here with the function, from `test_regime_filter.py`.

What gets tested hardest is VWAP, because it is the only genuinely new
quantity in D2 and it has the two failure modes a session-anchored cumulative
has: carrying across the overnight break, and weighting by nothing when
volume is uniform, which makes it silently equal to a plain mean and hides a
missing weight.
"""

from __future__ import annotations

import numpy as np
from conftest import NEXT, SESSION, bars_at

from features import expansion as ex
from features import orderflow as of
from s1 import TICK


# --------------------------------------------------------------------------
# ATR -- moved from regime_filter on D2, same behaviour
# --------------------------------------------------------------------------
def test_atr_is_in_ticks_not_price() -> None:
    bars = bars_at(list(range(10)), [100.0] * 10, ranges=[2.0] * 10)
    assert ex.atr(bars, window="5min", min_bars=3).dropna().round(6).eq(20.0).all()


def test_atr_has_no_value_until_the_window_is_full() -> None:
    bars = bars_at(list(range(10)), [100.0] * 10, ranges=[2.0] * 10)
    a = ex.atr(bars, window="5min", min_bars=5)
    assert a.iloc[:4].isna().all()
    assert a.iloc[4:].notna().all()


def test_atr_does_not_measure_the_gap_across_a_session_break() -> None:
    bars = bars_at(
        list(range(8)),
        [100.0] * 4 + [150.0] * 4,
        ranges=[2.0] * 8,
        session=[SESSION] * 4 + [NEXT] * 4,
    )
    assert ex.atr(bars, window="5min", min_bars=1).iloc[4] == 20.0


def test_regime_filter_uses_the_same_atr() -> None:
    # The point of the move: one true-range calculation, not two that drift.
    from features import regime_filter as rf

    assert rf.atr is ex.atr


# --------------------------------------------------------------------------
# Bar range and body ratio
# --------------------------------------------------------------------------
def test_bar_range_is_ticks() -> None:
    bars = bars_at([0, 1, 2], [100.0] * 3, ranges=[0.5, 2.0, 6.0])
    assert list(ex.bar_range(bars).round(6)) == [5.0, 20.0, 60.0]


def test_body_ratio_spans_zero_to_one() -> None:
    # A bar that opens at its low and closes at its high is a full body; one
    # that opens and closes at the same price is a doji whatever it ranged.
    bars = bars_at([0, 1], [100.0, 100.0], ranges=[2.0, 2.0])
    full = bars.copy()
    full.loc[full.index[0], "open"] = 99.0
    full.loc[full.index[0], "close"] = 101.0
    r = ex.body_ratio(full)
    assert r.iloc[0] == 1.0, "open at the low, close at the high"
    assert r.iloc[1] == 0.0, "open equals close is a doji"


def test_a_zero_range_bar_is_zero_not_infinite() -> None:
    # Gold prints these: one price, never traded away. 0/0 must not be inf.
    bars = bars_at([0], [100.0], ranges=[0.0])
    assert ex.body_ratio(bars).iloc[0] == 0.0
    assert np.isfinite(ex.body_ratio(bars)).all()


# --------------------------------------------------------------------------
# VWAP
# --------------------------------------------------------------------------
def test_vwap_is_volume_weighted_and_not_a_plain_mean() -> None:
    # Two bars: one lot at 100, ninety-nine at 200. The mean is 150; VWAP is
    # 199. Uniform volume would make these equal and hide a missing weight.
    bars = bars_at([0, 1], [100.0, 200.0])
    bars["volume"] = [1, 99]
    v = of.vwap(bars)
    assert v.iloc[0] == 100.0
    assert round(v.iloc[1], 6) == 199.0
    assert v.iloc[1] != bars["close"].mean()


def test_vwap_uses_typical_price_not_close() -> None:
    # One bar ranging 2.0 around a close of 100: typical is (101+99+100)/3.
    bars = bars_at([0], [100.0], ranges=[2.0])
    assert round(of.vwap(bars).iloc[0], 6) == round((101.0 + 99.0 + 100.0) / 3, 6)


def test_vwap_reanchors_at_the_session_boundary() -> None:
    # Session one trades at 100, session two at 200. Session two's first bar
    # must read 200, not a blend of the two sessions.
    bars = bars_at(
        list(range(6)), [100.0] * 3 + [200.0] * 3, session=[SESSION] * 3 + [NEXT] * 3
    )
    v = of.vwap(bars)
    assert v.iloc[2] == 100.0
    assert v.iloc[3] == 200.0, (
        "an overnight-anchored VWAP describes a session that has ended"
    )


def test_vwap_distance_is_signed_ticks() -> None:
    bars = bars_at([0, 1], [100.0, 100.5])
    d = of.vwap_distance(bars)
    assert d.iloc[0] == 0.0, "the first bar of a session sits on its own VWAP"
    assert d.iloc[1] > 0, "a close above the session average is positive"
    assert round(d.iloc[1], 6) == round(
        (bars["close"].iloc[1] - of.vwap(bars).iloc[1]) / TICK, 6
    )


def test_a_zero_volume_bar_is_nan_not_a_division_by_zero() -> None:
    bars = bars_at([0, 1], [100.0, 100.0])
    bars["volume"] = [0, 0]
    assert of.vwap(bars).isna().all(), (
        "a bar with no trades is a data fault, reported not smoothed"
    )


# --------------------------------------------------------------------------
# The re-exports D2 asks for -- imported, not re-derived
# --------------------------------------------------------------------------
def test_orderflow_reexports_the_tested_originals() -> None:
    import strategies as st

    assert of.delta_z is st.delta_z
    assert of.cvd_slope is st.cvd_slope
    assert of.absorption is st.absorption


def test_absorption_is_still_contracts_per_tick() -> None:
    # Guarding the re-export, not re-testing strategies.py: 400 contracts of
    # one-sided flow across a 20-tick bar is 20 contracts per tick.
    bars = bars_at([0], [100.0], deltas=[400], ranges=[2.0])
    assert of.absorption(bars).iloc[0] == 20.0
