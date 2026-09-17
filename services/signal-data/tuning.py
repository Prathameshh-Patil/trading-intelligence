"""§7's fine-tuning protocol: purged walk-forward, a trial counter, a haircut.

WHAT §14 ASKS FOR AND WHAT IT OMITS. `mathematical.md` §14 specifies
24 months train / 6 validate / roll 3, and warns against random splits because
they "leak time-series information". A rolling split leaks too, and the leak it
does not mention is the larger one here: **a 90-minute label opened at 15:00 on
the last training day resolves inside the validation fold.** Purging closes it.
Nothing in §14 asks for purging, so it is added here and mutation-tested.

THE THREE GUARDS, AND WHY EACH IS MECHANICAL RATHER THAN A CONVENTION.

  purge + embargo   a boundary-crossing label is removed from training, and
                    deleting either turns a test red
  Trials            counts configurations INSIDE the tuner, with no reset and
                    no decrement, because a haircut is only honest if the
                    count is and the count is written by whoever reports it
  deflated_sharpe   the haircut itself -- at 200 configurations and 500
                    observations, a Sharpe near 1.0 arrives by chance

NO NEW DEPENDENCY. The normal CDF and its inverse come from the stdlib's
`statistics.NormalDist`. scipy would do it too and is not needed for it.

`is_monotone` is §7.3's parameter guard, and `MONOTONICITY_EXEMPT` is the one
place a parameter can be excused from it -- see the constant's comment, because
the exemption is arithmetic rather than discretion.
"""

from __future__ import annotations

from itertools import pairwise
from math import e as _e
from math import sqrt
from statistics import NormalDist

import pandas as pd

_N = NormalDist()
_EULER = 0.5772156649015329

# §7.3's guard does not apply to a parameter that enters expectancy TWICE.
# `d_usd` does: as the loss leg, and through §10's `R = max(2.5D, $10.00)` as
# the win leg. Measured 2026-09-18 from `e3_cost.surface` at 1.91 bp, EV runs
# 7.03 / 6.01 / 5.33 / 3.62 / 5.00 across D = $2.00..$5.00 -- a minimum at
# $4.00 where the target floor stops binding. The dip is the spec's own target
# formula, so the guard would reject the construction rather than find noise.
# **Before adding to this set, check whether the parameter enters EV twice.**
MONOTONICITY_EXEMPT: frozenset[str] = frozenset({"d_usd"})


def folds(
    index: pd.DatetimeIndex,
    *,
    holdout_start: pd.Timestamp,
    train_m: int = 24,
    val_m: int = 6,
    roll_m: int = 3,
    label_minutes: int = 90,
    embargo_days: int = 1,
) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """§14's walk-forward, purged and embargoed. Holdout is never returned.

    Returns `[]` rather than a short fold when history cannot hold one full
    train+validate window -- a walk-forward with a truncated training window
    is a walk-forward in name only, and it would be scored as if it were not.
    """
    cv = index[index < holdout_start]
    if len(cv) == 0:
        return []
    out: list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]] = []
    train_start = cv.min()
    while True:
        val_start = train_start + pd.DateOffset(months=train_m)
        val_end = val_start + pd.DateOffset(months=val_m)
        if val_end > cv.max():
            return out
        # Purge, then embargo. Both measured back from the validation start:
        # a label opened after `cut` resolves inside validation, and the
        # embargo takes a further span for serial correlation the label
        # horizon does not cover.
        cut = val_start - pd.Timedelta(minutes=label_minutes) - pd.Timedelta(days=embargo_days)
        tr = cv[(cv >= train_start) & (cv < cut)]
        va = cv[(cv >= val_start) & (cv < val_end)]
        if len(tr) and len(va):
            out.append((tr, va))
        train_start = train_start + pd.DateOffset(months=roll_m)


class Trials:
    """Counts configurations evaluated. No reset, no decrement, read-only count.

    The count lives here rather than in the caller because the haircut is only
    as honest as the number fed to it, and the number is otherwise written by
    whoever writes the summary.
    """

    __slots__ = ("_n",)

    def __init__(self) -> None:
        self._n = 0

    def record(self) -> None:
        self._n += 1

    @property
    def count(self) -> int:
        return self._n


def expected_max_sharpe(*, n_trials: int, n_obs: int) -> float:
    """The Sharpe a search of `n_trials` produces under a null of no skill.

    The expected maximum of `K` standard normals, scaled by the standard error
    of a Sharpe estimated on `n_obs` observations. This is the number a result
    has to beat before it is a result rather than the best of K coin flips.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be at least 1, got {n_trials}")
    if n_obs < 2:
        raise ValueError(f"n_obs must be at least 2, got {n_obs}")
    se = sqrt(1.0 / (n_obs - 1))
    if n_trials == 1:
        return se * _N.inv_cdf(1.0 - 1.0 / (2.0 * _e))
    k = float(n_trials)
    emax = (1.0 - _EULER) * _N.inv_cdf(1.0 - 1.0 / k) + _EULER * _N.inv_cdf(1.0 - 1.0 / (k * _e))
    return se * emax


def deflated_sharpe(sr: float, *, n_trials: int, n_obs: int) -> float:
    """Probability the observed Sharpe beats what the search alone would give.

    Below 0.5 means the number is worse than the best of `n_trials` coin
    flips. A configuration that does not survive this is not reported as a
    result -- §7.4.
    """
    sr0 = expected_max_sharpe(n_trials=n_trials, n_obs=n_obs)
    # Standard error of a Sharpe estimate; the SR^2/2 term is the correction
    # for the estimate's own variance and matters once SR exceeds ~1.
    se = sqrt((1.0 + 0.5 * sr * sr) / (n_obs - 1))
    return float(_N.cdf((sr - sr0) / se))


def is_monotone(profile: list[float], *, max_reversals: int = 0) -> bool:
    """§7.3's guard: does performance move one way across a parameter's range?

    Real profiles are noisy, so `max_reversals` allows a stated number of
    sign changes. A profile needing more than that is being fit to noise, and
    §7.3 says that is a finding -- the parameter freezes at the spec's value.
    """
    d = [b - a for a, b in pairwise(profile) if b != a]
    if len(d) < 2:
        return True
    reversals = sum(1 for a, b in pairwise(d) if (a > 0) != (b > 0))
    return reversals <= max_reversals


def haircut_report(sr: float, trials: Trials, n_obs: int) -> str:
    """One line, for the fold write-up. Takes the counter, never a bare int.

    Taking `Trials` rather than an int is the point: a caller cannot pass a
    number it made up without first constructing a counter that recorded them.
    """
    dsr = deflated_sharpe(sr, n_trials=max(trials.count, 1), n_obs=n_obs)
    sr0 = expected_max_sharpe(n_trials=max(trials.count, 1), n_obs=n_obs)
    verdict = "REPORTABLE" if dsr >= 0.95 else "not reportable"
    return (f"SR {sr:.3f} over {n_obs} obs, {trials.count} configurations tried; "
            f"null expects {sr0:.3f}; deflated {dsr:.3f} -> {verdict}")


__all__ = ["MONOTONICITY_EXEMPT", "Trials", "deflated_sharpe", "expected_max_sharpe",
           "folds", "haircut_report", "is_monotone"]
