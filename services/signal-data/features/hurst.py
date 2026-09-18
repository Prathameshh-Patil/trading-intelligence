"""§6's Hurst exponent, by two independent estimators.

Split out of `features/expansion.py` on 2026-09-18. §2's volatility is in
`features/volatility.py`.

THE INPUT CONVENTION IS THE WHOLE TRAP. DFA integrates its input and
variance-time differences its input, so the same series fed to both in the
"obvious" way returns 0.5 from one and 1.5 from the other, and neither function
can tell it was misused. **Both take LOG PRICE LEVELS.**

§6 says, in terms: "Do not trade from one noisy Hurst estimate." That is what
`hurst_agree` is for, and the scorer reads `h_agree` rather than either
estimate alone.
"""

from __future__ import annotations

import numpy as np

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
