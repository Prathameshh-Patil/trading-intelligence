"""Route 2's bulk transport -- Dukascopy over S3 instead of over HTTP.

WHY THIS EXISTS AND `spot.pull()` DOES NOT SUFFICE. Measured 2026-09-17/18:
the HTTP datafeed serves ~2 requests from a three-day rest and then returns
**HTTP 429** -- an explicit rate limit, not the IP ban `SPOT_FEED_CHECK.md`
recorded from connection resets. The 429's own JSON body points at Dukascopy's
data-export documentation, which documents this requester-pays bucket. The
limit did not lift in 40 minutes of cooldown, so it is not a pacing problem.

    5 years over HTTP hour-files   ~43,800 requests   against a ~2/period budget
    5 years over S3                ~1,300 day objects  no documented limit

⚠️ **THE OBJECT NAME UNDER THE PREFIX IS UNVERIFIED.** No AWS credentials exist
on this machine and nobody has listed the bucket, so `day_prefix` is written
and tested and `fetch_day` is written and *not*. E0's first action is
`aws s3 ls s3://cfg-public-proper-wallaby/XAUUSD/2021/00/ --request-payer
requester --region eu-west-1`, and its whole point is to find out what the
objects are called. `OBJECT_SUFFIX` below is the documentation's claim, not a
measurement -- if E0 shows otherwise, fix it there and say so.

NOTHING ABOUT THE DECODER CHANGES. `dukascopy.decode_bi5` and
`dukascopy.POINTS` are imported, never reimplemented. Two decoders is how two
files quietly disagree about a price scale, and `spot.py`'s docstring records
what that already cost once.

WHY boto3 IS IMPORTED INSIDE THE FUNCTION. It is not a project dependency yet,
and adding it is a lockfile change that belongs to whoever decides S3 is the
route. Everything this module can be tested on -- prefix construction, the
symbol guard -- needs no network and no boto3, so the import sits at the one
call site that genuinely needs it and the tests run on a machine without it.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

import dukascopy as dk

BUCKET = "cfg-public-proper-wallaby"
REGION = "eu-west-1"

# Claimed by Dukascopy's data-export documentation, NOT measured. See the
# warning above -- E0 replaces this with what the bucket actually holds.
OBJECT_SUFFIX = "_ticks.bi5"


def day_prefix(symbol: str, day: date) -> str:
    """Dukascopy's layout for one instrument-day. **The month is zero-indexed.**

    June is `05`. An off-by-one returns a real file for the wrong month: it
    downloads, it decodes, and it looks entirely fine. `dukascopy.url_for`
    uses the same convention over HTTP and a test pins the two together.
    """
    return f"{symbol}/{day.year}/{day.month - 1:02d}/{day.day:02d}"


def fetch_day(symbol: str, day: date) -> pd.DataFrame:
    """One day of ticks from the requester-pays bucket.

    The symbol guard runs before anything else so that an unknown instrument
    refuses identically whether or not boto3 is installed -- `POINTS`' rule:
    a guessed point scale is a 10x price error that decodes cleanly.
    """
    if symbol not in dk.POINTS:
        raise ValueError(
            f"no point scale for {symbol}; add it to dukascopy.POINTS deliberately -- §4.6")

    # Not a project dependency until S3 is the chosen route, so mypy cannot
    # see it and the ignore is load-bearing rather than noise. **Delete it in
    # the same commit that adds boto3 to pyproject.toml** -- left in place it
    # would hide a real typing error against the installed package.
    import boto3  # type: ignore[import-not-found]

    obj = boto3.client("s3", region_name=REGION).get_object(
        Bucket=BUCKET,
        Key=f"{day_prefix(symbol, day)}{OBJECT_SUFFIX}",
        RequestPayer="requester",
    )
    return dk.decode_bi5(obj["Body"].read(), symbol, pd.Timestamp(day, tz="UTC"))
