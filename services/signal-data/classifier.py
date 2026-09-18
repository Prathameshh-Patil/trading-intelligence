"""§8's calibrated expansion classifier -- the thing that produces `p_E`.

`fsm.exclusions` reads `row["p_e"]` and rejects below 0.62, and until now
nothing produced it. This is that.

⚠️ §8's FEATURE VECTOR IS DOWN TO FOUR LIVE COMPONENTS. It specifies ten:

    Z_L = [OFI_z, D_div, CVD_z, H, P(B_t), P(E_{t+1}), H_buy, R_hat_60,
           S_sweep, S_reclaim]

**Four died with the tape** -- `OFI_z`, `D_div`, `CVD_z`, `H_buy` -- and two
more (`P(B_t)`, `P(E_{t+1})`) are NaN until E4 says the HMM survives. That
leaves `H`, `R_hat_60`, `S_sweep`, `S_reclaim`. A four-feature logistic is a
much weaker claim than a ten-feature one, and the threshold §8 attaches to it
(0.62) was chosen for the ten.

CALIBRATION IS A TESTABLE CLAIM, NOT AN ADJECTIVE. §8 says "calibrated
classifier"; design §7.5 turns that into three checks -- Brier score, a
reliability diagram, and the one that matters: **if the `p_E` in [0.60, 0.64]
bucket does not fire near 62% of the time, the 0.62 threshold means nothing.**
`bucket_rate` is that check.

THE ISOTONIC FIT IS THE LEAK THIS MODULE IS SHAPED TO PREVENT. Recalibrating on
the data you then score is how a miscalibrated model reports perfect
calibration. `fit_isotonic` takes the INNER fold and nothing else, and the two
steps are separate functions so a caller cannot pass one dataset to both by
accident -- they have to write the mistake out.

RELIABILITY IS NOT REIMPLEMENTED HERE. `calibration.reliability` already
computes it, and two of them is how two files quietly disagree about what
"calibrated" means. Build `pd.DataFrame({"p": p, "outcome": y})` and call it.
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

# §8's surviving components. `p_build`/`p_expand` are absent rather than listed
# and NaN: a feature the fit cannot use is not a feature, and including a
# column of NaN would make `fit` raise on data that is otherwise fine.
FEATURES: tuple[str, ...] = ("h_dfa_15m", "r_hat_60_usd", "s_sweep", "s_reclaim")

P_E_THRESHOLD = 0.62      # §8's minimum
BUCKET = (0.60, 0.64)     # the band whose realised rate must sit near the threshold


def fit(x: np.ndarray, y: np.ndarray) -> LogisticRegression:
    """§8's logistic, on the training fold only.

    No regularisation search and no class weighting. With four live features
    and a few hundred labels, a tuned penalty is another configuration the
    haircut has to pay for -- `tuning.Trials` counts what a search costs, and
    the cheapest search is the one not run.
    """
    if len(x) != len(y):
        raise ValueError(f"x has {len(x)} rows and y has {len(y)}")
    if len(np.unique(y)) < 2:
        raise ValueError("y has one class; a classifier fitted on it predicts that class forever")
    return LogisticRegression(max_iter=1000).fit(x, y)


def predict(model: LogisticRegression, x: np.ndarray) -> np.ndarray:
    """`p_E` for each row."""
    return np.asarray(model.predict_proba(x)[:, 1], dtype=float)


def fit_isotonic(p_inner: np.ndarray, y_inner: np.ndarray) -> IsotonicRegression:
    """Recalibration map, fitted on the INNER fold and never on validation.

    Separate from `apply` on purpose: fitting and applying in one call makes
    the leak a default rather than a mistake someone has to write out.
    """
    return IsotonicRegression(out_of_bounds="clip").fit(p_inner, y_inner)


def apply_isotonic(iso: IsotonicRegression, p: np.ndarray) -> np.ndarray:
    return np.asarray(iso.predict(p), dtype=float)


def brier(p: np.ndarray, y: np.ndarray) -> float:
    """Mean squared error of the probability. 0 is perfect, 0.25 is a coin flip."""
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2))


def bucket_rate(p: np.ndarray, y: np.ndarray,
                bucket: tuple[float, float] = BUCKET) -> tuple[int, float]:
    """`(n, realised rate)` inside a probability band. Design §7.5's check.

    **If the [0.60, 0.64] band does not fire near 0.62, §8's threshold is void**
    until it does -- not a high bar, a meaningless one. Returns `n` beside the
    rate because a rate on nine samples is not a rate.
    """
    lo, hi = bucket
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    inside = (p >= lo) & (p < hi)
    n = int(inside.sum())
    return n, float(y[inside].mean()) if n else float("nan")
