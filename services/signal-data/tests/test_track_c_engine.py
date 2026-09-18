"""The event loop: fills, exits, the daily caps, and the same-bar tie.

The contexts here are built by hand (`test_track_c_strategies.py` says why) and
every one of them fires S1, because what is under test is the LOOP -- which
strategy produced the suggestion is the other file's question.

`test_the_whole_pipeline_runs_on_synthetic_bars` is the one end-to-end case:
random-walk bars through `context.build`, `engine.run`, `funnel.check` and
`metrics.summarize`. It asserts almost nothing about the numbers, deliberately
-- a random walk has no edge and any assertion that it does would be the test
fitting itself. What it proves is that the pipeline runs, accounts for every
bar, and produces a refusal for nearly all of them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import pytest
from conftest import spot_bars
from test_track_c_strategies import NEUTRAL

import backtest as bt
import fsm
from instruments import XAUUSD
from track_c import config, engine, funnel, metrics, strategies
from track_c.suggestion import Suggestion

CFG = config.load()

# The S1 row from `test_track_c_strategies`: entry 3400.00, stop 3396.00,
# target 3410.00, D = $4.00 at ATR $4.00.
FIRES: dict[str, Any] = {"close": 3401.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62}
QUIET: dict[str, Any] = {"in_s1": False, "in_s2": False, "in_s3": False, "in_s4": False}
ENTRY, STOP, TARGET = 3400.0, 3396.0, 3410.0


def ctx(*rows: Mapping[str, Any], start: str = "2026-07-16T13:00:00Z") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz="UTC")
    return pd.DataFrame([{**NEUTRAL, **r} for r in rows], index=idx)


def bar(low: float, high: float, close: float | None = None,
        **over: Any) -> dict[str, Any]:
    """A quiet bar with a chosen range -- no strategy fires on it."""
    return {**QUIET, "low": low, "high": high, "close": close if close is not None else high,
            **over}


# --------------------------------------------------------------------------
# Fills


def test_a_limit_fills_on_the_next_bar_at_its_own_price() -> None:
    """Never at the bar's price and never better: last in queue, no improvement."""
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3409.0, 3411.0)), CFG)
    assert len(res.trades) == 1
    assert res.trades["entry"].iloc[0] == pytest.approx(ENTRY)
    assert res.trades["exit_reason"].iloc[0] == "target"


def test_a_limit_that_is_not_touched_expires_and_is_never_re_rested() -> None:
    """§9 gives it 20 seconds. It does not become a market order and it does
    not sit there for the rest of the session."""
    res = engine.loop(ctx(FIRES, bar(3401.0, 3403.0), bar(3395.0, 3402.0)), CFG)
    assert res.trades.empty
    assert res.vetoes[("s1", "limit_expired")] == 1


def test_every_fill_is_flagged_unresolved_at_five_minute_bars() -> None:
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3409.0, 3411.0)), CFG)
    assert res.unresolved == 1
    assert bool(res.trades["unresolved"].iloc[0])


# --------------------------------------------------------------------------
# Exits


def test_a_bar_that_clears_both_barriers_resolves_to_the_stop() -> None:
    """The one convention borrowed from `backtest.first_touch`: the order is
    not in the bar, so the worse of the two is the honest answer."""
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3390.0, 3412.0)), CFG)
    assert res.trades["exit_reason"].iloc[0] == "stop"


def test_the_borrowed_tie_rule_is_the_same_one_first_touch_uses() -> None:
    """Pinned against `backtest.first_touch_from` on the same geometry rather
    than asserted in prose. The engine cannot call it -- its stop moves to
    break-even -- so what is shared is the rule, and this is where the two are
    held to the same answer."""
    bars = spot_bars([3400.0] * 6, rng=0.0)
    bars.loc[bars.index[1], ["high", "low"]] = [3412.0, 3390.0]
    trades = pd.DataFrame({"t": [bars.index[0]], "side": [1], "entry": [ENTRY]})
    ex = bt.excursions(bars, trades, XAUUSD, horizon=10)
    touch = bt.first_touch_from(ex, target=(TARGET - ENTRY) / XAUUSD.tick,
                                stop=(ENTRY - STOP) / XAUUSD.tick)
    assert touch.iloc[0] == -1


def test_a_gapping_stop_loses_more_than_one_r() -> None:
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3380.0, 3399.0)), CFG)
    assert res.trades["r"].iloc[0] < -1.0


def test_the_stop_moves_to_break_even_at_one_and_a_half_r() -> None:
    """And not before: the move is applied at the bar's close, so the bar that
    earned it is still carrying full risk."""
    res = engine.loop(ctx(FIRES,
                          bar(3399.0, 3402.0),          # fills at 3400.00
                          bar(3400.0, 3406.5),          # +$6.50 = 1.625D -> BE armed
                          bar(3399.0, 3400.5)), CFG)    # back through entry -> stopped flat
    assert res.trades["exit_reason"].iloc[0] == "stop"
    assert res.trades["r"].iloc[0] > -0.5      # a break-even stop, minus the exit cost


def test_a_position_is_flat_at_the_end_of_its_session() -> None:
    """Day trading: nothing is carried over the session boundary."""
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3400.0, 3402.0)), CFG)
    assert res.trades["exit_reason"].iloc[0] == "eod"


