"""The four candidates, on bars built by hand so the answer is known.

Three failure modes get a test each, because all three produce signal series
that look entirely plausible:

  * a trailing window that reaches back across the overnight break, mixing
    Asia's distribution into NY's;
  * a window measured in ROWS when minute_bars has dropped empty minutes, so
    "30 bars" is however many minutes traded;
  * anything at all reading a bar later than the one it fills on.

The last one is the only bug here that cannot be found by looking at the
output, so it is tested by mutating the future and asserting the past did not
move.

What this file does NOT test is whether any strategy makes money. That is
thresholds_selector.md Part B's question and it is not answerable yet.
"""

import numpy as np
import pandas as pd
import pytest
from conftest import NEXT, SESSION, bars_at, noise, ticks_at

import backtest as bt
import strategies as st
from s1 import TICK


# --------------------------------------------------------------------------
# The three ways a feature lies
# --------------------------------------------------------------------------
def test_a_trailing_window_never_reaches_into_the_previous_session() -> None:
    # Session one runs flat at delta 10; session two opens at 1000. If the
    # window spans the break, that 1000 is scored against session one's
    # distribution and reads as a colossal outlier. It is just a new session.
    mins = list(range(40))
    bars = bars_at(
        mins,
        [100.0] * 40,
        deltas=noise(35) + [1000] * 5,
        session=[SESSION] * 35 + [NEXT] * 5,
    )
    z = st.delta_z(bars, window="30min", min_bars=5)
    assert z.iloc[10:35].notna().all(), "session one has trailing context and should be scored"
    assert z.iloc[35:40].isna().all(), "session two starts from nothing; the window stopped at the break"


def test_a_window_is_measured_on_the_clock_not_on_row_offsets() -> None:
    # Bars at minutes 0,1,2 then a 100-minute gap. At minute 100 the trailing
    # 30 minutes hold exactly one bar -- its own -- however many rows precede.
    bars = bars_at([0, 1, 2, 100, 101], [100.0] * 5, deltas=[10, 12, 8, 500, 10])
    z = st.delta_z(bars, window="30min", min_bars=3)
    assert np.isnan(z.iloc[3]), "minute 100 has no trailing context; a row window would give it three"


def test_no_feature_reads_a_bar_later_than_its_own() -> None:
    mins = list(range(60))
    bars = bars_at(mins, [100.0 + (i % 7) * TICK for i in range(60)], deltas=noise(60), ranges=[0.5] * 60)
    later, tail = bars.copy(), bars.index[50:]
    later.loc[tail, "delta"] = 99_999
    later.loc[tail, "close"] = 500.0
    later["cvd"] = later.groupby("session", sort=False)["delta"].cumsum()

    for feature in (
        lambda b: st.delta_z(b, window="30min", min_bars=5),
        lambda b: st.cvd_slope(b, window="30min", min_bars=5),
        lambda b: st.absorption(b),
    ):
        before, after = feature(bars).iloc[:50], feature(later).iloc[:50]
        pd.testing.assert_series_equal(before, after)


# --------------------------------------------------------------------------
# The candidates
# --------------------------------------------------------------------------
def test_delta_outlier_takes_the_side_of_the_outlying_bar() -> None:
    bars = bars_at(list(range(41)), [100.0] * 41, deltas=noise(40) + [1000])
    sig = st.delta_outlier(bars, window="30min", min_bars=10, z=3.0)
    assert sig.iloc[40] == 1
    assert (sig.iloc[:40] == 0).all()

    down = bars_at(list(range(41)), [100.0] * 41, deltas=noise(40) + [-1000])
    assert st.delta_outlier(down, window="30min", min_bars=10, z=3.0).iloc[40] == -1


def test_cvd_divergence_shorts_a_new_high_that_flow_does_not_confirm() -> None:
    # Price grinds to a new high on the last bar while CVD falls the whole way.
    n = 40
    closes = [100.0 + i * TICK for i in range(n)]
    bars = bars_at(list(range(n)), closes, deltas=[-50] * n)
    sig = st.cvd_divergence(bars, window="30min", min_bars=10, min_slope=200)
    assert sig.iloc[-1] == -1

    # Same price path, flow confirming it. Nothing to diverge from.
    agree = bars_at(list(range(n)), closes, deltas=[50] * n)
    assert (st.cvd_divergence(agree, window="30min", min_bars=10, min_slope=200) == 0).all()


