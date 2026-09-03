"""Layer 3's order-flow features: what the flow did, and where price sits.

Week 1 D2, `plans/team/week-01.md` §3. **D2 says import, do not re-derive**,
and three of the four names here are that import: `delta_z`, `cvd_slope` and
`absorption` already exist in `strategies.py`, tested, with the session-window
and dropped-minute traps already solved. Re-deriving them beside their
originals is how two copies of a feature start disagreeing about the London
open. This module is the Layer 3 surface `signals/engine.py` reads on D3, and
it re-exports them deliberately rather than wrapping them in a layer that
would only forward.

The new one is VWAP, which is session-anchored and therefore causal by
construction: every bar's value is a cumulative sum over bars that already
closed.
"""

from __future__ import annotations

import pandas as pd

from s1 import TICK
from strategies import absorption, cvd_slope, delta_z

__all__ = ["absorption", "cvd_slope", "delta_z", "vwap", "vwap_distance"]


def vwap(bars: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP over typical price, in PRICE.

    Typical price rather than close, because a bar's close is one print at one
    instant and VWAP is meant to describe where the session actually traded.

    Anchored at each session open and never carried across the break: an
    overnight-anchored VWAP describes a session that has ended, which is the
    same trap `strategies.py` documents for trailing windows.

    Volume floors at nothing here -- a bar exists because trades happened, so
    a zero-volume bar is a data fault rather than a case to smooth over. It
    comes back NaN, loudly, instead of dividing by zero.
    """
    session = bars["session"].to_numpy()
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3
    traded = (typical * bars["volume"]).groupby(session, sort=False).cumsum()
    volume = bars["volume"].groupby(session, sort=False).cumsum()
    return traded / volume.where(volume > 0)


def vwap_distance(bars: pd.DataFrame) -> pd.Series:
    """Close minus session VWAP, in TICKS. Signed: above is positive.

    This is the feature; `vwap` is the intermediate. A raw VWAP is ~4,000 and
    its distribution says nothing, which matters because D2's deliverable is
    every feature's distribution and one of them would have been unreadable.
    """
    return (bars["close"] - vwap(bars)) / TICK
