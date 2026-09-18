"""§8's classifier, tested on the claim the word "calibrated" makes.

§8 says "calibrated classifier" and attaches a 0.62 threshold to it. That is a
testable claim in two parts: the probabilities have to mean something (Brier,
reliability), and the specific band the threshold sits in has to fire at the
rate it advertises. A classifier that discriminates well and is calibrated
badly passes every accuracy test and makes 0.62 meaningless.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import calibration
import classifier


def separable(n: int = 400, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    x = (y[:, None] + rng.standard_normal((n, 4)) * 0.3)
    return x, y


def noise(n: int = 400, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 4)), rng.integers(0, 2, n)


# ------------------------------------------------------------- the feature set

def test_the_dead_flow_components_are_absent_from_the_feature_vector() -> None:
    # §8 specifies ten; OFI_z, D_div, CVD_z and H_buy died with the tape.
    assert not {"ofi_z", "d_div", "cvd_z", "h_buy"} & set(classifier.FEATURES)


def test_the_hmm_components_are_absent_until_e4_says_otherwise() -> None:
    # A column of NaN is not a feature, and including one makes `fit` raise on
    # data that is otherwise fine.
    assert not {"p_build", "p_expand"} & set(classifier.FEATURES)


def test_only_four_of_section_8s_ten_components_survive() -> None:
    # Pinned because it is the honest size of the claim: the 0.62 threshold
    # was chosen for a ten-feature model.
    assert len(classifier.FEATURES) == 4


# --------------------------------------------------------------------- fitting

def test_a_separable_problem_is_learned() -> None:
    x, y = separable()
    p = classifier.predict(classifier.fit(x, y), x)
    assert classifier.brier(p, y) < 0.05


def test_pure_noise_lands_near_a_coin_flip() -> None:
    x, y = noise()
    p = classifier.predict(classifier.fit(x, y), x)
    assert 0.20 < classifier.brier(p, y) <= 0.26


def test_one_class_is_refused_rather_than_fitted() -> None:
    # A classifier fitted on one class predicts that class forever, at
    # probability 1.0, and every downstream gate opens.
    with pytest.raises(ValueError, match="one class"):
        classifier.fit(np.zeros((50, 4)), np.zeros(50, dtype=int))


def test_mismatched_lengths_are_refused() -> None:
    with pytest.raises(ValueError, match="rows"):
        classifier.fit(np.zeros((50, 4)), np.zeros(40, dtype=int))


# ----------------------------------------------------------------- Brier score

def test_brier_is_zero_for_a_perfect_forecast_and_a_quarter_for_a_coin() -> None:
    y = np.array([0, 1, 0, 1])
    assert classifier.brier(y.astype(float), y) == 0.0
    assert classifier.brier(np.full(4, 0.5), y) == pytest.approx(0.25)


def test_a_confident_wrong_forecast_scores_worse_than_an_unsure_one() -> None:
    y = np.array([1, 1, 1, 1])
    assert classifier.brier(np.full(4, 0.1), y) > classifier.brier(np.full(4, 0.4), y)


# ----------------------------------------------------------- the §8 band check

def test_the_bucket_rate_returns_n_beside_the_rate() -> None:
    # A rate on nine samples is not a rate, so n travels with it.
    p = np.array([0.61, 0.62, 0.63, 0.10, 0.90])
    y = np.array([1, 1, 0, 0, 1])
    n, rate = classifier.bucket_rate(p, y)
    assert n == 3
    assert rate == pytest.approx(2 / 3)


def test_an_empty_bucket_is_nan_not_zero() -> None:
    # Zero would read as "the band never fires", which is a different
    # statement from "nothing landed in the band".
    n, rate = classifier.bucket_rate(np.array([0.1, 0.9]), np.array([0, 1]))
    assert n == 0
    assert np.isnan(rate)


def test_a_miscalibrated_model_is_caught_by_the_band_not_by_brier() -> None:
    # The whole reason design §7.5 asks for this check. A model that always
    # says 0.62 while the truth is 0.30 has a mediocre Brier -- and a band
    # rate of 0.30 against an advertised 0.62, which is unmissable.
    rng = np.random.default_rng(0)
    y = (rng.random(1000) < 0.30).astype(int)
    p = np.full(1000, 0.62)
    n, rate = classifier.bucket_rate(p, y)
    assert n == 1000
    assert rate == pytest.approx(0.30, abs=0.05)
    assert abs(rate - classifier.P_E_THRESHOLD) > 0.25


# ------------------------------------------------------------------- isotonic

def test_isotonic_recalibration_improves_a_miscalibrated_forecast() -> None:
    rng = np.random.default_rng(0)
    y = (rng.random(2000) < 0.30).astype(int)
    p = np.clip(rng.normal(0.62, 0.05, 2000), 0, 1)     # confident and wrong
    iso = classifier.fit_isotonic(p, y)
    assert classifier.brier(classifier.apply_isotonic(iso, p), y) < classifier.brier(p, y)


def test_fitting_and_applying_are_separate_calls() -> None:
    # The leak this module is shaped to prevent: recalibrating on the data you
    # then score. Two functions means a caller has to WRITE the mistake out
    # rather than get it from a default.
    assert not hasattr(classifier, "calibrate")
    assert callable(classifier.fit_isotonic) and callable(classifier.apply_isotonic)


def test_isotonic_is_monotone() -> None:
    # A recalibration map that reorders the forecasts is not a recalibration.
    rng = np.random.default_rng(3)
    p = rng.random(500)
    y = (rng.random(500) < p).astype(int)
    out = classifier.apply_isotonic(classifier.fit_isotonic(p, y), np.sort(p))
    assert np.all(np.diff(out) >= -1e-12)


# ------------------------------------------------------- reuse, not a second copy

def test_reliability_is_calibrations_and_not_a_second_implementation() -> None:
    # Two reliability functions is how two files quietly disagree about what
    # "calibrated" means. This module builds the frame and calls that one.
    assert not hasattr(classifier, "reliability")
    rng = np.random.default_rng(0)
    p = rng.random(500)
    y = (rng.random(500) < p).astype(int)
    out = calibration.reliability(pd.DataFrame({"p": p, "outcome": y}))
    assert {"n", "predicted", "realised", "thin"} <= set(out.columns)
    good = out[~out["thin"]]
    assert np.allclose(good["predicted"], good["realised"], atol=0.12)
