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
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import spot
import spot_s3
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


# --------------------------------------------------------------------------
# pull(), against the S3 day transport. Task 5.
#
# FIVE TESTS WERE DELETED HERE, NOT BROKEN. They guarded the hour cache, the
# per-hour resume and the partial-day rule -- machinery that existed because
# the HTTP datafeed served fewer than 24 requests a day. E0 replaced it with
# one object per day, so a day now arrives whole or not at all and there is no
# longer a code path that can write a day with holes. The invariant survives;
# what is gone is the code that had to enforce it. Git remembers the old path.


def fake_day(n: int = 3) -> pd.DataFrame:
    ts = pd.date_range("2025-06-02T00:00:00Z", periods=n, freq="1h")
    return pd.DataFrame({"timestamp": ts, "bid": 3000.0, "ask": 3000.5})


def test_a_day_is_one_request_and_is_written_whole(tmp_path: Path) -> None:
    calls = []

    def fetch(sym: str, day: date) -> pd.DataFrame:
        calls.append(day)
        return fake_day()

    spot.pull("XAUUSD", ["2025-06"], tmp_path, fetch=fetch)
    assert len(calls) == 30, "one request per calendar day, not 24"
    assert len(list(tmp_path.glob("*.parquet"))) == 30


def test_a_shut_day_is_written_empty_rather_than_skipped(tmp_path: Path) -> None:
    # Every Saturday. Skipping it means the next pass re-requests it forever,
    # and a billed request repeated forever is worse than an empty file.
    def fetch(sym: str, day: date) -> pd.DataFrame:
        return fake_day() if day.weekday() != 5 else fake_day(0)

    spot.pull("XAUUSD", ["2025-06"], tmp_path, fetch=fetch)
    sat = tmp_path / "2025-06-07.parquet"
    assert sat.exists() and len(pd.read_parquet(sat)) == 0


def test_a_day_already_on_disk_is_not_fetched_again(tmp_path: Path) -> None:
    # Resumability survives the simplification, and it is what makes a 1,776
    # day pull restartable. Each fetch is billed, so this is money as well as
    # time.
    calls = []

    def fetch(sym: str, day: date) -> pd.DataFrame:
        calls.append(day)
        return fake_day()

    spot.pull("XAUUSD", ["2025-06"], tmp_path, fetch=fetch)
    first = len(calls)
    spot.pull("XAUUSD", ["2025-06"], tmp_path, fetch=fetch)
    assert len(calls) == first, "a second pass must cost nothing"


def test_there_is_no_hour_cache_left_behind(tmp_path: Path) -> None:
    spot.pull("XAUUSD", ["2025-06"], tmp_path, fetch=lambda s, d: fake_day())
    assert not (tmp_path / ".hours").exists()


def test_the_default_transport_is_s3_not_the_http_datafeed(tmp_path: Path) -> None:
    # The swap itself, pinned. The HTTP path is rate-limited to ~2 requests
    # per multi-day period and cannot serve this pull at any pace.
    import inspect

    assert inspect.signature(spot.pull).parameters["fetch"].default is spot_s3.fetch_day
