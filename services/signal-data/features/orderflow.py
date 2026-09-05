"""Layer 3's order-flow features: what the flow did, and where price sits.

**VENUE-SPECIFIC -- GC only.** ARCHITECTURE §2. Spot gold has no tape, no
aggregate volume and no aggressor, so nothing in this file is computable
there; `instruments.require_flow` is what says so out loud.

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

import numpy as np
import pandas as pd

from instruments import Instrument, require_flow
from strategies import _align, _window, absorption, cvd_slope, delta_z

__all__ = [
    "absorption",
    "cvd_persistence",
    "cvd_slope",
    "delta_z",
    "vwap",
    "vwap_distance",
]


def _persistence(delta: np.ndarray) -> float:
    """|sum(delta)| / sum(|delta|) -- how one-directional a stretch of flow was.

    Dimensionless, in [0, 1]. One means every contract went the same way; zero
    means buying and selling cancelled exactly.

    **This is the canonical definition and `regimes.py` imports it from here.**
    It lived there first, as `_cvd_persistence`, because the clustering needed
    it before anything else did. It belongs at this layer: a feature the
    clustering consumes, not a detail of the clustering. Keeping one copy is
    what stops the regime labels and the gate that filters on them from
    quietly measuring different things.

    A window with no flow at all has no direction to report, so it is NaN
    rather than 0.0 -- zero would read as "perfectly balanced", which is a
    different statement from "nothing happened".
    """
    gross = np.abs(delta).sum()
    if gross == 0:
        return np.nan
    return float(abs(delta.sum()) / gross)


def cvd_persistence(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """`_persistence` over a trailing clock window, restarted each session.

    `regimes.py` computes this same quantity over a window measured in BARS
    rather than clock time. The two agree on a frame with no missing bars and
    diverge on one with gaps, which is the dropped-minute trap `strategies.py`
    documents -- this version is the one that survives it.
    """
    r = _window(bars, "delta", window, min_bars)
    return _align(r.apply(_persistence, raw=True), bars)


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


def vwap_distance(bars: pd.DataFrame, inst: Instrument) -> pd.Series:
    """Close minus session VWAP, in TICKS of `inst`. Signed: above is positive.

    This is the feature; `vwap` is the intermediate. A raw VWAP is ~4,000 and
    its distribution says nothing, which matters because D2's deliverable is
    every feature's distribution and one of them would have been unreadable.
    """
    require_flow(inst)
    return (bars["close"] - vwap(bars)) / inst.tick
