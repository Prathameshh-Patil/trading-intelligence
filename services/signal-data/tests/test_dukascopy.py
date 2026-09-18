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
from datetime import date

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


def test_the_request_carries_both_headers_the_feed_requires(monkeypatch) -> None:
    """A UA is necessary and not sufficient -- without `Accept` the feed 503s.

    Found 2026-09-10: every request this module made started failing while
    `curl` on the identical URL returned 200. The 503 reads as a vendor outage
    and would have been believed, because the reachability check had passed a
    month earlier. Pinned here so a header cannot be dropped as decoration.
    """
    sent = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return bi5([])

    def fake_urlopen(req, timeout=0):
        sent.update(req.headers)
        return FakeResponse()

    monkeypatch.setattr(dk, "urlopen", fake_urlopen)
    dk.fetch_hour("XAUUSD", pd.Timestamp("2025-06-18T14:00:00Z"))

    # urllib title-cases header names on the way in.
    assert sent.get("User-agent", "").startswith("Mozilla/"), "no UA -> connection reset"
    assert sent.get("Accept") == "*/*", "no Accept -> 503"


# `fetch_day` -- ONE request for a whole day. The 429 that sent E0 to S3 had
# lifted by 2026-09-19, and the day object the S3 bucket holds turned out to be
# served over HTTP too. No network here: what these pin is the day-completeness
# invariant `spot.pull` depends on, and the two answers a request can give.


def test_a_day_is_one_request_for_the_day_object(monkeypatch) -> None:
    """Twenty-four hour files would be twenty-four requests and ~43,800 for
    five years. The day object is 1,776. The count is the whole reason this
    function exists, so it is asserted rather than described."""
    asked = []

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return bi5([(0, 3_400_000, 3_399_000, 1.0, 1.0)])

    def fake_urlopen(req, timeout=0):
        asked.append(req.full_url)
        return FakeResponse()

    monkeypatch.setattr(dk, "urlopen", fake_urlopen)
    day = dk.fetch_day("XAUUSD", date(2025, 6, 18))

    assert len(asked) == 1, f"one day should be one request, not {len(asked)}"
    assert asked[0].endswith("/2025/05/18_ticks.bi5"), asked[0]
    assert len(day) == 1


def test_the_day_object_is_a_sibling_of_the_hour_directory_not_a_file_in_it() -> None:
    """`.../05/18_ticks.bi5` beside `.../05/18/13h_ticks.bi5`. A day URL built
    inside the directory returns 404 and would read as a missing day."""
    day = pd.Timestamp("2025-06-18", tz="UTC")
    assert dk.day_url("XAUUSD", day).endswith("/2025/05/18_ticks.bi5")
    assert dk.url_for("XAUUSD", day + pd.Timedelta(hours=13)).endswith("/2025/05/18/13h_ticks.bi5")


def test_a_shut_day_is_two_hundred_and_empty_not_an_error(monkeypatch) -> None:
    """Measured on Saturday 2026-08-01: HTTP 200, zero bytes. `spot.pull`
    writes it as an empty parquet so a later pass does not re-request it
    forever -- which it cannot do with a raise. **This is also what makes the
    503 unambiguous**: absence has its own answer, so a 503 is the throttle."""
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b""

    monkeypatch.setattr(dk, "urlopen", lambda req, timeout=0: FakeResponse())
    day = dk.fetch_day("XAUUSD", date(2026, 8, 1))

    assert day.empty
    assert list(day.columns) == ["timestamp", "bid", "ask", "bid_vol", "ask_vol"]


def test_a_failed_day_raises_rather_than_returning_a_partial_one(monkeypatch) -> None:
    """The invariant: a day with a hole looks exactly like a quiet day once it
    is on disk, so the day is not written at all and the next resumable pass
    picks it up."""
    def dead(req, timeout=0):
        raise OSError("503")

    monkeypatch.setattr(dk, "urlopen", dead)
    monkeypatch.setattr(dk.time, "sleep", lambda _: None)
    with pytest.raises(ConnectionError):
        dk.fetch_day("XAUUSD", date(2025, 6, 18), retries=2)


def test_an_unknown_instrument_raises_before_any_request_is_made(monkeypatch) -> None:
    """`decode_bi5` also guards, but from inside `_fetch`'s try, where
    `except ValueError` retried it and re-raised it as a ConnectionError -- an
    unknown symbol reading as a dead feed. Both fetchers guard up front."""
    def forbidden(req, timeout=0):
        raise AssertionError("a request was made for an instrument with no point scale")

    monkeypatch.setattr(dk, "urlopen", forbidden)
    for call in (lambda: dk.fetch_hour("EURUSD", HOUR),
                 lambda: dk.fetch_day("EURUSD", date(2025, 6, 18))):
        with pytest.raises(ValueError, match="no point scale"):
            call()
