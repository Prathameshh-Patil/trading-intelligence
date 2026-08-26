"""The runner's mechanics, and one finding it made executable.

Nothing here asks whether a strategy makes money -- Part B owns that question
and it is not answerable yet. What is testable now is that the runner reports
what A4, A5 and A6 say it must, and that it perturbs the right things.

The finding, in `test_a_z_threshold_does_not_inherit...`: A5 exists because
session delta is method-dependent at ~15-20%, and the design's example of what
that costs is "a rule that fires at delta > 200 fires somewhere between 170 and
240". That reasoning holds for a threshold denominated in CONTRACTS. It does
not hold for a z-score, which divides by its own standard deviation and so is
invariant to a uniform rescaling of delta. Two of the four candidates are
structurally immune; two are not. That is worth an executable assertion rather
than a paragraph, because it changes what A5 is evidence of.
"""

from functools import partial

import pandas as pd
import pytest
from conftest import bars_at, noise

import stage1
import strategies as st


def one_session(n: int = 60) -> pd.DataFrame:
    return bars_at(
        list(range(n)),
        [100.0 + (i % 7) * 0.1 for i in range(n)],
        deltas=noise(n),
        ranges=[0.5] * n,
    )


def two_candidates(bars: pd.DataFrame) -> dict[str, stage1.Candidate]:
    return {
        "delta_outlier": (
            partial(st.delta_outlier, bars),
            {"window": "30min", "min_bars": 10, "z": 1.0},
        ),
        "absorption_fade": (
            partial(st.absorption_fade, bars),
            {"min_ratio": 1.5, "min_delta": 5},
        ),
    }


def test_every_candidate_reports_every_variant_at_every_horizon() -> None:
    bars = one_session()
    out = stage1.run(two_candidates(bars), bars, horizons=(5, 15))

    assert set(out["variant"]) == {"actual", "null", "thr-20%", "thr+20%"}
    assert len(out) == 2 * 4 * 2
    assert out["n"].notna().all(), "A4: N sits next to every number, including a zero one"
    assert set(out["horizon"]) == {5, 15}


def test_the_perturbation_moves_delta_magnitudes_and_leaves_windows_alone() -> None:
    # A5 moves the delta magnitudes. A window length and a bar count are not
    # delta magnitudes and do not inherit the +/-15-20% error, so moving them
    # would be testing something nobody claimed.
    bars = one_session(40)
    seen: list[stage1.Thresholds] = []

    def spy(**kw: float | str) -> pd.Series:
        seen.append(dict(kw))
        return pd.Series(0, index=bars.index)

    stage1.run({"spy": (spy, {"window": "30min", "min_bars": 20, "z": 3.0})}, bars, horizons=(5,))

    assert [float(k["z"]) for k in seen] == pytest.approx([3.0, 2.4, 3.6])
    assert all(k["window"] == "30min" and k["min_bars"] == 20 for k in seen)
    assert len(seen) == 3, "the null does not re-run the strategy, it reshuffles its entries"


def test_a_non_numeric_threshold_named_for_perturbation_fails_loud() -> None:
    with pytest.raises(TypeError, match="not numeric"):
        stage1.perturb({"z": "three"}, 0.8)


def test_the_filter_variant_appears_only_when_a_filter_is_given() -> None:
    bars = one_session()
    cands = two_candidates(bars)

    assert "filtered" not in set(stage1.run(cands, bars, horizons=(5,))["variant"])

    def veto_everything(entries: pd.Series, bars: pd.DataFrame) -> pd.Series:
        return entries * 0

    out = stage1.run(cands, bars, horizons=(5,), decision_filter=veto_everything)
    filtered = out[out["variant"] == "filtered"]
    assert len(filtered) == 2
    # A6's whole point: a filter that improves the numbers by deleting the
    # sample has to be visible doing it, side by side with the unfiltered row.
    assert (filtered["n"] == 0).all()


def test_a_z_threshold_does_not_inherit_the_delta_error_a_magnitude_one_does() -> None:
    bars = bars_at(list(range(60)), [100.0] * 60, deltas=noise(59) + [1000], ranges=[0.5] * 60)
    scaled = bars.copy()
    scaled["delta"] = bars["delta"] * 1.2  # float, so the scaling stays exact
    scaled["cvd"] = scaled.groupby("session", sort=False)["delta"].cumsum()

    # A z-score divides by the standard deviation of the same series, so a
    # uniform rescale cancels top and bottom. Identical signals.
    pd.testing.assert_series_equal(
        st.delta_outlier(bars, window="30min", min_bars=10, z=3.0),
        st.delta_outlier(scaled, window="30min", min_bars=10, z=3.0),
    )

    # A threshold denominated in contracts does not cancel. 1,000 clears a
    # 1,100 floor only once delta is read 20% larger.
    assert (st.absorption_fade(bars, min_ratio=100.0, min_delta=1100) == 0).all()
    assert (st.absorption_fade(scaled, min_ratio=100.0, min_delta=1100) != 0).any()


def test_the_thin_flag_survives_into_the_report() -> None:
    # A4: a cell under 30 is reported and not acted on. backtest.py sets the
    # flag; the runner's job is to not lose it on the way out.
    #
    # The outlier sits at bar 50, not at the end: evaluate drops an entry on a
    # session's last bar because there is nothing after it to measure, so an
    # outlier parked there yields n=0 and tests nothing.
    bars = bars_at(list(range(60)), [100.0] * 60, deltas=noise(50) + [1000] + noise(9), ranges=[0.5] * 60)
    cands: dict[str, stage1.Candidate] = {
        "rare": (partial(st.delta_outlier, bars), {"window": "30min", "min_bars": 10, "z": 3.0})
    }
    out = stage1.run(cands, bars, horizons=(5,))
    actual = out[out["variant"] == "actual"].iloc[0]
    assert 0 < actual["n"] < 30
    assert bool(actual["thin"]) is True
