"""The log's integrity properties, which are the only reason to trust its report.

A calibration number is worth exactly as much as the guarantee that nobody
edited the forecast after seeing the outcome. Four of these tests are that
guarantee; the rest is arithmetic.
"""

from pathlib import Path

import pandas as pd
import pytest

import calibration as cal

SHOWN = {
    "at": "2026-09-05T12:00:00Z",
    "side": 1,
    "p": 0.61,
    "target": 70.0,
    "stop": 20.0,
    "horizon": 30,
    "bucket": {"regime": "trending-flow", "atr": "40-50"},
    "n": 214,
    "thresholds": {"z": 2.0, "window": "120min"},
    "feed": {"state": "live", "vendor": "databento", "gapCount": 0},
}


def _emit(path: Path, **over: object) -> str:
    return cal.emit(path, **{**SHOWN, **over})


def test_a_signal_missing_its_context_is_refused_at_the_boundary(tmp_path: Path) -> None:
    # `p` alone is not a forecast. Without the feed state and the bucket's N,
    # the row cannot be read back and judged by anyone, including us.
    short = {k: v for k, v in SHOWN.items() if k not in ("feed", "n")}
    with pytest.raises(ValueError, match="feed"):
        cal.emit(tmp_path / "log.ndjson", **short)


def test_settling_never_rewrites_the_forecast_that_was_shown(tmp_path: Path) -> None:
    # The property the whole file exists for: the signal line on disk after an
    # outcome lands is byte-identical to the one written before it.
    path = tmp_path / "log.ndjson"
    sid = _emit(path)
    before = path.read_text().splitlines()[0]

    cal.settle(path, sid, outcome=1, at="2026-09-05T12:30:00Z")

    lines = path.read_text().splitlines()
    assert lines[0] == before
    assert len(lines) == 2


def test_an_outcome_cannot_precede_the_signal_it_settles(tmp_path: Path) -> None:
    path = tmp_path / "log.ndjson"
    _emit(path)
    with pytest.raises(KeyError, match="never emitted"):
        cal.settle(path, "deadbeef0000", outcome=1, at="2026-09-05T12:30:00Z")


def test_an_outcome_is_written_once(tmp_path: Path) -> None:
    path = tmp_path / "log.ndjson"
    sid = _emit(path)
    cal.settle(path, sid, outcome=1, at="2026-09-05T12:30:00Z")
    with pytest.raises(ValueError, match="already settled"):
        cal.settle(path, sid, outcome=-1, at="2026-09-05T12:31:00Z")


def test_the_outcome_encoding_is_first_touchs_and_nothing_else(tmp_path: Path) -> None:
    # A bare True/False here would be a second, incompatible definition of
    # "hit" living alongside backtest.first_touch's.
    path = tmp_path / "log.ndjson"
    sid = _emit(path)
    with pytest.raises(ValueError, match="first_touch"):
        cal.settle(path, sid, outcome=True, at="2026-09-05T12:30:00Z")  # type: ignore[arg-type]


def test_ids_are_generated_so_two_signals_can_never_collide(tmp_path: Path) -> None:
    path = tmp_path / "log.ndjson"
    assert _emit(path) != _emit(path)


def test_an_open_signal_reads_back_with_no_outcome(tmp_path: Path) -> None:
    path = tmp_path / "log.ndjson"
    sid = _emit(path)
    log = cal.read(path)
    assert list(log["id"]) == [sid]
    assert log["outcome"].isna().all()
    feed = log.loc[0, "feed"]  # the nested context survives the round trip
    assert isinstance(feed, dict) and feed["state"] == "live"


def test_a_hand_edited_orphan_outcome_is_caught_on_read(tmp_path: Path) -> None:
    path = tmp_path / "log.ndjson"
    _emit(path)
    path.write_text(path.read_text() + '{"kind": "outcome", "id": "ghost", "at": "x", "outcome": 1}\n')
    with pytest.raises(ValueError, match="never emitted"):
        cal.read(path)


def test_reliability_reports_predicted_against_realised_with_its_n(tmp_path: Path) -> None:
    # Four signals at p=0.61, two of which reached the target. The model said
    # 61% and the tape said 50%; the table has to show both, not the average.
    path = tmp_path / "log.ndjson"
    for outcome in (1, 1, -1, 0):
        cal.settle(path, _emit(path), outcome=outcome, at="2026-09-05T12:30:00Z")

    row = cal.reliability(cal.read(path)).iloc[0]
    assert row["n"] == 4
    assert row["predicted"] == pytest.approx(0.61)
    assert row["realised"] == pytest.approx(0.50)
    assert row["thin"]  # four is not evidence, and the column says so


def test_reliability_on_a_log_with_nothing_settled_is_empty_not_zero(tmp_path: Path) -> None:
    # An unsettled signal is not a miss. Counting it as one reads as a badly
    # calibrated model rather than as a horizon that has not closed yet.
    path = tmp_path / "log.ndjson"
    _emit(path)
    assert cal.reliability(cal.read(path)).empty


def test_reliability_separates_the_bins(tmp_path: Path) -> None:
    path = tmp_path / "log.ndjson"
    for p, outcome in ((0.3, -1), (0.3, -1), (0.9, 1), (0.9, 1)):
        cal.settle(path, _emit(path, p=p), outcome=outcome, at="2026-09-05T12:30:00Z")

    table = cal.reliability(cal.read(path))
    assert len(table) == 2
    assert list(table["realised"]) == [0.0, 1.0]
    assert isinstance(table.index, pd.CategoricalIndex)
