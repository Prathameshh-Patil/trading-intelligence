"""Mechanics of the harness, on bars built by hand so the answer is known.

The three failure modes worth a test each: measuring a horizon in rows when the
bar frame has gaps, letting a window run past the session it started in, and
reporting a leg the session cut short as though it had run the full horizon.
All three produce numbers that look completely reasonable.
"""

import numpy as np
import pandas as pd
import pytest
from conftest import SESSION, bars_at, entries_at

import backtest as bt
from s1 import TICK


def test_horizon_is_measured_on_the_clock_not_on_row_offsets() -> None:
    # Bars exist at minutes 0,1,2 then jump to 10. Five rows on is minute 12;
    # five MINUTES on is minute 2. Only one of those is the 5m return.
    bars = bars_at([0, 1, 2, 10, 11, 12, 13], [100.0, 100.5, 101.0, 200.0, 200.0, 200.0, 200.0])
    tr = bt.evaluate(bars, entries_at(bars, {0: 1}), horizons=(5,))
    assert tr["move_5m"].iloc[0] == pytest.approx((101.0 - 100.0) / TICK)


def test_a_horizon_never_runs_past_its_session() -> None:
    # The horizon completes at minute 5, inside its own session. The next
    # session opening at 500 is four bars away and must not reach the numbers.
    bars = bars_at([0, 1, 2, 3, 4, 5, 6, 7], [100.0] + [101.0] * 5 + [500.0, 500.0],
                   session=[SESSION] * 6 + ["next", "next"])
    tr = bt.evaluate(bars, entries_at(bars, {0: 1}), horizons=(5,))
    assert tr["move_5m"].iloc[0] == pytest.approx((101.0 - 100.0) / TICK)
    assert tr["mfe_5m"].iloc[0] == pytest.approx((101.0 - 100.0) / TICK)


def test_a_horizon_whose_session_ends_inside_it_is_nan_not_a_short_leg() -> None:
    # Two minutes of session left against a five-minute horizon. Scoring the
    # two-minute move as the 5m return is the silent version of this bug: it
    # reads as a real observation and drags the horizon's mean toward zero.
    bars = bars_at([0, 1, 2, 3], [100.0, 101.0, 500.0, 500.0],
                   session=[SESSION, SESSION, "next", "next"])
    tr = bt.evaluate(bars, entries_at(bars, {0: 1}), horizons=(5,))
    assert np.isnan(tr["move_5m"].iloc[0])


def test_a_short_horizon_survives_where_a_long_one_is_cut_off() -> None:
    # July 2026 in miniature: 5m completes, 30m does not. The row is kept and
    # only the horizon that could not run is NaN -- dropping the whole entry
    # would throw away a measurement that is perfectly good at 5m.
    bars = bars_at(list(range(11)), [100.0] + [101.0] * 10)
    tr = bt.evaluate(bars, entries_at(bars, {0: 1}), horizons=(5, 30))
    assert tr["move_5m"].iloc[0] == pytest.approx((101.0 - 100.0) / TICK)
    assert np.isnan(tr["move_30m"].iloc[0])


def test_an_entry_on_the_last_bar_of_a_session_is_dropped_not_scored() -> None:
    bars = bars_at([0, 1], [100.0, 101.0])
    assert bt.evaluate(bars, entries_at(bars, {1: 1})).empty


def test_a_short_profits_when_price_falls() -> None:
    bars = bars_at([0, 1, 2, 3, 4, 5], [100.0, 99.0, 98.0, 98.0, 98.0, 98.0])
    tr = bt.evaluate(bars, entries_at(bars, {0: -1}), horizons=(5,))
    assert tr["move_5m"].iloc[0] == pytest.approx(20.0)      # 2.00 down / 0.10
    assert tr["mfe_5m"].iloc[0] == pytest.approx(20.0)
    # It never traded against the short, so even the worst moment was +10.
    assert tr["mae_5m"].iloc[0] == pytest.approx(10.0)


def test_adverse_excursion_is_negative_when_the_trade_goes_against_you() -> None:
    bars = bars_at([0, 1, 2, 3, 4, 5], [100.0, 98.0, 103.0, 103.0, 103.0, 103.0])
    tr = bt.evaluate(bars, entries_at(bars, {0: 1}), horizons=(5,))
    assert tr["mae_5m"].iloc[0] == pytest.approx(-20.0)
    assert tr["mfe_5m"].iloc[0] == pytest.approx(30.0)
    assert tr["move_5m"].iloc[0] == pytest.approx(30.0)
    assert tr["mae_5m"].iloc[0] <= tr["mfe_5m"].iloc[0]


def test_entries_off_the_bar_grid_are_rejected() -> None:
    bars = bars_at([0, 1, 2], [100.0, 101.0, 102.0])
    stray = pd.Series([1], index=[pd.Timestamp("2026-07-15T22:00:30Z")])
    with pytest.raises(ValueError, match="not bars"):
        bt.evaluate(bars, stray)


def test_summary_carries_n_and_flags_a_thin_cell() -> None:
    bars = bars_at(list(range(40)), [100.0 + i for i in range(40)])
    tr = bt.evaluate(bars, entries_at(bars, {i: 1 for i in range(5)}), horizons=(5,))
    s = bt.summarize(tr, 5)
    assert s["n"] == 5 and s["thin"] is True          # design §6.5: under 30
    assert s["hit_rate"] == 1.0 and s["median"] > 0
    assert s["expectancy_usd"] == pytest.approx(s["expectancy_ticks"] * 10.0)


def test_the_null_matches_count_and_side_mix() -> None:
    bars = bars_at(list(range(60)), [100.0 + (i % 7) for i in range(60)])
    real = entries_at(bars, {3: 1, 9: 1, 20: -1})
    null = bt.random_entries(bars, real, seed=1)
    assert (null != 0).sum() == 3
    assert sorted(null.to_numpy()) == sorted(real[real != 0].to_numpy())
    assert null.index.isin(bars.index).all()
    assert not null.index.equals(real[real != 0].index)


def test_a_flat_market_has_no_edge_and_the_harness_says_so() -> None:
    bars = bars_at(list(range(60)), [100.0] * 60)
    tr = bt.evaluate(bars, entries_at(bars, {i: 1 for i in range(40)}), horizons=(5, 15))
    rep = bt.report(tr, horizons=(5, 15))
    assert (rep["expectancy_ticks"] == 0).all()
    assert (rep["n"] == 40).all()
    assert np.isclose(rep["hit_rate"], 0.0).all()
