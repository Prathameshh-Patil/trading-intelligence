"""D3's four conditions, each on bars where the answer is known by hand.

The combiner is tested separately from the conditions, because the two ways
it can be wrong are different. A condition is wrong when it fires on the
wrong bar. The combiner is wrong when it counts a bar three conditions
disagree about as agreement -- which looks like a working signal engine right
up until the backtest.

Condition A is a stub by decision (Part B, `absorption_fade` dropped), so
there is a test pinning it to zeros. If it ever returns something, the
3-of-4 combiner stops being 3-of-3 and every number D3 reported changes
meaning.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from conftest import NEXT, SESSION, bars_at

from signals import engine as en


def set_bar(bars: pd.DataFrame, i: int, o: float, h: float, low: float, c: float) -> pd.DataFrame:
    """OHLC for one bar, overriding `bars_at`'s close-centred range.

    `bars_at` puts the open at the close, so every fixture bar has a zero
    body -- which is exactly the half of condition D that ATR cannot see.
    """
    bars.loc[bars.index[i], ["open", "high", "low", "close"]] = [o, h, low, c]
    return bars


# --------------------------------------------------------------------------
# Condition B -- delta divergence
# --------------------------------------------------------------------------
def test_divergence_goes_long_on_a_new_low_that_selling_did_not_confirm() -> None:
    # Price falls every bar; the selling behind it dries up. The last bar is
    # the window's low on the smallest delta in it -- textbook exhaustion.
    bars = bars_at(
        list(range(6)),
        [100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        deltas=[-50, -40, -30, -20, -10, -5],
    )
    assert en.delta_divergence(bars, window="20min", min_bars=3).iloc[-1] == 1


def test_divergence_is_flat_when_the_new_low_comes_on_the_heaviest_selling() -> None:
    # Same falling price, delta falling with it. That is a trend, not a
    # divergence, and it is the case a price-only rule would call long.
    bars = bars_at(
        list(range(6)),
        [100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        deltas=[-10, -20, -30, -40, -50, -60],
    )
    assert en.delta_divergence(bars, window="20min", min_bars=3).iloc[-1] == 0


def test_divergence_goes_short_on_a_new_high_that_buying_did_not_confirm() -> None:
    bars = bars_at(
        list(range(6)),
        [95.0, 96.0, 97.0, 98.0, 99.0, 100.0],
        deltas=[50, 40, 30, 20, 10, 5],
    )
    assert en.delta_divergence(bars, window="20min", min_bars=3).iloc[-1] == -1


def test_divergence_has_no_signal_before_the_window_is_full() -> None:
    bars = bars_at(
        list(range(6)),
        [100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        deltas=[-50, -40, -30, -20, -10, -5],
    )
    assert (en.delta_divergence(bars, window="20min", min_bars=4).iloc[:3] == 0).all()


def test_divergence_does_not_read_across_the_session_break() -> None:
    # The new session's first bars have no trailing context of their own, and
    # the previous session's low must not supply one.
    bars = bars_at(
        list(range(8)),
        [100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0],
        deltas=[-50, -40, -30, -20, -10, -5, -4, -3],
        session=[SESSION] * 4 + [NEXT] * 4,
    )
    assert (en.delta_divergence(bars, window="20min", min_bars=3).iloc[4:6] == 0).all()


# --------------------------------------------------------------------------
# Condition C -- CVD momentum shift
# --------------------------------------------------------------------------
def test_cvd_shift_fires_on_the_bar_the_slope_turns_positive() -> None:
    # CVD falls for four bars, then one bar of buying flips the trailing
    # slope. The flip is the signal, not the sign.
    bars = bars_at(list(range(6)), [100.0] * 6, deltas=[-10, -10, -10, -10, 30, 5])
    assert en.cvd_shift(bars, window="4min", min_bars=3).iloc[4] == 1


def test_cvd_shift_is_flat_while_the_slope_stays_positive() -> None:
    # The next bar has a stronger positive slope and no signal: this is a
    # shift detector, not a momentum reading.
    bars = bars_at(list(range(6)), [100.0] * 6, deltas=[-10, -10, -10, -10, 30, 5])
    assert en.cvd_shift(bars, window="4min", min_bars=3).iloc[5] == 0


def test_cvd_shift_fires_short_when_the_slope_turns_negative() -> None:
    bars = bars_at(list(range(6)), [100.0] * 6, deltas=[10, 10, 10, 10, -30, -5])
    assert en.cvd_shift(bars, window="4min", min_bars=3).iloc[4] == -1


def test_cvd_shift_does_not_read_across_the_session_break() -> None:
    bars = bars_at(
        list(range(8)),
        [100.0] * 8,
        deltas=[-10, -10, -10, -10, 30, 30, 30, 30],
        session=[SESSION] * 4 + [NEXT] * 4,
    )
    assert (en.cvd_shift(bars, window="4min", min_bars=3).iloc[4:7] == 0).all()


# --------------------------------------------------------------------------
# Condition D -- range expansion
# --------------------------------------------------------------------------
def test_expansion_goes_long_on_a_wide_bar_that_closed_at_its_high() -> None:
    bars = set_bar(bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6), 5, 99.0, 105.0, 99.0, 104.5)
    s = en.range_expansion(bars, atr_window="20min", atr_min_bars=3, mult=1.5, body_min=0.6)
    assert s.iloc[-1] == 1


def test_expansion_is_flat_when_the_wide_bar_gave_it_all_back() -> None:
    # The same 60-tick range, closing near its open. A fight, not expansion --
    # and ATR alone cannot tell the two apart, which is why the body is here.
    bars = set_bar(bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6), 5, 101.0, 105.0, 99.0, 101.5)
    s = en.range_expansion(bars, atr_window="20min", atr_min_bars=3, mult=1.5, body_min=0.6)
    assert s.iloc[-1] == 0


def test_expansion_is_flat_when_a_directional_bar_is_no_wider_than_average() -> None:
    bars = set_bar(bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6), 5, 99.0, 101.0, 99.0, 100.9)
    s = en.range_expansion(bars, atr_window="20min", atr_min_bars=3, mult=1.5, body_min=0.6)
    assert s.iloc[-1] == 0


def test_expansion_goes_short_on_a_wide_bar_that_closed_at_its_low() -> None:
    bars = set_bar(bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6), 5, 105.0, 105.0, 99.0, 99.5)
    s = en.range_expansion(bars, atr_window="20min", atr_min_bars=3, mult=1.5, body_min=0.6)
    assert s.iloc[-1] == -1


# --------------------------------------------------------------------------
# Condition A -- stubbed by decision, not by difficulty
# --------------------------------------------------------------------------
def test_absorption_is_a_stub_and_never_fires() -> None:
    bars = bars_at(list(range(6)), [100.0] * 6, deltas=[500, -500, 500, -500, 500, -500])
    a = en.absorption_reversal(bars)
    assert (a == 0).all()
    assert a.index.equals(bars.index)


# --------------------------------------------------------------------------
# The combiner
# --------------------------------------------------------------------------
def votes(bars: pd.DataFrame, *cols: list[int]) -> list[pd.Series]:
    return [pd.Series(c, index=bars.index, dtype="int64") for c in cols]


def test_three_agreeing_conditions_make_a_signal() -> None:
    bars = bars_at([0, 1], [100.0] * 2)
    c = votes(bars, [0, 1], [0, 1], [0, 1], [0, 0])
    out = en.combine(c, min_conditions=3, eligible=pd.Series(True, index=bars.index))
    assert list(out) == [0, 1]


def test_two_conditions_are_not_three() -> None:
    bars = bars_at([0, 1], [100.0] * 2)
    c = votes(bars, [0, 1], [0, 1], [0, 0], [0, 0])
    out = en.combine(c, min_conditions=3, eligible=pd.Series(True, index=bars.index))
    assert list(out) == [0, 0]


def test_a_condition_voting_the_other_way_kills_the_signal() -> None:
    # Three long votes against one short is a disagreement, not a 3-of-4 pass.
    bars = bars_at([0, 1], [100.0] * 2)
    c = votes(bars, [0, 1], [0, 1], [0, 1], [0, -1])
    out = en.combine(c, min_conditions=3, eligible=pd.Series(True, index=bars.index))
    assert list(out) == [0, 0]


def test_an_ineligible_bar_cannot_signal() -> None:
    bars = bars_at([0, 1], [100.0] * 2)
    c = votes(bars, [1, 1], [1, 1], [1, 1], [0, 0])
    out = en.combine(c, min_conditions=3, eligible=pd.Series([False, True], index=bars.index))
    assert list(out) == [0, 1]


def test_a_missing_eligibility_value_fails_closed() -> None:
    # A bar the filter could not score is not a bar that passed it.
    bars = bars_at([0, 1], [100.0] * 2)
    c = votes(bars, [1, 1], [1, 1], [1, 1], [0, 0])
    out = en.combine(c, min_conditions=3, eligible=pd.Series([np.nan, True], index=bars.index))
    assert list(out) == [0, 1]
