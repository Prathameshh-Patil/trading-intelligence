"""The S3 transport, tested on the parts that do not need the network.

WHAT IS PINNED HERE. The zero-indexed month -- the same layout `dukascopy.url_for`
uses over HTTP and `test_dukascopy.py` already pins. And, since E0 listed the
bucket on 2026-09-18: the tick object's position beside the day prefix, the
midnight anchor a day object needs, and the missing-day-is-empty rule. The
network half is verified in `analysis/E0_TRANSPORT.md` against a known hour,
not here.

The month is the trap worth a test on its own: an off-by-one returns a real
file for the wrong month. It downloads, it decodes, and it looks entirely fine.
"""

from __future__ import annotations

from datetime import date

import pytest

import spot_s3


def test_the_month_in_the_prefix_is_zero_indexed():
    # June 2025 lives under /05/. Same convention as dukascopy.url_for.
    assert spot_s3.day_prefix("XAUUSD", date(2025, 6, 18)) == "XAUUSD/2025/05/18"


def test_january_is_month_zero_not_twelve():
    assert spot_s3.day_prefix("XAUUSD", date(2025, 1, 2)) == "XAUUSD/2025/00/02"


def test_december_is_month_eleven():
    assert spot_s3.day_prefix("XAUUSD", date(2025, 12, 31)) == "XAUUSD/2025/11/31"


def test_the_prefix_agrees_with_the_http_url_dukascopy_py_already_uses():
    # Two layouts for one vendor is how two files quietly disagree. If
    # url_for ever changes, this test fails rather than the pull going quiet.
    import pandas as pd

    import dukascopy as dk

    http = dk.url_for("XAUUSD", pd.Timestamp("2025-06-18T14:00:00Z"))
    assert spot_s3.day_prefix("XAUUSD", date(2025, 6, 18)) in http


def test_an_unknown_symbol_refuses_rather_than_guessing_a_scale():
    # dukascopy.POINTS' rule, and §4.6's: a guessed point scale is a 10x
    # price error that decodes cleanly and looks plausible.
    with pytest.raises(ValueError, match="EURJPY"):
        spot_s3.fetch_day("EURJPY", date(2025, 6, 18))


def test_the_symbol_check_happens_before_any_network_call():
    # The refusal above must not depend on boto3 being installed, or the
    # guard silently becomes an ImportError on a machine without it.
    with pytest.raises(ValueError):
        spot_s3.fetch_day("NOTASYMBOL", date(2025, 6, 18))


# -- E0 confirmed the layout on 2026-09-18; these pin what it found. ---------


def test_the_tick_object_sits_beside_the_day_prefix_not_inside_it():
    # XAUUSD/2025/05/18/ is a prefix of candles; the day's ticks are
    # XAUUSD/2025/05/18_ticks.bi5 at the month level. A slash before _ticks
    # returns NoSuchKey for every day and reads as a coverage problem.
    assert spot_s3.tick_key("XAUUSD", date(2025, 6, 18)) == "XAUUSD/2025/05/18_ticks.bi5"


def test_a_day_object_is_decoded_from_midnight_not_from_an_hour():
    # A day object's offsets run from 00:00 UTC. Any other anchor shifts every
    # quote by that much and the frame still parses.
    import lzma
    import struct

    import pandas as pd

    body = struct.pack(">IIIff", 14 * 3_600_000 + 500, 3_380_000, 3_379_500, 1.0, 1.0)
    raw = lzma.compress(body, format=lzma.FORMAT_ALONE)
    got = spot_s3.decode_day(raw, "XAUUSD", date(2025, 6, 18))
    assert got["timestamp"].iloc[0] == pd.Timestamp("2025-06-18T14:00:00.500Z")
    assert got["ask"].iloc[0] == pytest.approx(3380.0)
    assert got["bid"].iloc[0] == pytest.approx(3379.5)


def test_a_missing_day_is_an_empty_frame_not_an_exception():
    # Saturdays have no object. The caller iterating a date range must see
    # "no quotes", not a retry loop chasing a hole that is supposed to be there.
    class _NoSuchKey(Exception):
        pass

    class FakeClient:
        class exceptions:  # mirrors botocore's shape
            NoSuchKey = _NoSuchKey

        def get_object(self, **_: object) -> dict[str, object]:
            raise _NoSuchKey()

    got = spot_s3.fetch_day("XAUUSD", date(2025, 6, 14), s3=FakeClient())  # type: ignore[arg-type]
    assert got.empty
    assert list(got.columns) == ["timestamp", "bid", "ask", "bid_vol", "ask_vol"]
