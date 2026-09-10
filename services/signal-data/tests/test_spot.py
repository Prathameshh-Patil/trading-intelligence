"""Route 2's spot loader. The traps here are all "a number wearing the wrong name".

**No test touches the network.** `test_dukascopy.py` states the reason and it
holds here: a suite that fails when a vendor is briefly down is a suite people
learn to ignore. What is tested is the two ways this module could hand
downstream a frame that looks right and is not — a price that is the bid or the
ask rather than the mid, and a quote count that could be read as traded size —
plus the one that costs data: a day written with holes in it.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd
import pytest

import dukascopy as dk
import spot
from instruments import XAUUSD


def ticks(n: int = 120, *, start: str = "2026-05-04T00:00:00Z",
          bid: float = 3300.0, ask: float = 3300.6) -> pd.DataFrame:
    ts = pd.date_range(start, periods=n, freq="1s")
    return pd.DataFrame({"timestamp": ts, "bid": bid, "ask": ask,
                         "bid_vol": 0.1, "ask_vol": 0.1})


def test_bars_are_built_from_the_mid_and_not_from_either_side() -> None:
    # A bracket measured on the bid and filled on the ask is a measurement of
    # the spread wearing a strategy's name. Deliberately lopsided quotes.
    b = spot.minute_bars(ticks(bid=3300.0, ask=3301.0), XAUUSD)
    assert b["close"].iloc[0] == pytest.approx(3300.5)
    assert b["open"].iloc[0] != 3300.0, "opened on the bid"
    assert b["open"].iloc[0] != 3301.0, "opened on the ask"


def test_the_spread_is_carried_in_basis_points_beside_the_price() -> None:
    b = spot.minute_bars(ticks(bid=3300.0, ask=3301.0), XAUUSD)
    assert b["spread_bp"].iloc[0] == pytest.approx(1.0 / 3300.5 * 1e4)


def test_there_is_no_volume_column_anywhere_and_ticks_is_a_count() -> None:
    """The guardrail, and it is the whole reason this module is not `s1`.

    Spot has no aggregate size. `AllTick`'s `GOLD.md` is this repo's own record
    of a feed's activity count being read as volume; the defence is that the
    quantity is never called volume in the first place.
    """
    b = spot.minute_bars(ticks(n=90), XAUUSD)
    r = spot.resample(b, "5min", XAUUSD)
    for frame in (b, r):
        assert "volume" not in frame.columns
        assert "delta" not in frame.columns
        assert "cvd" not in frame.columns
    assert b["ticks"].iloc[0] == 60, "one tick per second for a minute"


def test_a_minute_with_no_quotes_is_dropped_not_zero_filled() -> None:
    """Bar N+5 is not five minutes after bar N. `backtest` slices on the index."""
    gap = pd.concat([ticks(n=60), ticks(n=60, start="2026-05-04T00:05:00Z")],
                    ignore_index=True)
    b = spot.minute_bars(gap, XAUUSD)
    assert len(b) == 2
    assert (b.index[1] - b.index[0]) == pd.Timedelta(minutes=5)


def test_the_session_boundary_comes_from_the_instrument_not_a_constant() -> None:
    """`s1` and `regimes` hardcode SESSION_SHIFT; a second instrument cannot."""
    late = ticks(n=60, start="2026-05-04T22:30:00Z")
    same_day = spot.minute_bars(late, dataclasses.replace(XAUUSD, session_shift=pd.Timedelta(0)))
    rolled = spot.minute_bars(late, XAUUSD)  # +2h rolls 22:30 onto the next date
    assert str(same_day["session"].iloc[0]) == "2026-05-04"
    assert str(rolled["session"].iloc[0]) == "2026-05-05"


def test_a_day_that_lost_an_hour_is_not_written(tmp_path: Path, monkeypatch) -> None:
    """A hole and a quiet hour are indistinguishable once they are on disk.

    `atr_bp` and `rv_slope` would read a missing hour as calm rather than as
    absent, so the day is left for the next run instead. This is the property
    that makes resuming by day worth anything.
    """
    def flaky(symbol, hour, **kw):
        if hour.hour == 7:
            raise ConnectionError("reset")
        return ticks(n=5, start=f"{hour:%Y-%m-%dT%H:%M:%S}Z")

    monkeypatch.setattr(dk, "fetch_hour", flaky)
    spot.pull("XAUUSD", ["2026-05"], tmp_path, pause=0.0)
    assert list(tmp_path.glob("*.parquet")) == [], "wrote a day with a hole in it"


def test_a_clean_day_is_written_and_a_shut_market_is_a_real_answer(
    tmp_path: Path, monkeypatch
) -> None:
    """An hour with no ticks is a zero-byte file, not a failure -- weekends."""
    def quiet(symbol, hour, **kw):
        return dk.decode_bi5(b"", symbol, hour)

    monkeypatch.setattr(dk, "fetch_hour", quiet)
    spot.pull("XAUUSD", ["2026-05"], tmp_path, pause=0.0)
    written = sorted(tmp_path.glob("*.parquet"))
    assert len(written) == 31, "May has 31 days and every one of them resolved"
    assert len(pd.read_parquet(written[0])) == 0


def test_a_day_already_on_disk_is_not_fetched_again(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def counted(symbol, hour, **kw):
        calls.append(hour)
        return ticks(n=1, start=f"{hour:%Y-%m-%dT%H:%M:%S}Z")

    monkeypatch.setattr(dk, "fetch_hour", counted)
    spot.pull("XAUUSD", ["2026-05"], tmp_path, pause=0.0)
    first = len(calls)
    spot.pull("XAUUSD", ["2026-05"], tmp_path, pause=0.0)
    assert len(calls) == first, "re-fetched days that were already cached"
