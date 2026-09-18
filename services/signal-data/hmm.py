"""A Gaussian hidden Markov model in numpy, for E4 and nothing else yet.

WHY NOT `hmmlearn`. `pyproject.toml`'s versions are locked and a dependency
change is its own PR with the lockfile diff reviewed. E4 needs one model
class -- k-state, full-covariance Gaussian emissions, EM -- and that is ~150
lines whose correctness a test can PROVE by brute force (enumerate every
state path on a four-bar chain and compare the likelihood), which is a
stronger guarantee than a wheel's changelog. If a second consumer ever needs
Student-t emissions or left-right topologies, that is the day to buy the
dependency.

TWO KINDS OF POSTERIOR, AND ONLY ONE IS ALLOWED INTO A FEATURE. `filtered`
is P(S_t | x_1..t): what was knowable at bar t. `posteriors` is the smoothed
P(S_t | x_1..T), which reads the future and is for diagnostics only.
`p_build` and `p_expand` must come from `filtered` -- a smoothed posterior on
the way into a score is lookahead wearing a probability's name.

SEGMENTS. `lengths` splits `X` into contiguous runs (sessions). The chain is
re-initialised from `pi` at each run's start, because a gap between sessions
is not a transition anything here has a model of.

Everything is in log space. Emission densities on five standardised
observations underflow a float well inside one session.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_normal


@dataclass(frozen=True, slots=True)
class GaussianHMM:
    """`pi (k,)`, `A (k,k)` rows summing to one, `means (k,d)`, `covs (k,d,d)`."""

    pi: np.ndarray
    A: np.ndarray
    means: np.ndarray
    covs: np.ndarray

    @property
    def k(self) -> int:
        return int(self.pi.shape[0])


def _segments(lengths: np.ndarray, n: int) -> list[tuple[int, int]]:
    if int(lengths.sum()) != n:
        raise ValueError(f"lengths sum to {int(lengths.sum())}, X has {n} rows")
    if (lengths <= 0).any():
        raise ValueError("every segment needs at least one row")
    ends = np.cumsum(lengths)
    return [(int(e - length), int(e)) for e, length in zip(ends, lengths, strict=True)]


def _log_emissions(m: GaussianHMM, X: np.ndarray) -> np.ndarray:
    """(T, k) log N(x_t | mean_j, cov_j)."""
    return np.column_stack([
        multivariate_normal(mean=m.means[j], cov=m.covs[j], allow_singular=False).logpdf(X)
        for j in range(m.k)
    ]).reshape(len(X), m.k)


def _forward(log_pi: np.ndarray, log_A: np.ndarray, log_b: np.ndarray) -> np.ndarray:
    """Log alpha for one segment: (T, k), unnormalised."""
    t_len = log_b.shape[0]
    la = np.empty_like(log_b)
    la[0] = log_pi + log_b[0]
    for t in range(1, t_len):
        la[t] = logsumexp(la[t - 1][:, None] + log_A, axis=0) + log_b[t]
    return la


def _backward(log_A: np.ndarray, log_b: np.ndarray) -> np.ndarray:
    t_len = log_b.shape[0]
    lb = np.zeros_like(log_b)
    for t in range(t_len - 2, -1, -1):
        lb[t] = logsumexp(log_A + (log_b[t + 1] + lb[t + 1])[None, :], axis=1)
    return lb


def loglik(m: GaussianHMM, X: np.ndarray, lengths: np.ndarray) -> float:
    """log P(X | m), summed over segments."""
    log_b = _log_emissions(m, X)
    total = 0.0
    for s, e in _segments(lengths, len(X)):
        la = _forward(np.log(m.pi), np.log(m.A), log_b[s:e])
        total += float(logsumexp(la[-1]))
    return total


def filtered(m: GaussianHMM, X: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    """P(S_t | x_1..t), (T, k). No lookahead: the only posterior a feature may use."""
    log_b = _log_emissions(m, X)
    out = np.empty_like(log_b)
    for s, e in _segments(lengths, len(X)):
        la = _forward(np.log(m.pi), np.log(m.A), log_b[s:e])
        out[s:e] = np.exp(la - logsumexp(la, axis=1, keepdims=True))
    return out


def posteriors(m: GaussianHMM, X: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    """P(S_t | x_1..T), (T, k). Smoothed -- reads the future. Diagnostics only."""
    log_b = _log_emissions(m, X)
    out = np.empty_like(log_b)
    for s, e in _segments(lengths, len(X)):
        la = _forward(np.log(m.pi), np.log(m.A), log_b[s:e])
        lb = _backward(np.log(m.A), log_b[s:e])
        lg = la + lb
        out[s:e] = np.exp(lg - logsumexp(lg, axis=1, keepdims=True))
    return out


def viterbi(m: GaussianHMM, X: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    """The single most likely state path, (T,) ints."""
    log_b = _log_emissions(m, X)
    log_A = np.log(m.A)
    path = np.empty(len(X), dtype=np.int64)
    for s, e in _segments(lengths, len(X)):
        seg = log_b[s:e]
        t_len = seg.shape[0]
        delta = np.empty_like(seg)
        back = np.zeros((t_len, m.k), dtype=np.int64)
        delta[0] = np.log(m.pi) + seg[0]
        for t in range(1, t_len):
            cand = delta[t - 1][:, None] + log_A
            back[t] = cand.argmax(axis=0)
            delta[t] = cand.max(axis=0) + seg[t]
        st = int(delta[-1].argmax())
        for t in range(t_len - 1, -1, -1):
            path[s + t] = st
            st = int(back[t, st])
    return path


def _init(X: np.ndarray, k: int, rng: np.random.Generator) -> GaussianHMM:
    """k means drawn from the data, shared covariance, sticky transitions."""
    d = X.shape[1]
    means = X[rng.choice(len(X), size=k, replace=False)]
    cov = np.cov(X, rowvar=False).reshape(d, d) + np.eye(d) * 1e-3
    A = np.full((k, k), 0.1 / max(k - 1, 1))
    np.fill_diagonal(A, 0.9)
    return GaussianHMM(pi=np.full(k, 1.0 / k), A=A, means=means, covs=np.stack([cov] * k))


def fit(X: np.ndarray, lengths: np.ndarray, *, k: int, n_iter: int = 200,
        tol: float = 1e-4, seed: int = 0, reg: float = 1e-6) -> tuple[GaussianHMM, list[float]]:
    """Baum-Welch from a seeded start. Returns the model and its log-likelihood trace.

    The trace is non-decreasing by construction; `test_hmm` pins that, because
    an M-step with a sign error still converges -- to the wrong place.
    """
    X = np.asarray(X, dtype=float)
    if X.ndim != 2:
        raise ValueError(f"X must be (T, d), got shape {X.shape}")
    lengths = np.asarray(lengths, dtype=np.int64)
    segs = _segments(lengths, len(X))
    d = X.shape[1]
    m = _init(X, k, np.random.default_rng(seed))
    trace: list[float] = []

    for _ in range(n_iter):
        log_b = _log_emissions(m, X)
        log_A = np.log(m.A)
        gamma = np.empty_like(log_b)
        xi_sum = np.zeros((k, k))
        pi_sum = np.zeros(k)
        ll = 0.0
        for s, e in segs:
            seg = log_b[s:e]
            la = _forward(np.log(m.pi), log_A, seg)
            lb = _backward(log_A, seg)
            z = float(logsumexp(la[-1]))
            ll += z
            gamma[s:e] = np.exp(la + lb - z)
            pi_sum += gamma[s]
            if e - s > 1:
                # (T-1, k, k): alpha_t(i) A_ij b_{t+1}(j) beta_{t+1}(j) / P(X)
                lxi = la[:-1, :, None] + log_A[None] + (seg[1:] + lb[1:])[:, None, :] - z
                xi_sum += np.exp(lxi).sum(axis=0)
        trace.append(ll)

        # M-step.
        pi = pi_sum / pi_sum.sum()
        A = xi_sum / np.maximum(xi_sum.sum(axis=1, keepdims=True), 1e-300)
        w = gamma.sum(axis=0)
        means = (gamma.T @ X) / w[:, None]
        covs = np.empty((k, d, d))
        for j in range(k):
            xc = X - means[j]
            covs[j] = (gamma[:, j, None] * xc).T @ xc / w[j] + np.eye(d) * reg
        m = GaussianHMM(pi=pi, A=A, means=means, covs=covs)

        if len(trace) > 1 and trace[-1] - trace[-2] < tol:
            break
    return m, trace
