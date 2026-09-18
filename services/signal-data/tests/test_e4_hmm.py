"""E4's plumbing on fixtures. The fit on the archive is §17's and is not run here."""

from __future__ import annotations

import functools

import numpy as np
import pandas as pd
import pytest
from test_pipeline import NO_EVENTS, bars

import e4_hmm
import hmm
import pipeline
from features import frame as frame_mod

# `r_ratio` is NaN until `pipeline.RATIO_WINDOW` (5,760) bars have passed, so a
# fixture short of that has no complete observation row at all.
N = pipeline.RATIO_WINDOW + 1500


@functools.cache
def _built(n: int, spread: bool) -> pd.DataFrame:
    b = bars(n)
    if spread:
        b["spread_bp"] = 1.9 + np.random.default_rng(1).standard_normal(n) * 0.1
    return pipeline.build(b, events=NO_EVENTS)


def built(n: int = N, *, spread: bool = False) -> pd.DataFrame:
    return _built(n, spread).copy()


def test_the_thresholds_are_the_ones_section_17_commits() -> None:
    # Pinned so that nobody moves a gate after seeing which side a fit landed on.
    assert e4_hmm.MIN_SHARE == 0.02
    assert e4_hmm.MIN_STAY == 0.80
    assert e4_hmm.MIN_KAPPA == 0.75
    assert e4_hmm.MAX_COND == 50.0
    assert e4_hmm.MIN_SEP == 1.0
    assert e4_hmm.MIN_DELTA_LL == 0.05
    assert e4_hmm.LADDER_TOL == 0.25
    assert e4_hmm.SEEDS == (0, 1, 2, 3, 4)
    assert e4_hmm.OBS == ("r_hat_60_bp", "h_dfa_15m", "spread_bp", "range_compression",
                          "sigma_ratio")


def test_spread_is_refused_on_gc_rather_than_fit_on_nan() -> None:
    f = built()
    assert f["spread_bp"].isna().all()
    with pytest.raises(ValueError, match="this is GC"):
        e4_hmm.observations(f, spread=True)
    obs = e4_hmm.observations(f, spread=False)
    assert "spread_bp" not in obs.columns
    assert list(obs.columns) == ["r_hat_60_bp", "h_dfa_15m", "range_compression", "sigma_ratio",
                                 "segment"]


def test_with_spread_all_five_observations_are_present_and_finite() -> None:
    obs = e4_hmm.observations(built(spread=True), spread=True)
    assert list(obs.columns[:-1]) == list(e4_hmm.OBS)
    assert np.isfinite(obs.drop(columns="segment").to_numpy()).all()
    assert len(obs) > 0


def test_segments_break_at_session_changes_and_at_dropped_rows() -> None:
    f = built()
    obs = e4_hmm.observations(f, spread=False)
    seg = obs["segment"].to_numpy()
    sessions = f.loc[obs.index, "session"].astype(str).to_numpy()
    # Same segment implies same session ...
    for s in np.unique(seg):
        assert len(set(sessions[seg == s])) == 1
    # ... and consecutive rows of one segment are consecutive frame rows.
    pos = pd.Series(np.arange(len(f)), index=f.index).reindex(obs.index).to_numpy()
    same = seg[1:] == seg[:-1]
    assert (np.diff(pos)[same] == 1).all()
    assert e4_hmm.lengths_of(obs).sum() == len(obs)


