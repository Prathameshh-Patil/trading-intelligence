"""The vol lane's three step-4 features, on frames where the answer is arithmetic.

`rv_parkinson`, `rv_slope` and `efficiency_ratio` -- Varad's half of
`features/portable.py`, and the inputs to M2. Written before M2's thresholds
were pre-committed and before any outcome was measured through them.

What gets tested hardest is the two places a plausible wrong answer hides: the
zero-denominator cases, where the natural fallback is a number that ranks the
deadest window in the month as its cleanest signal, and `rv_slope` being
RELATIVE, which is what makes one cut mean the same thing at both ends of an
archive whose median vol runs 5.66 to 17.04 bp.
"""

from __future__ import annotations

import numpy as np
from conftest import NEXT, SESSION, bars_at

from features import portable as pt


# --------------------------------------------------------------------------
# Parkinson
# --------------------------------------------------------------------------
def test_parkinson_is_basis_points_of_the_log_range() -> None:
    bars = bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6)
    rv = pt.rv_parkinson(bars, window="5min", min_bars=3).dropna()
    want = 1e4 * np.sqrt(np.log(101.0 / 99.0) ** 2 / (4 * np.log(2)))
    assert rv.round(6).eq(round(want, 6)).all()


def test_a_zero_range_bar_contributes_zero_and_is_not_floored() -> None:
    # Gold prints bars that open, close and never trade away. ln(H/L) = 0 is
    # the right variance contribution from one -- a bar that did not move, not
    # a bar with no answer -- so unlike every ratio in expansion.py this one
    # needs no floor and must not have acquired one.
    bars = bars_at(list(range(4)), [100.0] * 4, ranges=[0.0] * 4)
    rv = pt.rv_parkinson(bars, window="4min", min_bars=1)
    assert (rv == 0.0).all() and np.isfinite(rv).all()


def test_parkinson_does_not_reach_across_a_session_break() -> None:
    bars = bars_at(
        list(range(8)), [100.0] * 4 + [150.0] * 4,
        ranges=[0.0] * 4 + [3.0] * 4, session=[SESSION] * 4 + [NEXT] * 4,
    )
    rv = pt.rv_parkinson(bars, window="5min", min_bars=1)
    assert rv.iloc[3] == 0.0, "the quiet session stays quiet"
    assert rv.iloc[4] > 0.0, "the new session starts from its own first bar"


def test_parkinson_is_scale_free_in_the_price_level() -> None:
    # The whole reason it is in bp. The same PROPORTIONAL range at two price
    # levels 4x apart must give the same number, or the estimator carries the
    # archive's 2,733 -> 5,037 drift into every bucket that reads it.
    lo = bars_at(list(range(4)), [100.0] * 4, ranges=[2.0] * 4)
    hi = bars_at(list(range(4)), [400.0] * 4, ranges=[8.0] * 4)
    a = pt.rv_parkinson(lo, window="4min", min_bars=1)
    b = pt.rv_parkinson(hi, window="4min", min_bars=1)
    assert np.allclose(a.to_numpy(), b.to_numpy())


# --------------------------------------------------------------------------
# rv_slope -- the vol_state axis
# --------------------------------------------------------------------------
def test_the_slope_is_relative_so_one_cut_means_one_thing_at_any_vol_level() -> None:
    # A doubling of volatility reads +1.0 whether it starts at 5 bp or at 20.
    # A raw bp change would read four times larger in the loud regime, and a
    # fixed cut would then select the loud months and call it a state.
    quiet = bars_at(list(range(8)), [100.0] * 8, ranges=[0.5] * 4 + [1.0] * 4)
    loud = bars_at(list(range(8)), [100.0] * 8, ranges=[2.0] * 4 + [4.0] * 4)
    a = pt.rv_slope(quiet, window="4min", min_bars=1).iloc[-1]
    b = pt.rv_slope(loud, window="4min", min_bars=1).iloc[-1]
    assert a > 0 and b > 0
    # Agreement is to ~1e-4 relative, not exact, and the residual is real
    # rather than floating point: `ln(H/L)` is linear in the range only to
    # first order, so a 4% bar carries 1.3e-4 more log-range per unit than a
    # 0.5% one. That is the size of the effect this feature is NOT scale-free
    # against, measured rather than assumed, and it is four orders of magnitude
    # below the vol changes M2 is looking for.
    assert abs(a - b) / a < 1e-3, "same proportional expansion, same number"