def test_s3s_time_stop_closes_a_reversion_that_did_not_happen() -> None:
    """The one strategy with a hard time stop -- `strategies/s3.py` says why."""
    fires: dict[str, Any] = {"close": 3395.0, "vwap_z": -2.5, "h_dfa": 0.40, "h_vt": 0.41,
             "vol_ratio": 0.80, "s3_dc_low": 3392.0, "in_s1": False}
    quiet = [bar(3393.0, 3396.0) for _ in range(config.i(CFG, "s3.time_stop_bars") + 2)]
    res = engine.loop(ctx(fires, *quiet), CFG)
    assert res.trades["exit_reason"].iloc[0] == "time_stop"


# --------------------------------------------------------------------------
# Layer 4 -- the caps refuse, they never resize


def test_only_one_position_is_open_at_a_time() -> None:
    res = engine.loop(ctx(FIRES, {**FIRES, "low": 3399.0}, bar(3409.0, 3411.0)), CFG)
    assert len(res.trades) == 1
    assert res.vetoes[("s1", "position_open")] >= 1


def test_the_third_trade_of_a_day_is_refused() -> None:
    """Two trades a day, §11, and the refusal is counted rather than resized."""
    seq: list[Mapping[str, Any]] = []
    for _ in range(3):
        seq += [FIRES, bar(3399.0, 3402.0), bar(3409.0, 3411.0)]
    res = engine.loop(ctx(*seq), CFG)
    assert len(res.trades) == config.i(CFG, "risk.max_trades_per_day")
    assert res.vetoes[("s1", "trade_limit")] >= 1


def test_the_daily_caps_reset_at_the_session_boundary() -> None:
    """22:00 UTC is where `inst.session_shift` cuts the day."""
    both = [FIRES, bar(3399.0, 3402.0), bar(3409.0, 3411.0)] * 4
    frame = ctx(*both, start="2026-07-16T21:30:00Z")
    assert frame["session"].nunique() == 1
    frame.loc[frame.index >= "2026-07-16T22:00:00Z", "session"] = \
        pd.Timestamp("2026-07-17").date()
    res = engine.loop(frame, CFG)
    assert len(res.trades) > config.i(CFG, "risk.max_trades_per_day")


# --------------------------------------------------------------------------
# Accounting


def test_the_funnel_accounts_for_every_bar_and_every_strategy() -> None:
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3409.0, 3411.0)), CFG)
    funnel.check(res.counts, strategies.CONDITIONS)
    for s in config.STRATEGIES:
        assert res.counts[(s, funnel.EVALUATED)] == 3


def test_r_is_the_risk_taken_at_entry_and_not_a_dollar_figure() -> None:
    res = engine.loop(ctx(FIRES, bar(3399.0, 3402.0), bar(3409.0, 3411.0)), CFG)
    t = res.trades.iloc[0]
    risk = t["d_usd"] * t["lots"] * config.f(CFG, "risk.value_per_lot")
    assert risk == pytest.approx(config.f(CFG, "risk.equity_usd")
                                 * config.f(CFG, "risk.risk_fraction"))
    assert t["r"] == pytest.approx(t["pnl_usd"] / risk)


def test_the_whole_pipeline_runs_on_synthetic_bars() -> None:
    """End to end: real `context.build`, real loop, real metrics. A random walk
    has no edge, so nothing is asserted about profitability -- only that every
    bar is accounted for and that the engine refuses nearly all of them."""
    rng = np.random.default_rng(11)
    bars = spot_bars(list(3400 + np.cumsum(rng.normal(0, 0.35, 3500))), rng=0.9)
    res = engine.run(bars, XAUUSD, CFG, events=pd.DatetimeIndex([], tz="UTC"))
    funnel.check(res.counts, strategies.CONDITIONS)
    table = funnel.table(res.counts, strategies.CONDITIONS)
    assert (table["reached"] >= table["survivors"]).all()
    assert res.counts[("s1", funnel.EVALUATED)] == len(bars)
    assert len(res.trades) < len(bars) / 100
    metrics.summarize(res.trades, CFG)      # runs on an empty frame too


def test_suggest_and_the_engine_answer_the_same_question() -> None:
    """The live path and the backtest path are one function, so they cannot
    disagree -- `suggest.py`'s whole reason for existing."""
    from track_c import suggest
    frame = ctx(FIRES)
    out = suggest.row(frame, 0, cfg=CFG, day=fsm.Day())
    assert isinstance(out[0], Suggestion)
    assert out[0].entry == pytest.approx(ENTRY)
    assert len(out) == len(strategies.ALL)


def test_at_slices_to_the_moment_asked_about() -> None:
    """`suggest.at` is the "any setups now?" path. **The frame must end at the
    moment being asked about** -- every context column is causal within its
    frame, so a frame running past `when` would let a rolling window include
    bars that had not happened yet. It slices rather than trusting the caller.
    """
    from track_c import suggest
    rng = np.random.default_rng(2)
    bars = spot_bars(list(3400 + np.cumsum(rng.normal(0, 0.4, 600))), rng=0.8)
    when = bars.index[400]
    out = suggest.at(bars, XAUUSD, CFG, events=pd.DatetimeIndex([], tz="UTC"), when=when)
    assert len(out) == len(strategies.ALL)
    assert all(o.ts == when for o in out)


def test_at_refuses_an_empty_frame_rather_than_answering() -> None:
    """No bars is a data failure, not a refusal: a refusal names a condition the
    market failed, and "there is no history" is not one."""
    with pytest.raises(ValueError, match="needs a history"):
        from track_c import suggest
        suggest.at(spot_bars([3400.0]).iloc[:0], XAUUSD, CFG,
                   events=pd.DatetimeIndex([], tz="UTC"))
