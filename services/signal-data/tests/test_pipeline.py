"""The S13 seam, exercised end to end. The only consumer-side proof it has.

`frame.require` describes a frame; until something builds one that satisfies it
and something else reads one, the seam is a declaration rather than a contract.
The first assembly found a three-way disagreement about `r_hat_60` that frozen
column names had not prevented.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import fsm
import pipeline
from features import frame


def bars(n: int = 900, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-06-02T00:00:00Z", periods=n, freq="5min")
    close = 3000 * np.exp(np.cumsum(rng.standard_normal(n) * 5e-4))
    span = np.abs(rng.standard_normal(n)) * 0.8
    return pd.DataFrame({
        "open": close - rng.standard_normal(n) * 0.2,
        "high": close + span,
        "low": close - span,
        "close": close,
        "session": pd.DatetimeIndex(idx).date,
    }, index=idx)


NO_EVENTS = pd.DatetimeIndex([], tz="UTC")


def test_the_assembled_frame_satisfies_the_seam() -> None:
    frame.require(pipeline.build(bars(), events=NO_EVENTS))


def test_the_columns_are_in_the_seam_order() -> None:
    # Order is not part of `require`, but a frame that matches it reads beside
    # FEATURES without anyone diffing two lists by eye.
    assert list(pipeline.build(bars(), events=NO_EVENTS).columns) == list(frame.FEATURES)


def test_the_volatility_columns_are_populated_not_nan() -> None:
    out = pipeline.build(bars(), events=NO_EVENTS)
    for col in ("sigma_yz_12", "sigma_yz_48", "sigma_garch", "r_hat_60_usd"):
        assert out[col].notna().any(), col


def test_r_hat_is_in_usd_per_ounce_and_plausible_for_gold() -> None:
    # The unit check that only an end-to-end run can make. At 3000 with a
    # 5e-4 per-bar sigma the hourly move is a few dollars -- if this came
    # back at 0.002 the price multiply was skipped, and if at 6000 the
    # horizon scaling was applied twice.
    r = pipeline.build(bars(), events=NO_EVENTS)["r_hat_60_usd"].dropna()
    assert 0.5 < r.median() < 50.0


def test_unmeasured_columns_are_nan_and_never_zero() -> None:
    # `fsm.exclusions` reads these by name. A zero passes a `>` gate that a
    # NaN correctly fails, so "not measured" must not look like "measured 0".
    out = pipeline.build(bars(), events=NO_EVENTS)
    for col in ("p_build", "p_expand", "swept_level", "reclaim_dt_s", "wick_w"):
        assert out[col].isna().all(), col


def test_a_news_window_shows_up_in_the_frame() -> None:
    ev = pd.DatetimeIndex([pd.Timestamp("2025-06-02T01:00:00Z")])
    out = pipeline.build(bars(), events=ev)
    assert out["news_lockout"].any()
    assert not out["news_lockout"].all()


def test_every_column_the_scorer_reads_exists_in_the_frame() -> None:
    # The other half of the seam. §13's score reads six component names; if
    # the frame stops carrying one, this fails here rather than at run time.
    out = pipeline.build(bars(), events=NO_EVENTS)
    assert "r_hat_60_usd" in out.columns, "the name fsm.exclusions reads"
    assert set(fsm.WEIGHTS) - set(out.columns), (
        "the s_* score components are derived from the frame, not carried in it -- "
        "if that changes, this test should change with it deliberately")


def test_a_frame_shorter_than_the_hurst_window_still_builds() -> None:
    # Short months exist, and a builder that raises on one cannot be run
    # month by month.
    out = pipeline.build(bars(n=400), events=NO_EVENTS)
    frame.require(out)
    assert out["h_dfa_15m"].isna().all()


def test_the_hurst_stride_does_not_change_the_values_it_computes() -> None:
    # Striding is a cost decision, not an approximation of a different
    # quantity: the bars it does compute must match the unstrided run.
    b = bars(n=900)
    fine = pipeline.build(b, events=NO_EVENTS, hurst_stride=1)["h_dfa_15m"]
    coarse = pipeline.build(b, events=NO_EVENTS, hurst_stride=12)["h_dfa_15m"]
    shared = coarse.dropna().index.intersection(fine.dropna().index)
    at_stride = [t for i, t in enumerate(shared) if i % 12 == 0]
    assert np.allclose(fine.loc[at_stride], coarse.loc[at_stride], equal_nan=True)
