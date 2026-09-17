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

    `n = 1` divides by zero, and a one-bar variance is not a window anyway.
    Found by review 2026-09-18.
    """
    if n < 2:
        raise ValueError(f"Yang-Zhang needs a window of at least 2 bars, got {n}")
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


# --------------------------------------------------------------------------
# mathematical.md §6 -- Hurst, by two independent estimators.
#
# THE INPUT CONVENTION IS THE WHOLE TRAP. DFA integrates its input and
# variance-time differences its input, so the same series fed to both in the
# "obvious" way returns 0.5 from one and 1.5 from the other, and neither
# function can tell it was misused. **Both take LOG PRICE LEVELS.** Handing
# either one returns shifts H by about 1, which is the entire usable range.
#
# §6 also says, in terms: "Do not trade from one noisy Hurst estimate." That
# is what `hurst_agree` is for, and the scorer reads `h_agree` rather than
# either estimate alone.

# Scales in bars. Geometric, because the estimators regress against log(scale)
# and evenly-spaced scales would weight the long end by density alone.
_SCALES: tuple[int, ...] = (4, 8, 16, 32, 64, 128, 256)

# §6's "preferably H_5m > 0.50" alongside "H_15m > 0.55" is a tolerance of
# about 0.05 between two readings of the same series, so that is the default.
AGREE_TOL = 0.05


# DFA cannot use a scale below this and neither may variance-time, even though
# variance-time alone would be fine: `hurst_agree` compares the two, and H is
# scale-dependent, so two estimators regressed over DIFFERENT scale sets are
# not two readings of one quantity. Measured 2026-09-18 with a shared
# `(2,4,8,16,32)` on a pure random walk -- DFA silently dropped the 2 and VT
# did not -- `dfa 0.563, vt 0.510, agree False`: the gate closed on the one
# series whose answer is known to be 0.5. Found by review.
MIN_SCALE = 4


def _usable_scales(n: int, scales: tuple[int, ...]) -> list[int]:
    """Scales with at least four windows in `n` points, and never below
    `MIN_SCALE`. Fewer than four windows and the fluctuation at that scale is
    an average of two or three numbers."""
    return [s for s in scales if s >= MIN_SCALE and n // s >= 4]


def _loglog_slope(x: list[float], y: list[float]) -> float:
    """Least-squares slope of log y on log x, or NaN if y has no variation."""
    if len(x) < 3 or not all(v > 0 for v in y):
        return float("nan")
    return float(np.polyfit(np.log(x), np.log(y), 1)[0])


def hurst_dfa(logprice: np.ndarray, scales: tuple[int, ...] = _SCALES) -> float:
    """Detrended fluctuation analysis. Input is LOG PRICE LEVELS.

    The profile is built by differencing to returns and re-integrating them
    mean-removed, which is the standard DFA construction and is NOT a no-op:
    it removes the drift that `mathematical.md` §6 would otherwise read as
    persistence, for the same reason §2 uses Yang-Zhang over close-to-close.
    """
    r = np.diff(np.asarray(logprice, dtype=float))
    if len(r) < 4 * min(scales):
        return float("nan")
    profile = np.cumsum(r - r.mean())
    f = []
    # `_usable_scales` applies MIN_SCALE. A least-squares line through 2 or 3
    # points fits them almost exactly, so F(s) collapses toward zero, log F(s)
    # toward -inf, and the slope explodes: measured 2026-09-18, including s=2
    # returned H = 14.0 on a series whose true H is below 0.5.
    used = _usable_scales(len(profile), scales)
    if len(used) < 3:
        return float("nan")
    for s in used:
        w = profile[: len(profile) // s * s].reshape(-1, s)
        t = np.arange(s)
        # Least-squares line per window, residual RMS pooled across windows.
        coef = np.polyfit(t, w.T, 1)
        resid = w.T - (np.outer(t, coef[0]) + coef[1])
        f.append(float(np.sqrt((resid**2).mean())))
    return _loglog_slope([float(s) for s in used], f)


def hurst_vt(logprice: np.ndarray, scales: tuple[int, ...] = _SCALES) -> float:
    """Variance-time regression. Input is LOG PRICE LEVELS.

    `Var(X_{t+tau} - X_t) ~ tau^{2H}`, so the slope of log variance on log
    tau is `2H` -- §6's own formulation, halved here rather than in the
    caller so the two estimators return the same quantity.
    """
    x = np.asarray(logprice, dtype=float)
    if len(x) < 4 * min(scales):
        return float("nan")
    used = _usable_scales(len(x), scales)
    if len(used) < 3:
        return float("nan")
    v = [float(np.var(x[s:] - x[:-s], ddof=1)) for s in used]
    return _loglog_slope([float(s) for s in used], v) / 2.0


def hurst_agree(h1: float, h2: float, tol: float = AGREE_TOL) -> bool:
    """Whether two estimates of the same series are close enough to use.

    NaN never agrees -- an estimator that could not produce a number must not
    be read as confirming the one that could.
    """
    if not (np.isfinite(h1) and np.isfinite(h2)):
        return False
    return bool(abs(h1 - h2) <= tol)
