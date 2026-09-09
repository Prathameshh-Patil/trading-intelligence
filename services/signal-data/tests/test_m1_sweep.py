"""M1's surface arithmetic, tested against the ways it can be wrong and look right.

**Written while the sweep was still running and before any surface was read.**
That is the point: a test written after the result is a test fitted to the
result, and `m1_sweep.surface()` decides what counts as a positive-EV cell.

Written against failure modes rather than the happy path, following
`test_m3_ev.py` -- both of 2026-09-06's M3 bugs produced complete, well-formed,
correctly typed output and reversed the conclusion, and nothing in the suite
would have caught either. Every test here is one of those shapes:

  * an EV term dropped or mis-signed,
  * unresolved legs scored at zero rather than at what they were worth,
  * rates averaged instead of counts pooled,
  * the null pooled over the wrong axis, which makes every lift meaningless,
  * the side mirror silently failing to join, which is what turns the
    archive's drift into a finding.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import m1_sweep as m1
from horizon import mde_rate


def cell(**kw: object) -> dict[str, object]:
    """One row of `month_counts` output. Counts, never rates."""
    row: dict[str, object] = {
        "bucket": "(7.0, 10.0]", "phase": "NY", "side": 1,
        "target_atr": 2.0, "stop_atr": 1.0, "horizon": 30,
        "n": 1000, "target": 200, "stop": 500,
        "open_pnl": 0.0, "cost_atr": 0.0,
    }
    row.update(kw)
    # The tie band collapses unless a test opens it: ties="target" can only
    # move a leg from the stop column to the target one.
    row.setdefault("target_max", row["target"])
    row.setdefault("stop_min", row["stop"])
    return row


def surface(*rows: dict[str, object]) -> pd.DataFrame:
    return m1.surface(pd.DataFrame(list(rows)))


def one(*rows: dict[str, object]) -> pd.Series:
    t = surface(*rows)
    assert len(t) == 1
    return t.iloc[0]


# --------------------------------------------------------------------------
# The EV terms
# --------------------------------------------------------------------------
def test_a_target_is_worth_its_multiple_and_a_stop_costs_its_own() -> None:
    r = one(cell(n=100, target=50, stop=50, target_atr=2.0, stop_atr=1.0))
    assert r["ev_barrier"] == pytest.approx((2.0 * 50 - 1.0 * 50) / 100)
    assert r["ev_lo"] == pytest.approx(0.5)


def test_an_unresolved_leg_is_worth_its_realized_move_not_zero() -> None:
    # The bug that reversed M3's conclusion, in this file's arithmetic. 43% of
    # real legs land here and they are not neutral: a leg that survived the
    # horizon without touching a nearby stop survived BECAUSE it drifted the
    # right way. Scoring them 0 charges the strategy for every stop and credits
    # it for no part of the tape it actually held.
    r = one(cell(n=100, target=0, stop=0, open_pnl=25.0))
    assert r["p_neither"] == pytest.approx(1.0)
    assert r["ev_barrier"] == pytest.approx(0.0)
    assert r["ev_lo"] == pytest.approx(0.25), "an unresolved leg is worth its move"


def test_the_decomposition_is_exact_and_not_a_second_calculation() -> None:
    # ev_barrier and ev_open exist so a cell whose EV is all mark-to-market
    # cannot be read as a cell that made money. They are only worth reporting
    # if they add up to the number they are splitting.
    r = one(cell(n=400, target=90, stop=210, open_pnl=33.0, cost_atr=8.0))
    assert r["ev_barrier"] + r["ev_open"] == pytest.approx(r["ev_lo"] + r["cost"])


def test_the_tie_band_only_ever_opens_upward() -> None:
    # `ties="target"` moves legs from the stop column to the target one and
    # never the reverse, so ev_hi >= ev_lo by construction. The band is not
    # decoration at this grid: 20.45% of bars are wide enough to tie at
    # 0.75x/0.5x against 0.13% at 3.0x/1.0x -- M3_CLOCK.md §3.2.
    r = one(cell(n=100, target=20, stop=60, target_max=35, stop_min=45))
    assert r["ev_hi"] > r["ev_lo"]
    assert r["p_target_max"] > r["p_target"]

    flat = one(cell(n=100, target=20, stop=60))
    assert flat["ev_hi"] == pytest.approx(flat["ev_lo"]), "no ties, no band"


# --------------------------------------------------------------------------
# Pooling. BASE_RATES.md's rule, and the archive's mix is why it matters
# --------------------------------------------------------------------------
def test_pooling_sums_counts_and_never_averages_rates() -> None:
    # A quiet month and a loud one put wildly different leg counts in the same
    # bucket -- 2025-08 spends 69% of its bars under 7 bp, 2026-03 spends 66%
    # above 14. A mean of monthly rates weights a 19-leg cell like a 13,000-leg
    # one, so the answer here must be 280/1000 and never (0.10 + 0.30) / 2.
    r = one(cell(n=100, target=10, stop=0), cell(n=900, target=270, stop=0))
    assert r["n"] == 1000
    assert r["p_target"] == pytest.approx(0.28)
    assert r["p_target"] != pytest.approx(0.20)


def test_cost_is_weighted_by_each_month_s_own_scale() -> None:
    # 1.4 ticks is a different fraction of the move in a quiet month than in a
    # loud one, so cost is accumulated in ATR units per cell and divided once.
    # A quiet month paying 0.05 ATR a leg on 100 legs and a loud one paying
    # 0.01 on 900 pools to 14/1000, not to the mean of 0.05 and 0.01.
    r = one(cell(n=100, cost_atr=5.0), cell(n=900, cost_atr=9.0))
    assert r["cost"] == pytest.approx(0.014)
    assert r["cost"] != pytest.approx(0.03)


# --------------------------------------------------------------------------
# The null. Pooled over the wrong axis and every lift in the file is meaningless
# --------------------------------------------------------------------------
def test_the_null_pools_over_phases_and_over_nothing_else() -> None:
    # A phase's lift is a statement about the CLOCK, so its null is the same
    # bucket, side and geometry with the clock averaged out. Pool over buckets
    # too and the lift becomes a statement about volatility wearing a phase's
    # name.
    t = surface(
        cell(phase="NY", n=1000, target=100, stop=0),
        cell(phase="Asia", n=1000, target=300, stop=0),
        cell(bucket="(14.0, inf]", phase="NY", n=1000, target=900, stop=0),
    )
    low = t[t["bucket"] == "(7.0, 10.0]"]
    assert low["p_null"].nunique() == 1, "two phases in one bucket share one null"
    assert low["p_null"].iloc[0] == pytest.approx(0.20), "(100 + 300) / 2000"
    assert t[t["bucket"] == "(14.0, inf]"]["p_null"].iloc[0] == pytest.approx(0.90), (
        "a different bucket is a different null"
    )
    assert low.set_index("phase")["lift"].round(4).to_dict() == {"NY": -0.10, "Asia": 0.10}


def test_mde_is_computed_off_the_null_and_the_cell_s_own_n() -> None:
    r = one(cell(n=1000, target=280, stop=500))
    assert r["mde"] == pytest.approx(mde_rate(r["p_null"], 1000))
    # And it must fall as n rises -- a bigger cell can prove a smaller lift.
    small = one(cell(n=500, target=140, stop=250))
    assert small["mde"] > r["mde"]


# --------------------------------------------------------------------------
# The side mirror. Without it the archive's drift reads as geometry
# --------------------------------------------------------------------------
def test_a_market_that_only_drifts_has_ev_sym_of_zero() -> None:
    # Measured on 2026-07 before the sweep ran: a 1.0x/1.0x cell reads +0.088
    # ATR long and -0.095 short. That is the month's direction wearing a
    # bracket's clothes, and `ev_sym` is what says so.
    t = surface(
        cell(side=1, n=1000, target=600, stop=400, target_atr=1.0, stop_atr=1.0),
        cell(side=-1, n=1000, target=400, stop=600, target_atr=1.0, stop_atr=1.0),
    )
    assert t["ev_lo"].tolist() == pytest.approx([0.2, -0.2])
    assert t["ev_sym"].tolist() == pytest.approx([0.0, 0.0])


def test_ev_sym_is_absent_rather_than_zero_when_there_is_no_mirror() -> None:
    # A one-sided run has nothing to average against. Zero would read as
    # "measured, and symmetric", which is a different and much stronger claim
    # than "not measured".
    r = one(cell(side=1, n=1000, target=600, stop=400))
    assert np.isnan(r["ev_mirror"]) and np.isnan(r["ev_sym"])


def test_the_mirror_joins_on_geometry_and_not_just_on_side() -> None:
    # The failure this catches: a merge that pairs a cell with the opposite
    # side of a DIFFERENT bracket. Both rows would still get a number.
    t = surface(
        cell(side=1, target_atr=2.0, n=1000, target=300, stop=400),
        cell(side=-1, target_atr=4.0, n=1000, target=100, stop=600),
    )
    assert t["ev_sym"].isna().all(), "different geometry is not a mirror"


# --------------------------------------------------------------------------
# The pass line. strategy-precommit.md §1, all three or the cell is not positive
# --------------------------------------------------------------------------
def test_the_sample_floor_is_400_and_not_backtest_s_30() -> None:
    import backtest

    assert m1.MIN_SAMPLES == 400, "strategy-precommit.md §3; a change needs the commitment amended"
    assert backtest.MIN_SAMPLES == 30, "Track A's reporting flag is a different object"
    assert one(cell(n=399, target=200, stop=0))["thin"]
    assert not one(cell(n=400, target=200, stop=0))["thin"]


# A dull neighbour in the same bucket, so the phase-pooled null sits well below
# the cell under test. A single cell IS its own null -- see the test below -- so
# there is no such thing as a lone passing cell, and that is correct.
QUIET = cell(phase="Asia", n=20000, target=1400, stop=12000)


def only(row: dict[str, object]) -> pd.Series:
    t = surface(row, QUIET)
    return t[t["phase"] == "NY"].iloc[0]


def test_each_condition_can_veto_the_pass_on_its_own() -> None:
    # Fat, profitable, and past its own MDE: p_target 0.40 against a pooled
    # null of 0.125, on 4,000 legs.
    good = cell(n=4000, target=1600, stop=1200, target_atr=2.0, stop_atr=1.0)
    r = only(good)
    assert (r["n"], r["p_target"]) == (4000, pytest.approx(0.40))
    assert r["ev_lo"] > 0 and r["beats_mde"] and not r["thin"] and r["passes"]

    thin = only(cell(**{**good, "n": 300, "target": 120, "stop": 90}))
    assert thin["thin"] and not thin["passes"], "n below the floor vetoes"

    # Same rates, but the cost floor eats it. EV is what a lane dies on --
    # M3 proved a surviving profile can still be worth nothing.
    priced = only(cell(**{**good, "cost_atr": 4000 * 0.6}))
    assert priced["beats_mde"] and priced["ev_lo"] < 0 and not priced["passes"]


def test_a_cell_cannot_pass_on_a_lift_its_own_n_could_not_prove() -> None:
    # The third condition, and the one that is easy to leave out because the
    # cell looks profitable without it. Two phases, identical EV, identical
    # p_target -- so neither has any lift over the null they share, and neither
    # may be read as a finding however good the EV looks.
    t = surface(
        cell(phase="NY", n=4000, target=1600, stop=1200),
        cell(phase="Asia", n=4000, target=1600, stop=1200),
    )
    assert (t["ev_lo"] > 0).all(), "profitable"
    assert (t["lift"] == 0).all() and not t["beats_mde"].any()
    assert not t["passes"].any(), "profitable and indistinguishable from its null is not a finding"


def test_a_cell_undecided_by_the_tie_band_is_flagged_and_does_not_pass() -> None:
    # Profitable if every same-bar tie resolved to the target, unprofitable if
    # they all resolved to the stop. No bar frame can say which, so it is
    # undecided until step 5's replay -- not a finding, and not a rejection.
    r = one(cell(n=1000, target=300, stop=500, target_max=420, stop_min=380,
                 target_atr=1.5, stop_atr=1.0))
    assert r["ev_lo"] <= 0 < r["ev_hi"]
    assert r["undecided"] and not r["passes"]


def test_m1_enters_every_bar_and_the_sweep_uses_that_one_definition() -> None:
    # `m1_geometry` has no entry condition on purpose: M1 asks what geometry
    # the tape supports, which is a property of the tape and not of a signal.
    #
    # This also pins the provenance of the 2026-09-06 run. The sweep built its
    # entries inline as `pd.Series(side, index=bars.index)` while it was in
    # flight and was wired to `m1_geometry` afterwards; the surface on disk is
    # only the surface this code produces if the two are identical, so that is
    # asserted rather than assumed.
    from conftest import bars_at

    import strategies as st
    from instruments import GC

    bars = bars_at(list(range(10)), [100.0 + i for i in range(10)])
    for side in (1, -1):
        got = st.m1_geometry(bars, GC, side=side)
        pd.testing.assert_series_equal(
            got, pd.Series(side, index=bars.index).astype("int64"), check_names=False
        )

    with pytest.raises(ValueError, match="must be \\+1 or -1"):
        st.m1_geometry(bars, GC, side=0)


# --------------------------------------------------------------------------
# The conditioning axis and ev_delta -- precommit §9. Written while the
# EXPANDING run was in flight and before its surface was read.
# --------------------------------------------------------------------------
def vcell(**kw: object) -> dict[str, object]:
    """A cell on the vol_state axis rather than the phase axis."""
    row = cell()
    row["vol_state"] = row.pop("phase")
    row.update(kw)
    return row


def test_the_axis_is_a_parameter_and_the_null_pools_out_whichever_one_is_used() -> None:
    # The failure this catches: the null pooling over `phase` by name while the
    # sweep conditions on `vol_state`. Every cell would still get a p_null, and
    # it would be the cell's own rate -- so every lift would be exactly zero
    # and the run would report "conditioning adds nothing" whatever the data said.
    t = m1.surface(pd.DataFrame([
        vcell(vol_state="EXPANDING", n=1000, target=300, stop=0),
        vcell(vol_state="STABLE", n=1000, target=100, stop=0),
    ]), axes=("vol_state",))
    assert list(t["vol_state"]) != []
    assert t["p_null"].nunique() == 1 and t["p_null"].iloc[0] == pytest.approx(0.20)
    assert set(t["lift"].round(4)) == {0.10, -0.10}


def test_ev_delta_is_what_conditioning_added_and_nothing_else() -> None:
    # precommit §9's whole question. The null is the SAME cell with the axis
    # pooled out, so a state that behaves exactly like the pool must show
    # ev_delta of zero however good or bad its EV is in absolute terms.
    same = m1.surface(pd.DataFrame([
        vcell(vol_state="EXPANDING", n=1000, target=300, stop=500),
        vcell(vol_state="STABLE", n=1000, target=300, stop=500),
    ]), axes=("vol_state",))
    assert (same["ev_delta"].round(10) == 0).all(), "identical states add nothing"

    t = m1.surface(pd.DataFrame([
        vcell(vol_state="EXPANDING", n=1000, target=400, stop=400),
        vcell(vol_state="STABLE", n=1000, target=200, stop=600),
    ]), axes=("vol_state",))
    exp = t[t["vol_state"] == "EXPANDING"].iloc[0]
    # pooled: 600 targets, 1000 stops over 2000 legs at 2.0/1.0
    assert exp["ev_null"] == pytest.approx((2.0 * 600 - 1.0 * 1000) / 2000)
    assert exp["ev_delta"] == pytest.approx(exp["ev_lo"] - exp["ev_null"])
    assert exp["ev_delta"] > 0


def test_ev_delta_is_measured_net_of_cost_on_both_sides_of_the_comparison() -> None:
    # A cost subtracted from the cell but not from its null would make every
    # ev_delta look worse by exactly the cost, which is the size of the effect
    # §9 is testing for. Cost cancels when both carry it.
    free = m1.surface(pd.DataFrame([
        vcell(vol_state="EXPANDING", n=1000, target=400, stop=400),
        vcell(vol_state="STABLE", n=1000, target=200, stop=600),
    ]), axes=("vol_state",))
    priced = m1.surface(pd.DataFrame([
        vcell(vol_state="EXPANDING", n=1000, target=400, stop=400, cost_atr=42.3),
        vcell(vol_state="STABLE", n=1000, target=200, stop=600, cost_atr=42.3),
    ]), axes=("vol_state",))
    assert priced["ev_lo"].iloc[0] < free["ev_lo"].iloc[0], "cost lowers the cell"
    pd.testing.assert_series_equal(
        priced["ev_delta"], free["ev_delta"], check_names=False
    ), "and cancels out of what conditioning added"


def test_the_phase_axis_still_behaves_exactly_as_it_did() -> None:
    # M1_SURFACE.md was produced by the pre-parameter version of this function.
    # The default must reproduce it, or the published surface stops being the
    # surface this code makes.
    rows = [cell(phase="NY", n=1000, target=100, stop=0),
            cell(phase="Asia", n=1000, target=300, stop=0)]
    default = m1.surface(pd.DataFrame(rows))
    named = m1.surface(pd.DataFrame(rows), axes=("phase",))
    pd.testing.assert_frame_equal(default, named)
    assert default["p_null"].iloc[0] == pytest.approx(0.20)
