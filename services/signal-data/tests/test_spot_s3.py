"""The S3 transport, tested on the parts that do not need the network.

WHAT IS AND IS NOT PINNED HERE. The zero-indexed month is certain -- it is the
same layout `dukascopy.url_for` already uses over HTTP and
`test_dukascopy.py` already pins -- so it is tested. **The object suffix under
that prefix is NOT verified**, because no AWS credentials exist on this machine
and nobody has listed the bucket. `day_prefix` is therefore the tested surface
and `fetch_day` is not; E0's first action is an `aws s3 ls` against the prefix
these tests pin, precisely to find out what the objects are called.

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
