"""The intra-bar audit, on frames where the 5-minute and 1-minute answers differ.

Both frames are built by hand and the disagreement is put there on purpose: an
audit that can only ever agree measures nothing, and that is the way this
particular test file would quietly stop being useful.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from conftest import spot_bars

from instruments import XAUUSD
from track_c import audit, config

CFG = config.load()
T0 = pd.Timestamp("2026-07-16T13:00:00Z")


def trade(**over: Any) -> pd.DataFrame:
    """One filled S1-shaped trade: entry 3400, stop 3396, target 3410."""
    row = {"strategy": "s1", "ts_signal": T0, "ts_entry": T0 + pd.Timedelta(minutes=5),
           "side": 1, "entry": 3400.0, "stop": 3396.0, "target": 3410.0, "lots": 1.0,
           "d_usd": 4.0, "ts_exit": T0 + pd.Timedelta(minutes=15), "exit_price": 3396.0,
           "exit_reason": "stop", "pnl_usd": -400.0, "r": -1.0, "confidence": 0.5,
           "unresolved": True, "be_moved": False}
    return pd.DataFrame([{**row, **over}])


def minutes(rows: list[tuple[float, float]], *, start: pd.Timestamp = T0,
            pad: int = 40) -> pd.DataFrame:
    """1-minute bars with chosen (low, high) ranges, padded so the horizon fits."""
    bars = spot_bars([3400.0] * (len(rows) + pad), start=str(start), freq="1min", rng=0.0)
    for i, (low, high) in enumerate(rows):
        bars.loc[bars.index[i], "low"] = low
        bars.loc[bars.index[i], "high"] = high
    return bars


def test_a_five_minute_fill_the_first_minute_does_not_confirm_is_flagged() -> None:
    """The extra four minutes of hindsight, counted rather than caveated."""
    bars = minutes([(3401.0, 3402.0), (3401.0, 3402.0), (3398.0, 3402.0)])
    assert not audit.entry_agreement(trade(), bars, CFG).iloc[0]


def test_a_fill_the_first_minute_does_confirm_agrees() -> None:
    # Index 1 is the first minute AFTER the signal bar's close, which is the
    # window §9's 20 seconds actually falls in.
    bars = minutes([(3401.0, 3402.0), (3398.0, 3402.0)])
    assert audit.entry_agreement(trade(), bars, CFG).iloc[0]


def test_the_finer_bars_can_flip_a_same_bar_tie() -> None:
    """The 5-minute bar cleared both barriers and the convention gave it to the
    stop. At 1 minute the order is visible and the target came first."""
    # The entry is at T0+5min, so the first bar the bracket is judged over is
    # index 6 -- `first_touch` measures bars strictly after entry.
    rows = [(3399.0, 3401.0)] * 6 + [(3399.0, 3411.0)] + [(3390.0, 3400.0)] * 4
    out = audit.compare(trade(), minutes(rows), XAUUSD, CFG)
    assert out["bar_outcome"].iloc[0] == "stop"
    assert out["min_outcome"].iloc[0] == "target"
    # Not `is False`: a column with no unjudged rows lands in pandas' own bool
    # dtype, so the value is `np.False_` rather than the builtin.
    assert out["outcome_agrees"].iloc[0] is not None
    assert not out["outcome_agrees"].iloc[0]


def test_the_finer_bars_confirming_the_stop_agrees() -> None:
    rows = [(3399.0, 3401.0)] * 6 + [(3395.0, 3401.0)] + [(3395.0, 3411.0)] * 4
    out = audit.compare(trade(), minutes(rows), XAUUSD, CFG)
    assert out["outcome_agrees"].iloc[0]


def test_a_trade_whose_stop_moved_is_not_judged_on_a_fixed_bracket() -> None:
    """`first_touch_from` answers a fixed-bracket question; a break-even stop is
    not one, and scoring it against one manufactures disagreements."""
    rows = [(3399.0, 3401.0)] * 6 + [(3399.0, 3411.0)] + [(3390.0, 3400.0)] * 4
    out = audit.compare(trade(be_moved=True), minutes(rows), XAUUSD, CFG)
    assert out["outcome_agrees"].iloc[0] is None


def test_bars_that_do_not_cover_the_trade_are_unknown_and_not_agreement() -> None:
    later = minutes([(3399.0, 3401.0)], start=T0 + pd.Timedelta(days=3))
    out = audit.compare(trade(), later, XAUUSD, CFG)
    assert out["min_outcome"].iloc[0] is None
    assert out["outcome_agrees"].iloc[0] is None


def test_the_summary_carries_the_label_every_headline_has_to_repeat() -> None:
    rows = [(3399.0, 3401.0)] * 6 + [(3399.0, 3411.0)] + [(3390.0, 3400.0)] * 4
    s = audit.summary(audit.compare(trade(), minutes(rows), XAUUSD, CFG))
    assert s["n"] == 1
    label = str(s["label"])
    assert "UPPER BOUND" in label
    assert "20-second" in label


def test_an_empty_trade_frame_is_a_result_not_an_exception() -> None:
    s = audit.summary(audit.compare(trade().iloc[:0], minutes([]), XAUUSD, CFG))
    assert s["n"] == 0
    assert s["label"] == "no trades to audit"
