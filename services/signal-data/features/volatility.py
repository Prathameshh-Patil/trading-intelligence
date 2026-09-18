"""§2's volatility ensemble: Yang-Zhang, GARCH(1,1)-t, and the forecast.

Split out of `features/expansion.py` on 2026-09-18, which had reached 442 lines
holding three unrelated concerns. Layer 3's bar-shape features stay there; §6's
Hurst is in `features/hurst.py`.

⚠️ EVERYTHING HERE IS DIMENSIONLESS EXCEPT `r_hat_60`. These are standard
deviations of LOG returns. `r_hat_60` is the one place a sigma becomes a
distance, by multiplying by price -- a sigma read as a distance is a
factor-of-4000 error at gold's price, and it would pass a `>` filter by never
passing it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, signal
from scipy.special import gammaln

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
# mathematical.md §2's second leg: GARCH(1,1) with Student-t innovations.
#
# WHY HAND-ROLLED RATHER THAN `arch`. The log-likelihood below is ~40 lines
# given an optimiser, which is under the write-it-yourself threshold; `arch`
# would pull statsmodels in for one estimator. scipy earns its place twice --
# `minimize` for the fit, `lfilter` for the variance recursion.
#
# WHY STUDENT-t AND NOT GAUSSIAN. §2 says "because GC returns have fat tails",
# and that is a claim about the estimator as well as the data: fitting a t to a
# fat-tailed series returns a small nu, and a Gaussian one returns a large nu.
# A test pins that direction.
#
# ⚠️ DIMENSIONLESS, LIKE `yang_zhang`. `omega` and the returned variances are in
# squared LOG RETURNS. Converting to a distance means multiplying the square
# root by price, which `r_hat_60` does and nothing else may.


@dataclass(frozen=True, slots=True)
class GarchFit:
    """(omega, alpha, beta, nu). `alpha + beta` is the persistence."""
    omega: float
    alpha: float
    beta: float
    nu: float


# Leaves a little room below 1 so a fit that wants to sit on the boundary
# fails the stationarity check rather than returning a divergent forecast.
MAX_PERSISTENCE = 0.999
MIN_NU = 2.1          # variance is undefined at nu <= 2
# Above roughly this, the t is Gaussian for any practical purpose and nu stops
# being identified -- the likelihood is flat, so the bound is where it lands.
NU_MAX = 200.0
MIN_OBS = 250         # four parameters need a sample; 250 is already thin


def _garch_variance(r: np.ndarray, omega: float, alpha: float, beta: float) -> np.ndarray:
    """The conditional variance path, as a first-order filter.

    `s2[i] = (omega + alpha * r[i-1]^2) + beta * s2[i-1]` is exactly what
    `lfilter([1], [1, -beta], x)` computes, so the per-bar Python loop the
    likelihood would otherwise run 10^5 times becomes one call. A test checks
    the filter against the plain loop, because a recursion that is subtly
    wrong still converges to something.
    """
    x = np.empty_like(r)
    x[0] = float(np.var(r))               # seed with the sample variance
    x[1:] = omega + alpha * r[:-1] ** 2
    return signal.lfilter([1.0], [1.0, -beta], x)


def _neg_loglik(theta: np.ndarray, r: np.ndarray, scale: float) -> float:
    """Negative log-likelihood of a standardised Student-t GARCH(1,1).

    `theta[0]` is omega DIVIDED BY the sample variance, not omega. Raw omega
    is ~1e-6 while alpha is ~0.08 and nu is ~6, and a six-order-of-magnitude
    spread across the parameter vector is what SLSQP handles worst: measured
    2026-09-18, the unscaled version returned omega = 24.3 on a series whose
    variance is 1e-4. Rescaling makes every parameter O(1).
    """
    w, alpha, beta, nu = theta
    omega = w * scale
    if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1 or nu <= 2:
        return np.inf
    s2 = _garch_variance(r, omega, alpha, beta)
    if np.any(s2 <= 0) or not np.all(np.isfinite(s2)):
        return np.inf
    # Standardised so the innovation has unit variance; the (nu-2) scaling is
    # what makes `omega/(1-alpha-beta)` the unconditional variance rather than
    # a multiple of it.
    c = (gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2)))
    ll = c - 0.5 * np.log(s2) - ((nu + 1) / 2) * np.log1p(r**2 / (s2 * (nu - 2)))
    return float(-ll.sum())


def garch_fit(r: np.ndarray, *, max_persistence: float = MAX_PERSISTENCE) -> GarchFit:
    """Maximum-likelihood GARCH(1,1)-t. Input is RETURNS, not prices.

    Stationary by construction: `alpha + beta` is bounded below 1 by the
    optimiser's constraint rather than checked afterwards, so there is no
    path that returns a divergent model.
    """
    r = np.asarray(r, dtype=float)
    if len(r) < MIN_OBS:
        raise ValueError(f"GARCH needs at least {MIN_OBS} returns to identify four "
                         f"parameters, got {len(r)}")
    scale = float(np.var(r))
    if scale <= 0:
        raise ValueError("returns have zero variance; there is no GARCH to fit")
    start = np.array([0.05, 0.08, 0.90, 8.0])
    # scipy-stubs types `minimize`'s objective as taking a 1-D
    # `ndarray[tuple[int], dtype[float64]]` positionally; `_neg_loglik`'s
    # plain `np.ndarray` does not match any overload. The call is correct at
    # runtime -- the parameter-recovery test is the proof -- so the ignore is
    # narrowed to the one diagnostic rather than silencing the module.
    out = optimize.minimize(  # type: ignore[call-overload]
        _neg_loglik, start, args=(r, scale), method="SLSQP",
        bounds=[(1e-8, 10.0), (0.0, 1.0), (0.0, 1.0), (MIN_NU, NU_MAX)],
        constraints=[{"type": "ineq",
                      "fun": lambda t: max_persistence - t[1] - t[2]}],
        options={"maxiter": 500, "ftol": 1e-12},
    )
    w, alpha, beta, nu = out.x
    return GarchFit(float(w * scale), float(alpha), float(beta), float(nu))


def garch_forecast(*, sigma2_t: float, params: GarchFit, m: int) -> float:
    """§2's m-step variance forecast. `m` is the count of bars in the horizon.

    `sigma2_bar + (alpha + beta)^m * (sigma2_t - sigma2_bar)` -- the current
    variance decaying toward the unconditional one at the persistence rate.
    """
    persist = params.alpha + params.beta
    if persist >= 1.0:
        raise ValueError(f"non-stationary fit: alpha+beta={persist:.6f}; the variance "
                         "forecast diverges and would put an infinite r_hat_60 into the filter")
    bar = params.omega / (1.0 - persist)
    return float(bar + persist**m * (sigma2_t - bar))


# --------------------------------------------------------------------------
# §2's ensemble: the two legs combined into one forecast, in USD per ounce.
#
# ⚠️ §2's GARCH HORIZON FORMULA IS THE TERMINAL VARIANCE, NOT THE CUMULATIVE
# ONE, and this module deliberately departs from it. The spec writes
#
#     sigma^2_{60,GARCH} = sigma_bar^2 + (alpha+beta)^m (sigma_t^2 - sigma_bar^2)
#
# which is the variance of the return AT bar t+m -- one 5-minute bar, twelve
# bars from now. §Objective's estimand is |P_{t+60} - P_t|, whose variance is
# the SUM over those twelve bars. Measured 2026-09-18 the two differ by 13x,
# and the terminal version would also sit on a different scale from the
# Yang-Zhang leg, so a 0.5/0.5 average of the two would be combining
# quantities that are not the same thing. `garch_forecast` above keeps the
# spec's per-step formula because the recursion needs it; `garch_sigma_h`
# aggregates it, and that is what the ensemble reads.

QUALITY_RATIO_MIN = 1.20   # §2's second filter


def yz_sigma_h(sigma_bar: float, *, m: int) -> float:
    """A per-bar Yang-Zhang sigma scaled to an `m`-bar horizon.

    Square-root-of-time. It assumes independent increments, which M1 measured
    directly -- the geometry surface is a random walk -- so the assumption is
    this archive's finding rather than a convenience.
    """
    return sigma_bar * np.sqrt(m)


def garch_sigma_h(*, sigma2_t: float, params: GarchFit, m: int) -> float:
    """Sigma of the cumulative `m`-bar return under a fitted GARCH.

    `sum_{k=1..m} E[sigma^2_{t+k}]` in closed form: `m * bar + (sigma2_t -
    bar) * rho * (1 - rho^m) / (1 - rho)`. A test checks it against summing
    the per-step forecasts, because a mis-derived geometric series produces a
    number that is wrong and entirely plausible.
    """
    rho = params.alpha + params.beta
    if rho >= 1.0:
        raise ValueError(f"non-stationary fit: alpha+beta={rho:.6f}")
    bar = params.omega / (1.0 - rho)
    total = m * bar + (sigma2_t - bar) * rho * (1.0 - rho**m) / (1.0 - rho)
    return float(np.sqrt(max(total, 0.0)))


def combine_sigma(*, sigma_yz: float, sigma_garch: float,
                  w_yz: float = 0.5, w_g: float = 0.5) -> float:
    """§2's ensemble. Weights are walk-forward-fitted; 0.5/0.5 is the start."""
    if abs(w_yz + w_g - 1.0) > 1e-9:
        raise ValueError(f"weights must sum to 1, got {w_yz} + {w_g} = {w_yz + w_g}")
    return w_yz * sigma_yz + w_g * sigma_garch


def r_hat_60(*, price: float, sigma_60: float) -> float:
    """The forecast 60-minute move, in USD per ounce.

    **This is the only place a dimensionless sigma becomes a distance.**
    `yang_zhang` and the GARCH legs are standard deviations of log returns;
    multiplying by price is what makes them comparable to §10's stops and
    §Objective's $15.00 threshold. A sigma read as a distance is a
    factor-of-3400 error at gold's price, and it would pass a `>` filter by
    never passing it.
    """
    return price * sigma_60


def r_ratio(r_hat: pd.Series, *, window: int) -> pd.Series:
    """§2's quality filter: `R_hat / trailing median(R_hat)`.

    **TRAILING, and that is the whole point.** A full-sample median knows the
    future, and it is the single easiest way to fake this filter: a calm early
    period reads as "elevated" against a median dragged down by calm that has
    not happened yet. NaN until the window is full, for the same reason
    `yang_zhang` is -- a partial median is a different number wearing the
    same name.
    """
    return r_hat / r_hat.rolling(window).median()
