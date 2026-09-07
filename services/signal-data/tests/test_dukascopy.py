"""Route 2's spot feed decoder. `analysis/SPOT_FEED_CHECK.md`.

**No test here touches the network.** The reachability result is a recorded
measurement, not a thing to re-assert on every run — a suite that fails when a
vendor is briefly down is a suite people learn to ignore. What is tested is the
decoding, where the errors are silent: a wrong point scale renders a plausible
chart at ten times the price, and a zero-indexed month returns a real file for
the wrong month.
"""

from __future__ import annotations

import lzma

import pandas as pd
import pytest

import dukascopy as dk

HOUR = pd.Timestamp("2025-06-18T14:00:00Z")


def bi5(ticks: list[tuple[int, int, int, float, float]]) -> bytes:
    """Build a .bi5 body: LZMA-alone over 20-byte big-endian records."""
    body = b"".join(dk.RECORD.pack(*t) for t in ticks)
    c = lzma.LZMACompressor(lzma.FORMAT_ALONE)
    return c.compress(body) + c.flush()


def test_a_tick_round_trips_with_its_price_scale_applied() -> None:
    got = dk.decode_bi5(bi5([(26, 3392575, 3391998, 1.5, 2.25)]), "XAUUSD", HOUR)
    assert len(got) == 1
    r = got.iloc[0]
    assert r["timestamp"] == HOUR + pd.Timedelta(milliseconds=26)
    assert r["ask"] == pytest.approx(3392.575)
    assert r["bid"] == pytest.approx(3391.998)
    assert r["ask_vol"] == pytest.approx(1.5)


def test_an_unknown_instrument_raises_rather_than_guessing_a_scale() -> None:
    # §4.6's error arriving through the vendor. A guessed point scale renders a
    # perfectly plausible chart at ten times or a tenth of the real price.
    with pytest.raises(ValueError, match="no point scale"):
        dk.decode_bi5(bi5([(0, 1, 1, 0.0, 0.0)]), "EURUSD", HOUR)


def test_an_empty_hour_is_a_shut_market_not_an_error() -> None:
    # Weekends and the daily break arrive as a zero-byte body, not a 404. On a
    # 24x5 instrument that is the normal case, and raising would make a caller's
    # retry loop chase a hole that is meant to be there.
    got = dk.decode_bi5(b"", "XAUUSD", HOUR)
    assert got.empty
    assert list(got.columns) == ["timestamp", "bid", "ask", "bid_vol", "ask_vol"]
    assert str(got["timestamp"].dtype) == "datetime64[ns, UTC]"


def test_a_truncated_payload_raises_instead_of_dropping_the_tail() -> None:
    body = b"".join(dk.RECORD.pack(0, 1, 1, 0.0, 0.0) for _ in range(3))[:-4]
    c = lzma.LZMACompressor(lzma.FORMAT_ALONE)
    with pytest.raises(ValueError, match="whole number"):
        dk.decode_bi5(c.compress(body) + c.flush(), "XAUUSD", HOUR)


def test_the_month_in_the_url_is_zero_indexed() -> None:
    # The trap: an off-by-one returns a REAL file for the wrong month. It
    # decodes, it looks fine, and it is May.
    assert dk.url_for("XAUUSD", HOUR).endswith("/XAUUSD/2025/05/18/14h_ticks.bi5")
    assert "/2025/00/" in dk.url_for("XAUUSD", pd.Timestamp("2025-01-02T03:00:00Z"))


def test_a_naive_hour_is_refused() -> None:
    with pytest.raises(ValueError, match="tz-aware"):
        dk.fetch_hour("XAUUSD", pd.Timestamp("2025-06-18T14:00:00"))


def test_ticks_stay_in_order_and_inside_their_hour() -> None:
    got = dk.decode_bi5(
        bi5([(26, 3392575, 3391998, 1.0, 1.0), (3599647, 3392000, 3391500, 1.0, 1.0)]),
        "XAUUSD", HOUR,
    )
    assert got["timestamp"].is_monotonic_increasing
    assert got["timestamp"].min() >= HOUR
    assert got["timestamp"].max() < HOUR + pd.Timedelta(hours=1)