def test_absorption_fades_heavy_delta_that_did_not_move_price() -> None:
    # 900 contracts bought into a bar one tick wide. The buyers got filled and
    # price went nowhere, so the resting seller won: fade it.
    bars = bars_at([0, 1, 2], [100.0] * 3, deltas=[10, 900, 10], ranges=[0.5, 0.1, 0.5])
    sig = st.absorption_fade(bars, min_ratio=500.0, min_delta=100)
    assert sig.iloc[1] == -1
    assert sig.iloc[0] == 0 and sig.iloc[2] == 0


def test_a_dead_bar_is_not_absorption() -> None:
    # The ratio is scale-free: five contracts into one tick scores what five
    # hundred into a hundred ticks does. On the real session the top ratios
    # were 5- and 6-lot bars in the Globex-open dead zone. Absorption means
    # SIZE that failed to move price, so the size floor is load-bearing.
    bars = bars_at([0, 1], [100.0, 100.0], deltas=[5, 900], ranges=[0.1, 0.1])
    sig = st.absorption_fade(bars, min_ratio=5.0, min_delta=100)
    assert sig.iloc[0] == 0, "five contracts is an empty market, not absorption"
    assert sig.iloc[1] == -1


def test_absorption_survives_a_bar_that_never_moved() -> None:
    # high == low is a real bar and the purest absorption there is. It must
    # not divide by zero and it must not become inf.
    bars = bars_at([0], [100.0], deltas=[900], ranges=[0.0])
    assert np.isfinite(st.absorption(bars)).all()


def test_footprint_stacks_on_the_buy_side() -> None:
    # Three price levels where buy volume at P dwarfs sell volume at P-1 tick.
    rows = []
    for lvl in range(3):
        p = 100.0 + lvl * TICK
        rows += [(0, p, 400, "B"), (0, p - TICK, 10, "A")]
    ticks = ticks_at(rows)
    bars = bars_at([0], [100.2], deltas=[1170], ranges=[0.3])
    sig = st.footprint_stack(ticks, bars, ratio=3.0, min_stack=3)
    assert sig.iloc[0] == 1

    assert (st.footprint_stack(ticks, bars, ratio=3.0, min_stack=4) == 0).all(), "four stacked levels do not exist"


def test_a_lone_print_with_nothing_opposite_is_not_an_imbalance() -> None:
    # Nothing traded at the level below, so there is no ratio to clear. A
    # divide-by-nothing must not read as infinite imbalance.
    ticks = ticks_at([(0, 100.0, 5, "B")])
    bars = bars_at([0], [100.0], deltas=[5])
    assert (st.footprint_stack(ticks, bars, ratio=3.0, min_stack=1) == 0).all()


# --------------------------------------------------------------------------
# The gate, and the seam to the harness
# --------------------------------------------------------------------------
def test_no_strategy_has_a_default_threshold() -> None:
    """thresholds_selector.md §6.1 made mechanical: the file cannot be run
    before Part B is committed, because there is no number to run it with.

    The `type: ignore`s are the same gate one layer earlier -- mypy rejects
    every one of these calls too, so a strategy without its thresholds does
    not survive `mypy` either. Deleting the ignores makes the type checker
    say what this test says.
    """
    bars = bars_at([0, 1], [100.0, 100.0], deltas=[1, 1])
    ticks = ticks_at([(0, 100.0, 1, "B")])
    for call in (
        lambda: st.delta_outlier(bars),  # type: ignore[call-arg]
        lambda: st.cvd_divergence(bars),  # type: ignore[call-arg]
        lambda: st.absorption_fade(bars),  # type: ignore[call-arg]
        lambda: st.footprint_stack(ticks, bars),  # type: ignore[call-arg]
    ):
        with pytest.raises(TypeError, match="required keyword-only"):
            call()


def test_signals_are_valid_input_to_the_backtest_harness() -> None:
    bars = bars_at(list(range(60)), [100.0 + (i % 5) * TICK for i in range(60)], deltas=noise(60))
    sig = st.delta_outlier(bars, window="30min", min_bars=10, z=1.0)
    assert set(sig.unique()) <= {-1, 0, 1}
    assert sig.index.equals(bars.index)
    bt.evaluate(bars, sig, horizons=(5,))  # raises if the index contract is broken
