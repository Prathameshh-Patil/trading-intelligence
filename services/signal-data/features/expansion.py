"""Layer 3's expansion features: how far a bar travelled, and how convincingly.

Week 1 D2, `plans/team/week-01.md` §3. Everything here is in TICKS except the
body ratio, which is dimensionless by construction.

`atr` lives here rather than in `regime_filter.py`, where D1 first put it. It
is an expansion feature that the regime gate happens to consume, and a second
true-range calculation is exactly the quiet disagreement `strategies.py` warns
about -- `regime_filter` imports this one.

A zero-range bar is real: gold prints bars that open, close and never trade
away from one price. Every ratio here floors its denominator at one tick, so
the flattest bar in the month is 0.0 rather than `inf` and then a dropped row.
"""

from __future__ import annotations

import pandas as pd

from instruments import Instrument
from windows import align, trailing


def atr(bars: pd.DataFrame, inst: Instrument, *, window: str, min_bars: int) -> pd.Series:
    """Average true range over a trailing clock window, in TICKS of `inst`.

    Ticks because every threshold in this project is in ticks (Part A, A7).
    A filter that quietly used points would be a factor-of-ten error visible
    only as a surprising pass rate.

    **`inst` is required and has no default.** A tick imported rather than
    passed is the assumption `instruments.py` exists to delete: at 40 ticks
    this reads as a $4.00 move on GC and could be $0.40 on spot, and the two
    are indistinguishable in the output. Track B wants this in basis points
    and calls `features.portable.atr_bp`, which wraps this rather than
    re-deriving it.

    True range needs the previous close, which is NaN at each session's first
    bar -- so that bar's range is high-low, which is the right answer rather
    than a gap measured against yesterday's close.
    """
    prev = bars.groupby("session", sort=False)["close"].shift(1)
    tr = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prev).abs(),
            (bars["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    rolled = trailing(bars.assign(_tr=tr), "_tr", window, min_bars).mean()
    return align(rolled, bars) / inst.tick


def bar_range(bars: pd.DataFrame, inst: Instrument) -> pd.Series:
    """High minus low, in ticks of `inst`.

    No window and no session grouping: a bar's own range is the one feature
    here that cannot be contaminated by its neighbours, which is why it is
    worth having next to ATR rather than folded into it.
    """
    return (bars["high"] - bars["low"]) / inst.tick


def body_ratio(bars: pd.DataFrame, inst: Instrument) -> pd.Series:
    """Body as a fraction of range: |close - open| / (high - low).

    Near 1 the bar went one way and held it; near 0 it travelled and gave it
    all back. This is the shape half of expansion -- a 60-tick range that
    closes on its open is not expansion, it is a fight, and ATR alone cannot
    tell the two apart.
    """
    span = (bars["high"] - bars["low"]).clip(lower=inst.tick)
    return (bars["close"] - bars["open"]).abs() / span
