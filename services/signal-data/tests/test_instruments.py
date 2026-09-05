"""The portability seam: the tick is injected, and flow is refused where absent.

`plans/team/strategy-split.md` §3. Everything in the strategy track waits on
this file's subject, so what is tested here is the seam's two promises rather
than any arithmetic: **a tick-denominated number cannot be produced without
naming the instrument**, and **a flow feature cannot be produced on an
instrument that has none.**
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import bars_at, ticks_at

import backtest as bt
import strategies as st
from features import expansion as ex
from features import orderflow as of
from features import portable as pt
from instruments import GC, Instrument, require_flow

# A spot instrument shaped the way the risk actually arrives: a DIFFERENT tick
# and no flow. Route 2 has not picked a vendor, so this is a fixture and not
# instruments.XAUUSD -- writing a real one would put a guessed tick in the seam.
SPOT = Instrument(
    name="XAUUSD-fixture",
    tick=0.01,
    tick_value=None,
    session_shift=pd.Timedelta(0),
    anchors=("prior_close",),
    has_flow=False,
)


def test_the_tick_is_no_longer_importable_from_s1() -> None:
    # The whole point of the seam. An import cannot be wrong out loud, so as
    # long as this name exists somebody will reach for it and silently measure
    # a second instrument in GC's ticks.
    import s1

    assert not hasattr(s1, "TICK")
    assert not hasattr(s1, "TICK_VALUE")


def test_no_tick_denominated_function_can_be_called_without_an_instrument() -> None:
    bars = bars_at([0, 1], [100.0, 100.0], ranges=[2.0, 2.0])
    for call in (
        lambda: ex.atr(bars, window="5min", min_bars=1),  # type: ignore[call-arg]
        lambda: ex.bar_range(bars),  # type: ignore[call-arg]
        lambda: ex.body_ratio(bars),  # type: ignore[call-arg]
        lambda: st.absorption(bars),  # type: ignore[call-arg]
        lambda: of.vwap_distance(bars),  # type: ignore[call-arg]
    ):
        with pytest.raises(TypeError):
            call()


# --------------------------------------------------------------------------
# has_flow is a hard boundary. ARCHITECTURE §10.3
# --------------------------------------------------------------------------
def test_flow_features_refuse_an_instrument_that_has_no_flow() -> None:
    # The frame deliberately CARRIES delta and volume. An MT5 spot feed ships a
    # `volume` column holding a tick count, so the missing-column KeyError that
    # would otherwise catch this is luck, not a rule -- and a proxy volume
    # produces a number that looks exactly like the real one.
    bars = bars_at([0, 1], [100.0, 100.5], deltas=[400, -200], ranges=[2.0, 2.0])
    ticks = ticks_at([(0, 100.0, 400, "B"), (0, 99.9, 10, "A")])

    with pytest.raises(ValueError, match="no order flow"):
        st.absorption(bars, SPOT)
    with pytest.raises(ValueError, match="no order flow"):
        st.bar_imbalance(ticks, SPOT, ratio=3.0)
    with pytest.raises(ValueError, match="no order flow"):
        of.vwap_distance(bars, SPOT)


def test_the_same_features_are_fine_on_gc() -> None:
    bars = bars_at([0], [100.0], deltas=[400], ranges=[2.0])
    require_flow(GC)
    assert st.absorption(bars, GC).iloc[0] == 20.0


# --------------------------------------------------------------------------
# Basis points -- ARCHITECTURE §4.6, the input-side twin of the display trap
# --------------------------------------------------------------------------
def test_atr_in_bp_is_the_same_number_whatever_the_tick_is() -> None:
    # This is the entire reason the track buckets in bp. In TICKS these two
    # answers differ by 10x for identical price action; in bp they agree, which
    # is what makes a bucket edge mean one thing on both instruments.
    bars = bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6)
    gc = pt.atr_bp(bars, GC, window="5min", min_bars=3)
    spot = pt.atr_bp(bars, SPOT, window="5min", min_bars=3)

    assert gc.dropna().eq(200.0).all(), "a 2.00 range on a 100.00 close is 200 bp"
    pd.testing.assert_series_equal(gc, spot)
    assert not ex.atr(bars, GC, window="5min", min_bars=3).equals(
        ex.atr(bars, SPOT, window="5min", min_bars=3)
    ), "the tick versions must still disagree, or the fixture is not testing anything"


def test_atr_bp_scales_with_the_price_level_not_with_the_range_alone() -> None:
    # 19 months of gold spans a large level change. A bp figure that ignored
    # the level would pool two populations and report the average as a base
    # rate -- the error §4.6 exists to prevent, and it is invisible downstream.
    low = bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6)
    high = bars_at(list(range(6)), [200.0] * 6, ranges=[2.0] * 6)
    assert pt.atr_bp(low, GC, window="5min", min_bars=3).dropna().iloc[0] == 200.0
    assert pt.atr_bp(high, GC, window="5min", min_bars=3).dropna().iloc[0] == 100.0


def test_atr_bp_wraps_the_one_atr_and_does_not_re_derive_it() -> None:
    # regime_filter.py's rule, which carries double force with two people
    # writing trailing windows: one true-range calculation, not two that drift.
    bars = bars_at(list(range(6)), [100.0] * 6, ranges=[2.0] * 6)
    ticks = ex.atr(bars, GC, window="5min", min_bars=3)
    pd.testing.assert_series_equal(
        pt.atr_bp(bars, GC, window="5min", min_bars=3),
        1e4 * ticks * GC.tick / bars["close"],
    )


# --------------------------------------------------------------------------
# Where an instrument has no answer, the answer is absent
# --------------------------------------------------------------------------
def test_expectancy_in_usd_is_absent_where_there_is_no_contract() -> None:
    # USD per tick per contract is a futures fact. Reporting the tick figure
    # under a dollar label would be a unit error wearing a measurement's name.
    bars = bars_at(list(range(40)), [100.0 + i for i in range(40)])
    entries = pd.Series(0, index=bars.index)
    entries.iloc[:5] = 1

    gc = bt.summarize(bt.evaluate(bars, entries, GC), GC, 5)
    spot = bt.summarize(bt.evaluate(bars, entries, SPOT), SPOT, 5)
    assert gc["expectancy_usd"] == pytest.approx(gc["expectancy_ticks"] * 10.0)
    assert np.isnan(spot["expectancy_usd"])
    assert spot["expectancy_ticks"] == pytest.approx(gc["expectancy_ticks"] * 10.0)


# --------------------------------------------------------------------------
# The committed signatures. split.md §3 point 4 -- this is what buys the
# independence, so it is asserted rather than remembered.
# --------------------------------------------------------------------------
PORTABLE = ["to_bp", "atr_bp", "range_bp", "rv_parkinson", "rv_slope", "efficiency_ratio", "session_phase", "event_proximity", "anchors", "mid", "spread_bp", "quote_rate_z"]


def test_every_committed_portable_name_exists_in_its_frozen_order() -> None:
    order = [n for n in pt.__dict__ if n in set(PORTABLE)]
    assert order == PORTABLE, "names and order are §4's table; changing either needs standup"


def test_the_unwritten_bodies_refuse_rather_than_return_something() -> None:
    bars = bars_at([0, 1], [100.0, 100.5])
    for fn in (pt.range_bp, pt.mid, pt.spread_bp):
        with pytest.raises(NotImplementedError):
            fn(bars)
    for name in ("m1_geometry", "m2_vol_momentum", "m3_session_event"):
        assert callable(getattr(st, name)), "committed on day one, filled in later"


def test_the_committed_atr_bp_edges_have_not_drifted() -> None:
    # A tripwire, not a derivation. The reasoning is in
    # plans/team/strategy-precommit.md §2 and the numbers are the archive's
    # pooled quartiles rounded; this asserts nobody edits them without going
    # back to that file. A threshold that can be changed silently is not one.
    assert pt.ATR_BP_EDGES == (0.0, 7.0, 10.0, 14.0, float("inf"))
