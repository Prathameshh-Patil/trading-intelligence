"""Pooling arithmetic, and one end-to-end pass over the committed fixture.

The pooling test is the one that matters. Months differ in bar count by more
than 2x, so a mean of monthly rates and a rate off pooled counts are different
numbers -- and the wrong one is not obviously wrong when you read it.
"""

from pathlib import Path

import pandas as pd
import pytest

import base_rates as br

FIXTURE = Path(__file__).resolve().parents[1] / "data/fixtures/gc_ticks_1session.parquet"


def test_rates_are_counts_over_their_own_n() -> None:
    counts = pd.DataFrame({"n": [200, 50], "target": [40, 20], "stop": [150, 25]})
    out = br.rates(counts)
    assert list(out["p_target"]) == [0.20, 0.40]
    assert list(out["p_stop"]) == [0.75, 0.50]


def test_a_bucket_with_no_legs_is_nan_not_a_zero_hit_rate() -> None:
    # An ATR bucket the month never visited did not fail; it did not happen.
    # Reporting 0.0 there would drag a pooled average toward a rate nothing
    # produced, and would read as a bucket that never works.
    out = br.rates(pd.DataFrame({"n": [0], "target": [0], "stop": [0]}))
    assert out["p_target"].isna().all()


def test_pooling_sums_counts_rather_than_averaging_rates() -> None:
    # A long month at 10% and a short month at 50%. The mean of the rates is
    # 30%; the truth is 14%. This is why every function here returns counts.
    long_month = pd.DataFrame({"n": [1000], "target": [100], "stop": [700]})
    short_month = pd.DataFrame({"n": [100], "target": [50], "stop": [40]})

    pooled = br.rates(long_month.add(short_month, fill_value=0))
    assert pooled.loc[0, "p_target"] == pytest.approx(150 / 1100)

    mean_of_rates = (0.10 + 0.50) / 2
    assert pooled.loc[0, "p_target"] != pytest.approx(mean_of_rates)


def test_month_counts_over_the_real_fixture_is_internally_consistent() -> None:
    counts = br.month_counts(
        FIXTURE, target=70.0, stop=20.0, horizon=30, bar_size="5min",
        edges=[0, 30, 40, 50, 1e9], atr_window="60min", atr_min_bars=6,
    )
    assert list(counts.columns) == ["n", "target", "stop"]
    # target + stop + neither == n, so no leg is counted twice or dropped.
    assert (counts["target"] + counts["stop"] <= counts["n"]).all()
    assert counts["n"].sum() > 0