def test_the_slope_is_signed_so_expanding_and_contracting_are_two_states() -> None:
    up = bars_at(list(range(8)), [100.0] * 8, ranges=[0.5] * 4 + [2.0] * 4)
    down = bars_at(list(range(8)), [100.0] * 8, ranges=[2.0] * 4 + [0.5] * 4)
    assert pt.rv_slope(up, window="4min", min_bars=1).iloc[-1] > 0
    assert pt.rv_slope(down, window="4min", min_bars=1).iloc[-1] < 0


def test_a_window_starting_from_no_volatility_is_nan_not_infinite() -> None:
    # Dividing an expansion by a zero starting vol is `inf`, which sorts to the
    # top of any EXPANDING screen and would make the deadest opening in the
    # month its strongest signal.
    bars = bars_at(list(range(8)), [100.0] * 8, ranges=[0.0] * 4 + [2.0] * 4)
    s = pt.rv_slope(bars, window="4min", min_bars=1)
    assert not np.isinf(s.to_numpy()).any()
    # Bars 0-6 all look back to a window with zero volatility in it.
    assert s.iloc[:7].isna().all()
    # Bar 7 is the first whose lookback window carries real range, and it is a
    # clean doubling -- 60.06 bp to 120.12 -- so the guard costs nothing once
    # there is something to divide by.
    assert s.iloc[7] == 1.0


# --------------------------------------------------------------------------
# efficiency_ratio
# --------------------------------------------------------------------------
def test_a_straight_line_is_perfectly_efficient() -> None:
    bars = bars_at(list(range(6)), [100.0 + i for i in range(6)])
    assert pt.efficiency_ratio(bars, window="6min", min_bars=2).iloc[-1] == 1.0


def test_ground_covered_twice_is_inefficient() -> None:
    bars = bars_at(list(range(5)), [100.0, 101.0, 100.0, 101.0, 100.0])
    # net 0 over a path of 4: the window went nowhere the hard way.
    assert pt.efficiency_ratio(bars, window="5min", min_bars=2).iloc[-1] == 0.0


def test_a_window_that_never_moved_is_nan_not_perfect() -> None:
    # 0/0. Returning 1.0 would rank the deadest hour of the month as its
    # cleanest trend, which is the exact inversion of what the feature is for.
    bars = bars_at(list(range(5)), [100.0] * 5)
    assert pt.efficiency_ratio(bars, window="5min", min_bars=2).isna().all()


def test_efficiency_is_dimensionless_and_transfers_untouched() -> None:
    lo = bars_at(list(range(5)), [100.0, 101.0, 100.5, 102.0, 103.0])
    hi = bars_at(list(range(5)), [400.0, 404.0, 402.0, 408.0, 412.0])
    a = pt.efficiency_ratio(lo, window="5min", min_bars=2)
    b = pt.efficiency_ratio(hi, window="5min", min_bars=2)
    assert np.allclose(a.dropna().to_numpy(), b.dropna().to_numpy())


def test_none_of_the_three_reads_a_bar_later_than_its_own() -> None:
    # The lookahead check every feature in this repo carries: truncating the
    # frame must not change any value that was already computable.
    bars = bars_at(list(range(12)), [100.0 + (i % 4) for i in range(12)],
                   ranges=[1.0 + (i % 3) for i in range(12)])
    for fn in (pt.rv_parkinson, pt.rv_slope, pt.efficiency_ratio):
        full = fn(bars, window="5min", min_bars=2)
        cut = fn(bars.iloc[:8], window="5min", min_bars=2)
        assert np.allclose(
            full.iloc[:8].to_numpy(), cut.to_numpy(), equal_nan=True
        ), f"{fn.__name__} reads forward"
