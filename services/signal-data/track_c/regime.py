"""Regime quantities: ATR, the volatility ratio, Hurst, and trailing ranks.

Every estimator is imported from `features/` and never re-spelled here --
`features.expansion.atr`, `features.volatility.yang_zhang`,
`features.hurst.hurst_dfa/hurst_vt`. This module decides **windows and
cadence**, which are Track C's choices, and nothing else.

WHY THERE IS NO GARCH LEG HERE. §2's ensemble is `0.5*YZ + 0.5*GARCH` and
`features/volatility.py` has both. Track C's four strategies read a volatility
*ratio* -- one window against another window of the same estimator -- and a
GARCH forecast is a different quantity (a level, one step ahead) that none of
the four conditions on. Fitting one per bar to feed nothing would be 40 lines
of runtime in service of a column no strategy reads. It stays available for
the day a strategy needs a forecast rather than a ratio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features import hurst as hu
from features.expansion import atr
from features.volatility import yang_zhang
from instruments import Instrument


def atr_usd(bars: pd.DataFrame, inst: Instrument, *, window: str, min_bars: int) -> pd.Series:
    """`features.expansion.atr` in USD per ounce rather than in ticks.

    The multiply-back is the same one `features.portable.atr_bp` performs
    before dividing by price. Track C wants the distance itself, because §10's
    stop bounds are in USD and a stop compared against a tick count is the
    factor-of-a-thousand error `instruments.py` exists to prevent.
    """
    return atr(bars, inst, window=window, min_bars=min_bars) * inst.tick


def vol_ratio(bars: pd.DataFrame, *, fast: int, slow: int) -> pd.Series:
    """Yang-Zhang over `fast` bars divided by Yang-Zhang over `slow` bars.

    Dimensionless twice over: each leg is a standard deviation of log returns,
    and the ratio cancels even that. **Above 1 means the last hour is running
    hotter than its own day** -- which is what "expansion" means operationally,
    and it needs no threshold on the level of volatility, so it transfers
    across a five-year archive in which gold's price nearly doubled.
    """
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be a shorter window than slow ({slow}); "
                         "the ratio is meaningless otherwise")
    return yang_zhang(bars, n=fast) / yang_zhang(bars, n=slow)


def hurst_scales(window: int) -> tuple[int, ...]:
    """The scales BOTH estimators can use over a `window`-bar sample.

    **This is the trap `features/hurst.py` documents, met in practice.** DFA
    differences its input and so regresses over `window - 1` points while
    variance-time uses all `window`; at window = 256 that is enough to give VT
    the 64-bar scale and deny it to DFA, and two estimators fitted over
    different scale sets are not two readings of one quantity -- which is
    exactly what `hurst_agree` would then be asked to compare. Taking the
    profile length for both makes the comparison mean what it says.
    """
    return tuple(s for s in hu.SCALES if s >= hu.MIN_SCALE and (window - 1) // s >= 4)


def hurst_pair(bars: pd.DataFrame, *, window: int, step: int) -> pd.DataFrame:
    """Rolling DFA and variance-time Hurst, recomputed every `step` bars.

    **WHY STEPPED AND HELD, WHICH IS A DECISION AND NOT AN OPTIMISATION.** H is
    a property of the whole `window`-bar sample. Advancing that window by one
    bar changes 1/256th of its input and moves the estimate by far less than
    its own standard error, so a per-bar recomputation buys precision that is
    not there and costs `step` times the runtime -- measured at 5-minute bars
    over five years, the difference between roughly half a minute and roughly
    six. The held value is always the LAST COMPUTED one, never an interpolated
    one, so it is stale by up to `step` bars and never early by any.
    """
    scales = hurst_scales(window)
    if len(scales) < 3:
        raise ValueError(f"a {window}-bar Hurst window admits only {len(scales)} shared "
                         "scales; three is the minimum for a log-log slope")
    lp = np.log(bars["close"].to_numpy(dtype=float))
    dfa = np.full(len(lp), np.nan)
    vt = np.full(len(lp), np.nan)
    for i in range(window, len(lp) + 1, step):
        seg = lp[i - window:i]
        dfa[i - 1] = hu.hurst_dfa(seg, scales)
        vt[i - 1] = hu.hurst_vt(seg, scales)
    out = pd.DataFrame({"h_dfa": dfa, "h_vt": vt}, index=bars.index).ffill()
    out["h_agree"] = [hu.hurst_agree(a, b) for a, b in zip(out["h_dfa"], out["h_vt"], strict=True)]
    return out


def pct_rank(s: pd.Series, *, lookback: int) -> pd.Series:
    """Where each value sits in its own trailing `lookback` sample, in [0, 1].

    Inclusive of the current bar, which is what makes it causal: the rank is
    of a sample that ends now. NaN until the window is full -- a percentile of
    forty observations called a percentile of 2,880 is a different statistic.
    """
    return s.rolling(lookback, min_periods=lookback).rank(pct=True)
