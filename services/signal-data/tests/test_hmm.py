"""`hmm.py` proven rather than trusted: brute force on a chain short enough to enumerate."""

from __future__ import annotations

from itertools import pairwise, product

import numpy as np
import pytest
from scipy.stats import multivariate_normal

import hmm


def planted(n: int = 600, seed: int = 0) -> tuple[np.ndarray, np.ndarray, hmm.GaussianHMM]:
    """Two well-separated states with sticky transitions; returns X, states, truth."""
    rng = np.random.default_rng(seed)
    truth = hmm.GaussianHMM(
        pi=np.array([0.5, 0.5]),
        A=np.array([[0.95, 0.05], [0.10, 0.90]]),
        means=np.array([[-2.0, 0.0], [2.0, 1.0]]),
        covs=np.stack([np.eye(2) * 0.3, np.eye(2) * 0.3]),
    )
    states = np.empty(n, dtype=int)
    states[0] = rng.choice(2, p=truth.pi)
    for t in range(1, n):
        states[t] = rng.choice(2, p=truth.A[states[t - 1]])
    X = np.array([rng.multivariate_normal(truth.means[s], truth.covs[s]) for s in states])
    return X, states, truth


def test_the_likelihood_equals_a_brute_force_sum_over_every_path() -> None:
    _, _, m = planted()
    rng = np.random.default_rng(1)
    X = rng.standard_normal((4, 2))
    lengths = np.array([4])

    total = 0.0
    for path in product(range(2), repeat=4):
        p = m.pi[path[0]]
        for a, b in pairwise(path):
            p *= m.A[a, b]
        for t, s in enumerate(path):
            p *= multivariate_normal(m.means[s], m.covs[s]).pdf(X[t])
        total += p
    assert hmm.loglik(m, X, lengths) == pytest.approx(np.log(total), rel=1e-9)


def test_segments_are_independent_chains_restarted_from_pi() -> None:
    _, _, m = planted()
    X = np.random.default_rng(2).standard_normal((6, 2))
    joint = hmm.loglik(m, X, np.array([6]))
    split = hmm.loglik(m, X, np.array([3, 3]))
    separate = hmm.loglik(m, X[:3], np.array([3])) + hmm.loglik(m, X[3:], np.array([3]))
    assert split == pytest.approx(separate)
    assert split != pytest.approx(joint)


def test_em_never_decreases_the_likelihood() -> None:
    X, _, _ = planted()
    _, trace = hmm.fit(X, np.array([len(X)]), k=2, n_iter=50, tol=0.0)
    assert len(trace) >= 2
    assert all(b >= a - 1e-6 for a, b in pairwise(trace))


def test_a_planted_two_state_chain_is_recovered() -> None:
    X, states, truth = planted(n=1500)
    m, _ = hmm.fit(X, np.array([len(X)]), k=2, seed=3)
    # Labels are arbitrary; align on the first mean's sign.
    order = np.argsort(m.means[:, 0])
    assert m.means[order] == pytest.approx(truth.means, abs=0.15)
    assert np.diag(m.A[order][:, order]) == pytest.approx(np.diag(truth.A), abs=0.05)
    path = hmm.viterbi(m, X, np.array([len(X)]))
    agree = (order[path] == states).mean()
    assert agree > 0.97


def test_both_posteriors_are_distributions() -> None:
    X, _, m = planted(n=200)
    lengths = np.array([120, 80])
    for f in (hmm.filtered, hmm.posteriors):
        p = f(m, X, lengths)
        assert p.shape == (200, 2)
        assert p.sum(axis=1) == pytest.approx(np.ones(200))
        assert (p >= 0).all()


def test_filtered_does_not_read_the_future_and_smoothed_does() -> None:
    X, _, _ = planted(n=100)
    # Overlapping emissions, so a posterior is not saturated at 0/1 and the
    # future actually has something to say about the past.
    m = hmm.GaussianHMM(
        pi=np.array([0.5, 0.5]),
        A=np.array([[0.9, 0.1], [0.1, 0.9]]),
        means=np.array([[-0.3, 0.0], [0.3, 0.0]]),
        covs=np.stack([np.eye(2) * 4.0, np.eye(2) * 4.0]),
    )
    lengths = np.array([100])
    altered = X.copy()
    altered[60:] += 5.0
    f0, f1 = hmm.filtered(m, X, lengths), hmm.filtered(m, altered, lengths)
    assert f0[:60] == pytest.approx(f1[:60])
    g0, g1 = hmm.posteriors(m, X, lengths), hmm.posteriors(m, altered, lengths)
    assert not np.allclose(g0[:60], g1[:60])


def test_lengths_must_account_for_every_row() -> None:
    X, _, m = planted(n=10)
    with pytest.raises(ValueError, match="lengths sum"):
        hmm.loglik(m, X, np.array([4, 4]))
    with pytest.raises(ValueError, match="at least one row"):
        hmm.loglik(m, X, np.array([10, 0]))
