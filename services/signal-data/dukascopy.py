"""Route 2's spot feed: Dukascopy historical ticks, fetched and decoded.

`docs/strategy/ARCHITECTURE.md` §4.1 — *"Dukascopy reachability is unverified
from this machine and step one of that route is a ten-minute check that a
download completes."* This module is that check, made reproducible. The result
is in `analysis/SPOT_FEED_CHECK.md`.

**It is not a bulk downloader and it does not commit the project to a vendor.**
Step 6 is unscheduled (`strategy-split.md` §9) and choosing a spot vendor is a
decision for the room. What this does is close the question the architecture
left open, so the decision is made against numbers.

THREE THINGS THAT COST TIME TO FIND, ALL RECORDED SO NOBODY PAYS AGAIN.

  * **A request without a browser `User-Agent` is reset, not refused.** No
    status code, no body -- `Recv failure: Connection reset by peer` after a
    ~25s hang, which reads exactly like an unreachable host. That is very
    likely what `DELTA_CVD_FINDINGS.md` §4 recorded as "unreachable". With a
    UA the same URL returns 200.
  * **A UA is necessary and NOT sufficient: without `Accept` the same URL is a
    503.** Found 2026-09-10, when every request this module made started
    failing while `curl` on the identical URL returned 200 and 85,669 bytes.
    `urllib` sends no `Accept` at all and `curl` defaults to `*/*`; adding it
    fixes it outright. **Two headers now, and the lesson is the one the bullet
    above already taught: this feed answers a non-browser request with a
    plausible transport failure rather than a refusal.** A 503 reads as "the
    vendor is down" and would have been believed -- the reachability check on
    7 Sep passed, so the natural reading a month later is an outage, not a
    client bug. Reproduce against `curl` before believing this feed is down.
  * **The month in the path is ZERO-INDEXED.** June 2025 is `/2025/05/`.
    An off-by-one here returns a real file for the wrong month, which is the
    worst kind of wrong: it decodes, it looks fine, and it is May.
  * **The feed is flaky under sequential load** -- one request in four was
    reset on a warm connection. Any bulk pull needs retries, and the failure
    is a reset rather than an HTTP error, so `raise_for_status` will not see
    it.

FORMAT. LZMA-compressed, 20-byte big-endian records, no header of its own:
`uint32` milliseconds from the hour, `uint32` ask, `uint32` bid, `float32` ask
volume, `float32` bid volume. Prices are integers in the instrument's own
points and **the scale is per-instrument** -- XAUUSD is 1e-3. Getting that
wrong is ARCHITECTURE §4.6's 10x error arriving through the vendor, so
`POINTS` is explicit and there is no default.

An hour with no ticks is a **zero-byte file, not a 404** -- weekends and the
daily break. Empty is a valid answer and means the market was shut.
"""

from __future__ import annotations

import lzma
import struct
import time
from urllib.request import Request, urlopen

import pandas as pd

FEED = "https://datafeed.dukascopy.com/datafeed"

# Both are required and neither is optional: no UA resets the connection, no
# `Accept` returns 503. See the docstring -- each was found the hard way.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "*/*"}

# Integer points per unit of price, per instrument. No default: a wrong scale
# here is a 10x price error that renders as a plausible chart (§4.6).
POINTS = {"XAUUSD": 1e-3}

RECORD = struct.Struct(">IIIff")  # ms, ask, bid, ask_vol, bid_vol


def url_for(symbol: str, hour: pd.Timestamp) -> str:
    """The feed's URL for one instrument-hour. **The month is zero-indexed.**

    January is `00`. An off-by-one returns a real file for the wrong month,
    which decodes cleanly and is silently a month early.
    """
    return (
        f"{FEED}/{symbol}/{hour.year}/{hour.month - 1:02d}/{hour.day:02d}"
        f"/{hour.hour:02d}h_ticks.bi5"
    )


def decode_bi5(raw: bytes, symbol: str, hour: pd.Timestamp) -> pd.DataFrame:
    """One hour of `.bi5` bytes -> a quote frame, timestamps in UTC.

    Returns the columns `features/portable.py` needs for `mid`, `spread_bp`
    and `quote_rate_z`, and nothing else.

    **A zero-byte body is an hour the market was shut**, and it returns an
    empty frame rather than raising: on a 24x5 instrument the weekend gap is
    the normal case, and treating it as an error would make the caller's
    retry loop chase a hole that is supposed to be there.
    """
    if symbol not in POINTS:
        raise ValueError(f"no point scale for {symbol}; add it to POINTS deliberately -- §4.6")
    cols = ["timestamp", "bid", "ask", "bid_vol", "ask_vol"]
    if not raw:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in cols}).astype(
            {"timestamp": "datetime64[ns, UTC]"}
        )

    body = lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(raw)
    if len(body) % RECORD.size:
        raise ValueError(
            f"{len(body)} bytes is not a whole number of {RECORD.size}-byte ticks; "
            "the payload is truncated or the record layout has changed"
        )
    rows = [RECORD.unpack_from(body, i) for i in range(0, len(body), RECORD.size)]
    df = pd.DataFrame(rows, columns=["ms", "ask", "bid", "ask_vol", "bid_vol"])

    point = POINTS[symbol]
    return pd.DataFrame(
        {
            "timestamp": hour + pd.to_timedelta(df["ms"], unit="ms"),
            "bid": df["bid"] * point,
            "ask": df["ask"] * point,
            "bid_vol": df["bid_vol"],
            "ask_vol": df["ask_vol"],
        }
    )


def fetch_hour(
    symbol: str, hour: pd.Timestamp, *, retries: int = 3, timeout: int = 60
) -> pd.DataFrame:
    """Download and decode one hour. Retries, because resets are routine.

    **The failure mode is a connection reset, not an HTTP status**, so this
    retries on any exception rather than on a status code. One request in four
    was reset during the reachability check on a warm connection.
    """
    if hour.tzinfo is None:
        raise ValueError("hour must be tz-aware; the feed is UTC and a naive hour is a guess")
    hour = hour.tz_convert("UTC").floor("h")

    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url_for(symbol, hour), headers=HEADERS)
            with urlopen(req, timeout=timeout) as r:
                return decode_bi5(r.read(), symbol, hour)
        # Named rather than blanket, and each one is a failure seen in the
        # reachability check: OSError covers the connection reset and the
        # timeout (URLError subclasses it), LZMAError a corrupt payload, and
        # ValueError decode_bi5's own truncation guard. A bad point scale is
        # also a ValueError and must NOT be retried -- but it raises before the
        # first request, so it never reaches here.
        except (OSError, lzma.LZMAError, ValueError) as exc:
            last = exc
            time.sleep(2**attempt)
    raise ConnectionError(f"{url_for(symbol, hour)} failed after {retries} attempts: {last}")
