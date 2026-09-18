"""The level universe: prior-day extremes, the Asian range, session VWAP, bands.

Every function here is a closed-form quantity of OHLC and the clock. Nothing
is fitted, nothing is learned, and nothing reads a tape -- Track C's whole
premise, enforced by `tests/test_track_c_purity.py` rather than by intent.

⚠️ THE ONE FAILURE MODE THIS MODULE IS WRITTEN AGAINST IS LOOKAHEAD, and it is
invisible in a backtest's output -- it shows up as a good equity curve. Three
places it would otherwise enter:

  * **The Asian range is NaN until the window has closed.** A running cummax
    inside the window is a partial range, and trading a breakout of a range
    that is still forming is trading a level that already includes the bar
    that broke it.
  * **Prior-day extremes are the PREVIOUS session's**, shifted by one session,
    never the current one's running extreme.
  * **Every rolling statistic is causal** -- `rolling(...)` closes on the
    current bar and `shift(1)` is applied where the current bar must not be
    part of its own reference level (`donchian`).

`test_track_c_core.py` asserts each of the three against a frame whose future is
deliberately extreme, so a lookahead leak moves the number visibly.
"""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd


def _local_time(idx: pd.DatetimeIndex) -> np.ndarray:
    if idx.tz is None:
        raise ValueError("Track C bars must carry a tz-aware UTC index; a naive index "
                         "guessed as UTC puts the Asian range five hours out")
    return np.asarray(idx.tz_convert("America/New_York").time)


def in_asian(idx: pd.DatetimeIndex, *, start: time, end: time) -> pd.Series:
    """The Asian window as a clock mask. Wraps midnight; no weekday filter.

    `features.structure.in_window` is the weekday-aware version and is what
    the TRADING windows use. It deliberately does not wrap, and it must not be
    used here for a second reason: Monday's Asian range forms on **Sunday**
    evening New York time, and a weekday filter would silently truncate it to
    the hours after midnight -- a shorter range on one day in five, which
    reads as a livelier Monday rather than as a bug.
    """
    t = _local_time(idx)
    inside = (t >= start) | (t < end) if start > end else (t >= start) & (t < end)
    return pd.Series(inside, index=idx)


def asian_range(bars: pd.DataFrame, *, start: time, end: time) -> pd.DataFrame:
    """Each bar's session's CLOSED Asian range: `asian_high`, `asian_low`.

    NaN before the window closes -- see the module docstring. The range is
    carried forward for the rest of the session, which is what makes it a
    level a breakout can be measured against.
    """
    mask = in_asian(pd.DatetimeIndex(bars.index), start=start, end=end)
    sess = bars["session"]
    hi = bars["high"].where(mask).groupby(sess).cummax().groupby(sess).ffill()
    lo = bars["low"].where(mask).groupby(sess).cummin().groupby(sess).ffill()
    # Inside the window the running extreme is a partial range; outside it, and
    # only after at least one bar has landed in it, it is the range.
    closed = ~mask
    return pd.DataFrame({"asian_high": hi.where(closed), "asian_low": lo.where(closed)})


def prior_day(bars: pd.DataFrame) -> pd.DataFrame:
    """The previous session's high and low: `pdh`, `pdl`.

    By session, not by calendar day -- `spot.minute_bars` already stamps each
    bar with `inst.session_shift` applied, so "yesterday" means the session a
    trader would file under yesterday rather than the UTC date.
    """
    sess = bars["session"]
    hi = bars.groupby(sess)["high"].max()
    lo = bars.groupby(sess)["low"].min()
    order = list(hi.index)
    return pd.DataFrame({
        "pdh": sess.map(hi.shift(1).reindex(order)).astype(float),
        "pdl": sess.map(lo.shift(1).reindex(order)).astype(float),
    }, index=bars.index)


def session_vwap(bars: pd.DataFrame) -> pd.Series:
    """Session VWAP, with QUOTE-UPDATE COUNT standing in for volume.

    **DECLARED ASSUMPTION, not a measurement.** Spot XAUUSD has no tape and no
    traded size; `spot.minute_bars` names the column `ticks` and never `volume`
    for exactly this reason. This weights each bar by how many quotes it
    carried, which correlates with activity and is not the same thing. Every
    report header states it, and S3 -- the only strategy that reads it -- is
    the only one whose result depends on the assumption holding.

    Typical price is the close, not `(h+l+c)/3`: the close is the price a
    reversion is measured back to, and the three-way average is a different
    quantity wearing the same name.
    """
    w = bars["ticks"].astype(float)
    sess = bars["session"]
    return ((bars["close"] * w).groupby(sess).cumsum() / w.groupby(sess).cumsum())


def vwap_z(bars: pd.DataFrame, vwap: pd.Series, *, min_bars: int) -> pd.Series:
    """`(close - vwap)` in units of its own session-to-date standard deviation.

    Expanding rather than rolling: the dispersion a reversion is measured
    against is the session's, and a rolling window would re-centre on the very
    excursion being tested. NaN until `min_bars` -- a z-score off six bars is
    a statement about six bars.
    """
    d = bars["close"] - vwap
    sd = d.groupby(bars["session"]).expanding(min_periods=min_bars).std(ddof=1)
    return d / sd.reset_index(level=0, drop=True)


def bb_width(bars: pd.DataFrame, *, n: int, k: float) -> pd.Series:
    """Bollinger width as a fraction of the mean: `2k*sd/ma`. Causal."""
    c = bars["close"]
    ma = c.rolling(n).mean()
    return 2.0 * k * c.rolling(n).std(ddof=1) / ma


def donchian(bars: pd.DataFrame, *, n: int) -> pd.DataFrame:
    """The highest high and lowest low of the `n` bars BEFORE this one.

    `shift(1)` is the whole content of the function: a breakout level that
    includes the breaking bar's own high can never be broken, and the bug
    presents as a strategy that simply never fires.
    """
    return pd.DataFrame({
        "dc_high": bars["high"].rolling(n).max().shift(1),
        "dc_low": bars["low"].rolling(n).min().shift(1),
    })
