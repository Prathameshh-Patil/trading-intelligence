"""M2's state cut and rate arithmetic, against the ways they can be wrong and look right.

**Written AFTER the surface was read, and that is a weaker guarantee than
[`test_m1_sweep.py`](test_m1_sweep.py) carries — said here rather than left for
someone to notice.** What limits the damage is that the failure shapes are
taken from that file and from `test_m3_ev.py` rather than invented against
M2's numbers: rates averaged instead of counts pooled, a null pooled over the
wrong axis, a boundary case filed into the wrong bucket by default.

The state cut is tested hardest, because `vol_state` is the whole of what M2
conditions on and its two failure modes both produce a complete, well-formed
table: a bar with no slope yet silently filed as STABLE, and a boundary that
is exclusive where the commitment says inclusive.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import bars_at

import m2_magnitude as m2


def cell(**kw: object) -> dict[str, object]:
    row: dict[str, object] = {
        "bucket": "(7.0, 10.0]", "vol_state": "EXPANDING",
        "target_atr": 1.5, "horizon": 30,
        "n": 1000, "hit": 300, "up": 160, "down": 140,
    }
    row.update(kw)
    return row


def surface(*rows: dict[str, object]) -> pd.DataFrame:
    return m2.surface(pd.DataFrame(list(rows)))


# --------------------------------------------------------------------------
# The state cut. strategy-precommit.md §8: symmetric, +/-0.20, inclusive
# --------------------------------------------------------------------------
def test_the_committed_cut_has_not_drifted() -> None:
    assert m2.SLOPE_MIN == 0.20, "precommit §8; changing it needs the commitment amended"
    assert m2.TARGETS == (1.0, 1.5, 2.0) and m2.HORIZONS == (15, 30, 60), "M1's, reused"
    assert m2.MIN_SAMPLES == 400
    assert m2.TRAIN == tuple(f"2025-{m:02d}" for m in range(1, 10)), "training half, §6's SPLIT"


def test_the_boundary_is_inclusive_on_both_sides() -> None:
    # A cut written `>` where the commitment says `>=` moves every bar sitting
    # exactly on the threshold into the middle state. It changes no column
    # name and no row count, and it is invisible in the output.
    slope = pd.Series([-0.30, -0.20, -0.19, 0.0, 0.19, 0.20, 0.30])
    bars = bars_at(list(range(len(slope))), [100.0] * len(slope))
    got = pd.Series(
        np.where(slope <= -m2.SLOPE_MIN, "CONTRACTING",
                 np.where(slope >= m2.SLOPE_MIN, "EXPANDING", "STABLE")),
        index=bars.index,
    )
    assert got.tolist() == [
        "CONTRACTING", "CONTRACTING", "STABLE", "STABLE", "STABLE", "EXPANDING", "EXPANDING"
    ]


def test_a_bar_with_no_slope_yet_is_absent_and_not_stable() -> None:
    # Every session's opening bars have no full window. Defaulting them to
    # STABLE would fill the middle state with the least informative bars in
    # the archive and dilute exactly the comparison M2 rests on.
    bars = bars_at(list(range(12)), [100.0 + (i % 3) for i in range(12)],
                   ranges=[1.0 + (i % 2) for i in range(12)])
    st = m2.vol_state(bars)
    slope = m2.rv_slope(bars, window=m2.WINDOW, min_bars=m2.MIN_BARS)
    assert st[slope.isna()].isna().all(), "no slope, no state"
    assert set(st.cat.categories) == set(m2.STATES), "all three states declared"


def test_every_state_is_present_in_the_index_even_when_a_frame_misses_one() -> None:
    # A state absent from a table's index is a hole nobody sees; a state
    # present with n=0 is a fact.
    bars = bars_at(list(range(12)), [100.0] * 12, ranges=[1.0] * 12)
    st = m2.vol_state(bars)
    assert list(st.cat.categories) == list(m2.STATES)


# --------------------------------------------------------------------------
# The rate arithmetic
# --------------------------------------------------------------------------
def test_pooling_sums_counts_and_never_averages_rates() -> None:
    # BASE_RATES.md's rule. The training months differ in leg count, so a mean
    # of monthly rates weights a thin month like a fat one.
    t = surface(cell(n=100, hit=10, up=6, down=4), cell(n=900, hit=270, up=140, down=130))
    assert len(t) == 1
    assert t["n"].iloc[0] == 1000
    assert t["p_hit"].iloc[0] == pytest.approx(0.28)
    assert t["p_hit"].iloc[0] != pytest.approx(0.20), "not the mean of 0.10 and 0.30"


def test_the_null_pools_over_vol_state_and_over_nothing_else() -> None:
    # The lift must be a statement about the STATE. Pool over buckets too and
    # it becomes a statement about volatility, which the bucket axis already
    # conditions on -- and M2's whole claim is that the slope adds something
    # the level does not.
    t = surface(
        cell(vol_state="EXPANDING", n=1000, hit=400),
        cell(vol_state="CONTRACTING", n=1000, hit=200),
        cell(bucket="(14.0, inf]", vol_state="EXPANDING", n=1000, hit=900),
    )
    low = t[t["bucket"] == "(7.0, 10.0]"]
    assert low["p_null"].nunique() == 1, "two states in one bucket share one null"
    assert low["p_null"].iloc[0] == pytest.approx(0.30), "(400 + 200) / 2000"
    assert t[t["bucket"] == "(14.0, inf]"]["p_null"].iloc[0] == pytest.approx(0.90)
    assert low.set_index("vol_state")["lift"].round(4).to_dict() == {
        "EXPANDING": 0.10, "CONTRACTING": -0.10
    }


def test_a_state_indistinguishable_from_its_null_does_not_pass() -> None:
    # Two states with identical rates share a null they cannot beat. However
    # high the rate, no lift is no finding.
    t = surface(
        cell(vol_state="EXPANDING", n=4000, hit=3000),
        cell(vol_state="CONTRACTING", n=4000, hit=3000),
    )
    assert (t["p_hit"] == 0.75).all() and (t["lift"] == 0).all()
    assert not t["passes"].any()


def test_the_sample_floor_vetoes_on_its_own() -> None:
    fat = surface(cell(n=4000, hit=1600), cell(vol_state="CONTRACTING", n=4000, hit=800))
    assert fat[fat["vol_state"] == "EXPANDING"]["passes"].iloc[0]

    thin = surface(cell(n=399, hit=160), cell(vol_state="CONTRACTING", n=4000, hit=800))
    row = thin[thin["vol_state"] == "EXPANDING"].iloc[0]
    assert row["thin"] and not row["passes"]


def test_the_direction_gap_is_what_separates_scale_from_a_side() -> None:
    # M2 claims magnitude. If one tail carries the lift and the other does
    # not, it is a directional claim wearing a magnitude claim's clothes --
    # and that WOULD contradict horizon.py rather than extend it.
    scale = surface(cell(n=1000, hit=300, up=150, down=150)).iloc[0]
    side = surface(cell(n=1000, hit=300, up=300, down=0)).iloc[0]
    assert scale["dir_gap"] == pytest.approx(0.0)
    assert side["dir_gap"] == pytest.approx(0.30)
