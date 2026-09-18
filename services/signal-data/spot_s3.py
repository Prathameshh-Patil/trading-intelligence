"""Route 2's bulk transport -- Dukascopy over S3 instead of over HTTP.

WHY THIS EXISTS AND `spot.pull()` DOES NOT SUFFICE. Measured 2026-09-17/18:
the HTTP datafeed serves ~2 requests from a three-day rest and then returns
**HTTP 429** -- an explicit rate limit, not the IP ban `SPOT_FEED_CHECK.md`
recorded from connection resets. The 429's own JSON body points at Dukascopy's
data-export documentation, which documents this requester-pays bucket. The
limit did not lift in 40 minutes of cooldown, so it is not a pacing problem.

    5 years over HTTP hour-files   ~43,800 requests   against a ~2/period budget
    5 years over S3                 1,776 day objects  1.34 GB, ~$0.12   (measured, E0)

THE LAYOUT, MEASURED 2026-09-18 (`analysis/E0_TRANSPORT.md`). The first
version of this file said the object name was unverified and that E0's first
action was to list the bucket. It was, and this is what it holds:

    XAUUSD/2025/05/18/BID_candles_min_1.bi5     the day is a PREFIX of 1-minute candles
    XAUUSD/2025/05/18/ASK_candles_min_1.bi5
    XAUUSD/2025/05/18_ticks.bi5                 the day's ticks: a SIBLING object at month level
    XAUUSD/2025/05/BID_candles_hour_1.bi5       one month of hourly candles
    XAUUSD/metadata/HistoryStart.bi5

So `day_prefix` + `_ticks.bi5` was the right key all along, and the day's
offsets run from 00:00 UTC -- the full day decodes to 228,269 quotes spanning
00:00:00.100 .. 23:59:59.561, and the 14:00 hour inside it reproduces
`SPOT_FEED_CHECK.md` §1's validated sample exactly (20,654 quotes, 1.91 bp).
The month is zero-indexed (June is 05). Saturdays have no object; Sundays do.
XAUUSD/ goes back to 1997-07 and updates daily.

NOTHING ABOUT THE DECODER CHANGES. `dukascopy.decode_bi5` and
`dukascopy.POINTS` are imported, never reimplemented. Two decoders is how two
files quietly disagree about a price scale, and `spot.py`'s docstring records
what that already cost once. The one difference from the HTTP path is the
anchor passed in: midnight for a day object, not the top of an hour.

CREDENTIALS. Requester-pays means every call is authenticated and billed to
the caller. boto3's default chain reads `~/.aws/credentials` -- a scoped IAM
user, never root -- and nothing here holds, logs or prints a secret.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import boto3
import pandas as pd

import dukascopy as dk

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

BUCKET = "cfg-public-proper-wallaby"
REGION = "eu-west-1"

# Measured, not claimed -- see the module docstring and E0_TRANSPORT.md §1.
OBJECT_SUFFIX = "_ticks.bi5"


def day_prefix(symbol: str, day: date) -> str:
    """Dukascopy's layout for one instrument-day. **The month is zero-indexed.**

    June is `05`. An off-by-one returns a real file for the wrong month: it
    downloads, it decodes, and it looks entirely fine. `dukascopy.url_for`
    uses the same convention over HTTP and a test pins the two together.
    """
    return f"{symbol}/{day.year}/{day.month - 1:02d}/{day.day:02d}"


def tick_key(symbol: str, day: date) -> str:
    """The day's tick object -- beside the day prefix, not inside it."""
    return f"{day_prefix(symbol, day)}{OBJECT_SUFFIX}"


def decode_day(raw: bytes, symbol: str, day: date) -> pd.DataFrame:
    """A day object's offsets run from midnight, so midnight is the anchor."""
    return dk.decode_bi5(raw, symbol, pd.Timestamp(day, tz="UTC"))


def client() -> S3Client:
    return boto3.client("s3", region_name=REGION)


def fetch_day(symbol: str, day: date, *, s3: S3Client | None = None) -> pd.DataFrame:
    """One day of ticks from the requester-pays bucket.

    The symbol guard runs before anything else so that an unknown instrument
    refuses before a single billed request -- `POINTS`' rule: a guessed point
    scale is a 10x price error that decodes cleanly.

    A day with no object -- every Saturday, and any holiday the venue closed --
    returns an empty frame with S1's columns, the same way `decode_bi5` treats
    a zero-byte hour. On a 24x5 instrument the gap is the normal case, and a
    caller iterating a date range must not have a retry loop chase it.
    """
    if symbol not in dk.POINTS:
        raise ValueError(
            f"no point scale for {symbol}; add it to dukascopy.POINTS deliberately -- §4.6")

    s3 = s3 if s3 is not None else client()
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=tick_key(symbol, day), RequestPayer="requester")
    except s3.exceptions.NoSuchKey:
        return decode_day(b"", symbol, day)
    ticks = decode_day(obj["Body"].read(), symbol, day)

    # THE ANCHOR CHECK, KEPT AFTER E0 CONFIRMED THE LAYOUT. `.bi5` records
    # carry milliseconds from their anchor, and a well-formed frame with every
    # tick inside hour 0 is the worst outcome available here -- it would mean
    # the bucket had quietly switched to hourly objects. E0 measured a full
    # day; this asserts each pull still is one. Found by review 2026-09-18.
    if len(ticks) and ticks["timestamp"].max() - ticks["timestamp"].min() < pd.Timedelta(hours=2):
        raise ValueError(
            f"{symbol} {day}: {len(ticks)} ticks span under two hours "
            f"({ticks['timestamp'].min()} .. {ticks['timestamp'].max()}). "
            "The object is probably hourly, not daily -- fix OBJECT_SUFFIX and "
            "the decoder anchor together, and record what the bucket actually holds.")
    return ticks
