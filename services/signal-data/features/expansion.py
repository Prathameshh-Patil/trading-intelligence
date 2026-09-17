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

import numpy as np
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


# --------------------------------------------------------------------------
# mathematical.md §2 -- the volatility ensemble's first leg.
#
# ⚠️ EVERYTHING BELOW IS DIMENSIONLESS, NOT TICKS. This module's header says
# "everything here is in TICKS except the body ratio", and Yang-Zhang breaks
# that: it is a standard deviation of LOG returns. Converting to a distance
# means multiplying by price, which `r_hat_60` does and nothing else may --
# a sigma read as ticks is a factor-of-3400 error at gold's price, and it
# would pass a `> threshold` filter by never passing it.


def _yz_k(n: int) -> float:
    """Yang & Zhang (2000)'s weight on the open-to-close term.

    `0.34 / (1.34 + (n+1)/(n-1))`. Rises from 0.078 at n=2 toward 0.34/2.34
    = 0.1453 as n grows; a value outside that band means a mistyped formula.
    """
    return 0.34 / (1.34 + (n + 1) / (n - 1))


def yang_zhang(bars: pd.DataFrame, *, n: int) -> pd.Series:
    """§2's realized volatility over a trailing `n`-bar window. Dimensionless.

    WHY THIS ESTIMATOR AND NOT CLOSE-TO-CLOSE. It is drift-independent, and
    the archive has a 55.2% rise in it (`M3B_DRIFT.md`'s correction to the
    published 84%). A close-to-close estimator reads that trend as volatility
    and would report the bull market as risk -- the exact confound M3b was
    written to separate.

    WHY THE FIRST VALID INDEX IS `n` AND NOT `n-1`. The overnight term needs
    a previous close, so `n` overnight returns need `n+1` bars. A partial
    window would be a smaller number that looks like calm, and `r_ratio`
    divides by it.

    NO SESSION GROUPING, DELIBERATELY. `atr` above groups by session because
    a true range across the break is not a range. Yang-Zhang is the opposite:
    the overnight term IS the gap, and grouping it away would delete the
    component the estimator exists to capture.
    """
    o, h, low, c = (np.log(bars[x]) for x in ("open", "high", "low", "close"))
    ro = o - c.shift(1)                       # overnight
    rc = c - o                                # open to close
    rs = (h - o) * (h - c) + (low - o) * (low - c)   # Rogers-Satchell
    k = _yz_k(n)
    var = (ro.rolling(n).var(ddof=1)
           + k * rc.rolling(n).var(ddof=1)
           + (1.0 - k) * rs.rolling(n).mean())
    # Rogers-Satchell is a sum of products and goes negative on a single bar;
    # over a window it can in principle drag the total under zero. Clip rather
    # than let sqrt produce a NaN that reads downstream as "no data".
    return np.sqrt(var.clip(lower=0.0))
