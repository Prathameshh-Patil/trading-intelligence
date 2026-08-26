"""The S1 contract's own numbers, asserted against the real fixture.

Every figure here comes from plans/team/contracts.md S1, which got them from a
different script on a different machine. If one of these moves, either the
fixture changed or the reader is wrong -- both are worth stopping for.
"""

from pathlib import Path

import pandas as pd
import pytest

import s1

FIXTURE = Path(__file__).resolve().parents[1] / "data/fixtures/gc_ticks_1session.parquet"


@pytest.fixture(scope="module")
def ticks() -> pd.DataFrame:
    return s1.load_ticks(FIXTURE)


def test_fixture_matches_the_contract(ticks: pd.DataFrame) -> None:
    assert len(ticks) == 77_532
    assert set(ticks["symbol"]) == {"GCQ6"}
    assert ticks["timestamp"].is_monotonic_increasing
    assert ticks[list(s1.DTYPES)].notna().all().all()


def test_session_delta_reproduces_the_findings(ticks: pd.DataFrame) -> None:
    # DELTA_CVD_FINDINGS.md §3, computed from the full month by another script.
    assert ticks["delta"].sum() == 1842
    assert ticks["session"].nunique() == 1


def test_unattributed_trades_are_present_and_contribute_nothing(ticks: pd.DataFrame) -> None:
    n = ticks["aggressor_side"] == "N"
    assert n.sum() == 1811
    assert ticks.loc[n, "delta"].abs().sum() == 0


def test_an_unknown_side_code_raises_rather_than_scoring_zero() -> None:
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-07-16T12:00:00Z"]),
        "price": [4000.0],
        "size": [1],
        "aggressor_side": ["X"],
    })
    with pytest.raises(ValueError, match="unknown aggressor_side"):
        s1.add_delta(df)


def test_duplicate_multi_fills_survive_the_read(ticks: pd.DataFrame) -> None:
    # 421 real multi-fills. Cleaning them moves session delta 8% -- the whole
    # reason nothing in the reader deduplicates.
    assert ticks.duplicated(subset=list(s1.DTYPES)).sum() == 421
    cleaned = ticks.drop_duplicates(subset=list(s1.DTYPES))["delta"].sum()
    assert cleaned == 1989
    assert abs(cleaned - 1842) / 1842 > 0.07


def test_unsigned_size_does_not_wrap_when_negated() -> None:
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-07-16T12:00:00Z"]),
        "price": [4000.0],
        "size": pd.array([7], dtype="uint32"),
        "aggressor_side": ["A"],
    })
    assert s1.add_delta(df)["delta"].iloc[0] == -7


def test_bars_reconcile_with_the_ticks_they_came_from(ticks: pd.DataFrame) -> None:
    bars = s1.minute_bars(ticks)
    assert bars["volume"].sum() == ticks["size"].sum()
    assert bars["trades"].sum() == len(ticks)
    assert bars["cvd"].iloc[-1] == ticks["delta"].sum()
    assert (bars["high"] >= bars["low"]).all()