def test_standardise_takes_its_moments_from_the_fit_rows_only() -> None:
    obs = e4_hmm.observations(built(), spread=False)
    mask = pd.Series(False, index=obs.index)
    mask.iloc[: len(obs) // 2] = True
    X, scaler = e4_hmm.standardise(obs, fit_mask=mask)
    fit_half = X[mask.to_numpy()]
    assert fit_half.mean(axis=0) == pytest.approx(np.zeros(4), abs=1e-9)
    assert fit_half.std(axis=0, ddof=1) == pytest.approx(np.ones(4), abs=1e-9)
    assert scaler.names == ("r_hat_60_bp", "h_dfa_15m", "range_compression", "sigma_ratio")


def synthetic_diag(*, k: int, shares: tuple[float, ...], stay: float = 0.9,
                   heldout: float = -5.0, ladder: bool = False,
                   sep: float = 3.0, cond: float = 2.0) -> e4_hmm.Diagnostics:
    return e4_hmm.Diagnostics(
        k=k, train_ll_per_bar=heldout, heldout_ll_per_bar=heldout, bic=0.0,
        share_viterbi=shares, share_gamma=shares, stay=(stay,) * k, kappa=(0.9,) * k,
        cond_A=cond, min_mahalanobis=sep, means=((0.0,) * 4,) * k, is_ladder=ladder,
    )


def test_a_one_percent_state_is_outcome_1_whatever_else_looks_good() -> None:
    d2 = synthetic_diag(k=2, shares=(0.5, 0.5))
    d3 = synthetic_diag(k=3, shares=(0.49, 0.50, 0.01), heldout=-4.0)
    assert e4_hmm.decide(d2, d3) == "outcome_1"


def test_a_third_state_that_buys_no_held_out_likelihood_is_outcome_3() -> None:
    d2 = synthetic_diag(k=2, shares=(0.5, 0.5), heldout=-5.00)
    d3 = synthetic_diag(k=3, shares=(0.3, 0.3, 0.4), heldout=-4.97)
    assert e4_hmm.decide(d2, d3) == "outcome_3"


def test_a_vol_ladder_is_outcome_3_even_when_likelihood_improves() -> None:
    d2 = synthetic_diag(k=2, shares=(0.5, 0.5), heldout=-5.0)
    d3 = synthetic_diag(k=3, shares=(0.3, 0.3, 0.4), heldout=-4.0, ladder=True)
    assert e4_hmm.decide(d2, d3) == "outcome_3"


def test_everything_passing_is_outcome_2() -> None:
    d2 = synthetic_diag(k=2, shares=(0.5, 0.5), heldout=-5.0)
    d3 = synthetic_diag(k=3, shares=(0.3, 0.3, 0.4), heldout=-4.0)
    assert e4_hmm.decide(d2, d3) == "outcome_2"


def test_the_ladder_test_reads_monotone_vol_means_and_flat_others() -> None:
    names = ("r_hat_60_bp", "h_dfa_15m", "range_compression", "sigma_ratio")
    ladder = hmm.GaussianHMM(
        pi=np.full(3, 1 / 3), A=np.eye(3),
        means=np.array([[-1.0, 0.0, -1.0, -1.0], [0.0, 0.1, 0.0, 0.0], [1.0, 0.2, 1.0, 1.0]]),
        covs=np.stack([np.eye(4)] * 3),
    )
    assert e4_hmm._is_ladder(ladder, names)
    # Same vol ladder, but the middle state sits 1 sd apart on Hurst: a real third state.
    means = ladder.means.copy()
    means[1, 1] = 1.0
    not_ladder = hmm.GaussianHMM(pi=ladder.pi, A=ladder.A, means=means, covs=ladder.covs)
    assert not e4_hmm._is_ladder(not_ladder, names)


def test_labels_put_e_on_the_highest_r_hat_and_c_on_the_lowest() -> None:
    names = ("r_hat_60_bp", "h_dfa_15m", "range_compression", "sigma_ratio")
    m = hmm.GaussianHMM(
        pi=np.full(3, 1 / 3), A=np.eye(3),
        means=np.array([[0.5, 0, 0, 0], [-1.0, 0, 0, 0], [2.0, 0, 0, 0]]),
        covs=np.stack([np.eye(4)] * 3),
    )
    assert e4_hmm.label_states(m, names) == {"C": 1, "B": 0, "E": 2}


def test_apply_fills_p_build_and_p_expand_in_unit_and_leaves_the_rest_nan() -> None:
    f = built()
    obs = e4_hmm.observations(f, spread=False)
    X, scaler = e4_hmm.standardise(obs, fit_mask=pd.Series(True, index=obs.index))
    m, _ = hmm.fit(X, e4_hmm.lengths_of(obs), k=3, n_iter=20)
    out = e4_hmm.apply(f, m, scaler, e4_hmm.label_states(m, scaler.names))

    frame_mod.require(out)
    filled = out.loc[obs.index, ["p_build", "p_expand"]]
    assert np.isfinite(filled.to_numpy()).all()
    assert ((filled >= 0) & (filled <= 1)).all().all()
    untouched = out.index.difference(obs.index)
    assert out.loc[untouched, ["p_build", "p_expand"]].isna().all().all()
    assert f["p_build"].isna().all()


def test_apply_refuses_a_two_state_model() -> None:
    f = built()
    obs = e4_hmm.observations(f, spread=False)
    X, scaler = e4_hmm.standardise(obs, fit_mask=pd.Series(True, index=obs.index))
    m, _ = hmm.fit(X, e4_hmm.lengths_of(obs), k=2, n_iter=5)
    with pytest.raises(ValueError, match="k=2"):
        e4_hmm.apply(f, m, scaler, e4_hmm.label_states(m, scaler.names))


def test_run_end_to_end_on_a_fixture_returns_both_models_and_a_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(e4_hmm, "SEEDS", (0,))
    f = built()
    diags, outcome, models, scaler = e4_hmm.run(f, spread=False)
    assert set(diags) == {2, 3} and set(models) == {2, 3}
    assert outcome in {"outcome_1", "outcome_2", "outcome_3"}
    assert len(scaler.names) == 4
    for d in diags.values():
        assert sum(d.share_viterbi) == pytest.approx(1.0)
        assert len(d.stay) == d.k
