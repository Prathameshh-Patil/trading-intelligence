"""The transcription guards, and the mix-matching that makes the null a null.

Two of these exist because of a bug that happened rather than one imagined.
`KAPPA_HORIZON_BARS` was first derived from the trade horizon (6 bars) instead
of transcribed. Every regime's kappa fell to ~0.3, the gate passed nothing, and
all four filtered arms reported zero signals -- which reads exactly like a
finding about the filter being too tight. It was the wrong number, and only the
recorded values catch it.
"""

from pathlib import Path

import pandas as pd
import pytest
from conftest import bars_at, entries_at

import families as fam
from features.regime_filter import regime_kappa

LABELS = (
    Path(__file__).resolve().parents[1]
    / "analysis/regimes_2026-09-02/regime_labels_window_5min_k3.csv"
)


@pytest.fixture(scope="module")
def training() -> pd.DataFrame:
    bars = pd.read_csv(LABELS, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    return bars[bars["session"].astype(str) <= "2026-07-19"]


def test_kappa_reproduces_the_recorded_values(training: pd.DataFrame) -> None:
    # daily_updates/2026-09-04.md: 0.842 / 0.833 / 0.798 on the training half.
    # Computed by a different script on a different day; if this moves, either
    # the labels changed or the horizon did.
    kappa = regime_kappa(training, horizon_bars=fam.KAPPA_HORIZON_BARS).sort_index()
    assert list(kappa.round(3)) == [0.842, 0.833, 0.798]


def test_the_conditions_reproduce_their_recorded_fire_counts(training: pd.DataFrame) -> None:
    # Same entry: A 0 (stub), B 405, C 386, D 213 on 3,516 training bars.
    fires = {k: int((v != 0).sum()) for k, v in fam.conditions(training).items()}
    assert fires == {"A": 0, "B": 405, "C": 386, "D": 213}


def test_the_null_is_matched_to_the_arms_own_mix() -> None:
    # Every bar here is wide enough to land in the 50+ ATR bucket, so the arm's
    # null must be that bucket's rate -- not an average over buckets it never
    # traded in. Getting this wrong is how ATR mix reads as edge.
    bars = bars_at(list(range(80)), [4000.0 + i for i in range(80)], ranges=[12.0] * 80)
    rates = pd.Series(
        {(1, "(50.0, 1000000000.0]"): 0.90, (1, "(0.0, 30.0]"): 0.10},
        index=pd.MultiIndex.from_tuples(
            [(1, "(50.0, 1000000000.0]"), (1, "(0.0, 30.0]")], names=["side", "bucket"]
        ),
    )
    out = fam.measure(
        bars, entries_at(bars, {20: 1, 25: 1}), rates, target=70.0, stop=20.0, horizon=30
    )
    assert out["legs"] > 0
    assert out["null_matched"] == pytest.approx(0.90)


def test_an_arm_that_never_fires_reports_zero_rather_than_raising() -> None:
    bars = bars_at(list(range(20)), [4000.0] * 20)
    out = fam.measure(
        bars, pd.Series(0, index=bars.index), pd.Series(dtype=float),
        target=70.0, stop=20.0, horizon=30,
    )
    assert out == {"signals": 0, "legs": 0}
