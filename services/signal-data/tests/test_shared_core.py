"""S9's shared core, enforced rather than promised.

`plans/team/strategy-split.md` §9, as amended 2026-09-10 and signed by Varad on
2026-09-11, replaces *"both loaders produce the same frame"* -- which was
measurably violated and could never have held -- with three rules:

  1. the shared core is `open, high, low, close, session` on a UTC index, and
     both loaders produce it;
  2. each loader may add instrument-specific columns, which are not gaps in the
     other frame but quantities the other instrument does not have;
  3. **no portable feature may read outside the shared core** unless
     `Instrument.has_flow` gates it.

**Rule 3 was true when it was written and nothing made it stay true.** That is
the `reach_table.json` situation exactly -- 41,280 numbers correct on the day
with nothing reconciling them, which then needed a test before anyone could
rely on it. A rule that becomes a frozen contract and is guarded only by
everyone remembering is the weaker half of its own argument, so it is guarded
here instead.

The enforcement is the only one that cannot rot: every portable feature is
handed a frame carrying **nothing but the core** and must still run. A feature
that starts reading `volume` fails this the day it is written, not the day
someone runs it on spot.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

import spot
from features import portable
from instruments import GC, XAUUSD
from m2_magnitude import vol_state

# §9 rule 1, transcribed. Not derived from either loader -- a test that reads
# the core off the code it is checking cannot fail.
SHARED_CORE = {"open", "high", "low", "close", "session"}

# §9 rule 2. Named so that a new column is a deliberate change to this list
# rather than something a loader grew quietly.
GC_ONLY = {"volume", "delta", "trades", "cvd"}
SPOT_ONLY = {"ticks", "spread_bp"}


def core_only(n: int = 240) -> pd.DataFrame:
    """A bars frame carrying the shared core and not one column more."""
    idx = pd.date_range("2026-06-18T00:00:00Z", periods=n, freq="5min")
    walk = 3300 + np.cumsum(np.sin(np.arange(n) / 7) * 0.4)
    frame = pd.DataFrame(
        {"open": walk, "high": walk + 0.6, "low": walk - 0.6, "close": walk,
         "session": [date(2026, 6, 18)] * n},
        index=idx,
    )
    assert set(frame.columns) == SHARED_CORE, "the fixture must BE the core"
    return frame


def quotes(n: int = 5_000) -> pd.DataFrame:
    t0 = pd.Timestamp("2026-06-18T00:00:00Z")
    bid = 3300 + np.cumsum(np.sin(np.arange(n) / 50) * 0.01)
    return pd.DataFrame({
        "timestamp": t0 + pd.to_timedelta(np.arange(n) * 200, unit="ms"),
        "bid": bid, "ask": bid + 0.30,
    })


# --- rule 3, the one with no other guard -----------------------------------

@pytest.mark.parametrize(
    ("name", "call"),
    [
        ("atr_bp", lambda b: portable.atr_bp(b, GC, window="60min", min_bars=3)),
        ("range_bp", lambda b: portable.range_bp(b)),
        ("rv_parkinson", lambda b: portable.rv_parkinson(b, window="60min", min_bars=3)),
        ("rv_slope", lambda b: portable.rv_slope(b, window="60min", min_bars=3)),
        ("efficiency_ratio", lambda b: portable.efficiency_ratio(b, window="60min", min_bars=3)),
        ("session_phase", lambda b: portable.session_phase(b, GC)),
        ("anchors", lambda b: portable.anchors(b, GC)),
        ("vol_state", lambda b: vol_state(b)),
    ],
)
def test_portable_features_read_only_the_shared_core(name, call):
    """Handed the core and nothing else, every one of them still answers.

    This is what makes rule 3 checkable. A feature that reaches for `volume`,
    `delta` or `spread_bp` raises `KeyError` here -- on the day it is written,
    rather than the first time someone runs the pipeline on the instrument that
    does not have the column.
    """
    got = call(core_only())
    assert len(got) == len(core_only())


def test_the_fixture_would_catch_a_feature_that_strayed():
    """The test above is only worth having if the frame really is bare."""
    with pytest.raises(KeyError):
        core_only()["volume"]


# --- rules 1 and 2, both loaders -------------------------------------------

def test_spot_produces_the_core_and_its_own_columns():
    bars = spot.minute_bars(quotes(), XAUUSD)
    assert SHARED_CORE <= set(bars.columns)
    assert set(bars.columns) - SHARED_CORE == SPOT_ONLY
    assert bars.index.tz is not None, "§9 rule 1: a UTC index"


def test_spot_survives_resampling_with_the_core_intact():
    bars = spot.resample(spot.minute_bars(quotes(), XAUUSD), "5min", XAUUSD)
    assert set(bars.columns) - SHARED_CORE == SPOT_ONLY


def test_the_two_loaders_do_not_have_the_same_columns_and_that_is_the_amendment():
    """S9 as originally written said they must. They cannot, and the direction
    matters: it is GC that carries the extra columns, because it has a tape and
    spot does not. Satisfying the original would mean inventing a `volume` for
    spot, which is the exact thing `has_flow` exists to prevent."""
    assert GC_ONLY & SPOT_ONLY == set()
    assert GC.has_flow and not XAUUSD.has_flow


# --- the duplication issue #6 asked to be closed ---------------------------

def test_spot_uses_portables_mid_and_spread_rather_than_its_own():
    """`spot.minute_bars` computed both inline while step 6's signatures were
    empty. One quantity, two definitions, is how two files quietly disagree."""
    q = quotes()
    bars = spot.minute_bars(q, XAUUSD)
    expected = portable.mid(q).iloc[0]
    assert bars["open"].iloc[0] == expected


def test_mid_is_the_midpoint():
    q = pd.DataFrame({"bid": [100.0, 200.0], "ask": [101.0, 210.0]})
    assert portable.mid(q).tolist() == [100.5, 205.0]


def test_spread_bp_is_denominated_in_the_mid():
    q = pd.DataFrame({"bid": [100.0], "ask": [101.0]})
    # 1.00 wide on a 100.50 mid -> 99.5024... bp
    assert portable.spread_bp(q).iloc[0] == pytest.approx(1.0 / 100.5 * 1e4)


def test_spread_bp_uses_mid_rather_than_a_second_copy(monkeypatch):
    """If it recomputed the midpoint it would not notice this."""
    monkeypatch.setattr(portable, "mid", lambda q: pd.Series([1000.0] * len(q)))
    q = pd.DataFrame({"bid": [100.0], "ask": [101.0]})
    assert portable.spread_bp(q).iloc[0] == pytest.approx(1.0 / 1000.0 * 1e4)


def test_a_locked_market_is_zero_not_an_error():
    """bid == ask happens on a thin spot feed and is a real quote, not a fault."""
    q = pd.DataFrame({"bid": [3300.0], "ask": [3300.0]})
    assert portable.spread_bp(q).iloc[0] == 0.0
