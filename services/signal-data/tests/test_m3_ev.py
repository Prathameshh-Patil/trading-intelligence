"""M3's EV arithmetic, and the two bugs that cost 2026-09-06.

`analysis/M3_CLOCK.md` §4. Both bugs produced complete, well-formed, correctly
typed output and reversed the conclusion, and neither was covered by a test.
This file is that coverage. It is written against the two failures rather than
against the happy path, because the happy path never broke.

  * **Bug 1 — bucketed in basis points, bracketed in fixed ticks.** Gold ran
    2,624 -> 5,627 over the archive, so a fixed 70-tick target meant ~25.6 bp
    at the start and ~13.9 bp at the end. `test_the_bracket_is_atr_relative...`
    is the pin: identical price ACTION at two price levels must give the same
    answer.
  * **Bug 2 — priced an unresolved leg at zero.** 43% of legs end unresolved,
    and they are not neutral: a leg that survived the horizon without touching
    a nearby stop survived BECAUSE it drifted the right way.
    `test_an_unresolved_leg_is_worth...` is the pin.

The last test is the SANITY CHECK that would have caught Bug 2 in seconds:
`horizon.py` measured GC as a directional random walk and `ohlcv_edge.py`
reproduced it on spot to within 0.4%, so **EV on a driftless series must come
out ~0.** Bug 2 produced -0.28 ATR per leg and contradicted a result this repo
already had.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import m3_profile as m3


def counts(**kw: float) -> pd.DataFrame:
    """One cell, in the shape `month_cells` emits."""
    row = {"n": 100.0, "target": 0.0, "stop": 0.0, "target_max": 0.0,
           "stop_min": 0.0, "open_pnl": 0.0, **kw}
    idx = pd.MultiIndex.from_tuples([("b", "NY", False)], names=["bucket", "phase", "near_event"])
    return pd.DataFrame([row], index=idx)


@pytest.fixture(autouse=True)
def bracket():
    """profile() prices EV in the bracket main() was invoked with."""
    m3.EV_TARGET, m3.EV_STOP = 3.0, 1.0
    yield


# --------------------------------------------------------------------------
# The payoffs
# --------------------------------------------------------------------------
def test_a_target_is_worth_the_target_and_a_stop_is_worth_the_stop() -> None:
    assert m3.profile(counts(target=100, target_max=100), ["phase"])["ev_lo"].iloc[0] == 3.0
    assert m3.profile(counts(stop=100, stop_min=100), ["phase"])["ev_lo"].iloc[0] == -1.0


def test_an_unresolved_leg_is_worth_its_realized_move_not_zero() -> None:
    # **Bug 2, pinned.** Every leg unresolved, carrying +50 ATR of realized
    # move between them. Priced at zero this cell reads 0.00 and the strategy
    # is charged for stops it never took while earning nothing from the paths
    # that quietly worked. 43% of real legs land here.
    got = m3.profile(counts(open_pnl=50.0), ["phase"])["ev_lo"].iloc[0]
    assert got == pytest.approx(0.5), "100 legs carrying +50 ATR is +0.5 ATR per leg"
    assert got != 0.0, "the bug this file exists for"


def test_the_three_outcomes_add_up() -> None:
    # 20 targets, 50 stops, 30 unresolved carrying +6 ATR between them.
    got = m3.profile(counts(target=20, target_max=20, stop=50, stop_min=50, open_pnl=6.0),
                     ["phase"])["ev_lo"].iloc[0]
    assert got == pytest.approx((3.0 * 20 - 1.0 * 50 + 6.0) / 100)


def test_the_band_is_the_two_tie_conventions_and_ev_hi_is_never_lower() -> None:
    # reach_table's rule: report the pair, never the midpoint. ties="target"
    # can only move a leg from the stop column to the target column.
    t = m3.profile(counts(target=10, stop=40, target_max=15, stop_min=35), ["phase"])
    assert t["ev_lo"].iloc[0] == pytest.approx((3.0 * 10 - 40) / 100)
    assert t["ev_hi"].iloc[0] == pytest.approx((3.0 * 15 - 35) / 100)
    assert t["ev_hi"].iloc[0] > t["ev_lo"].iloc[0]


def test_an_empty_cell_is_nan_not_zero() -> None:
    # A cell with no legs has no EV. Zero would read as "measured, and flat".
    assert np.isnan(m3.profile(counts(n=0), ["phase"])["ev_lo"].iloc[0])


# --------------------------------------------------------------------------
# The two bugs, end to end through month_cells
# --------------------------------------------------------------------------
def synthetic(path, *, level: float, seed: int, sessions: int = 10, minutes: int = 400):
    """A driftless random walk written as an S1 parquet, at a chosen price LEVEL.

    `level` is the whole point of the fixture: the same seed produces the same
    RETURNS, so two levels give identical price action and identical `atr_bp`
    while every tick-denominated quantity differs by the ratio of the levels.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(sessions):
        open_at = pd.Timestamp("2025-03-03T22:00:00Z") + pd.Timedelta(days=d)
        px = level
        for mi in range(minutes):
            for k in range(4):
                px *= 1.0 + rng.normal(0.0, 3e-4)  # driftless
                rows.append((open_at + pd.Timedelta(minutes=mi, seconds=15 * k), px,
                             10, "B" if rng.random() < 0.5 else "A"))
    df = pd.DataFrame(rows, columns=["timestamp", "price", "size", "aggressor_side"])
    df["size"] = df["size"].astype("int64")
    df["aggressor_side"] = df["aggressor_side"].astype("category")
    df.to_parquet(path)
    return path


def cells(path, **kw):
    from features.portable import ATR_BP_EDGES
    return m3.month_cells(path, target_atr=3.0, stop_atr=1.0, horizon=30, bar_size="5min",
                          atr_window="60min", atr_min_bars=6, edges=list(ATR_BP_EDGES),
                          event_window_minutes=15, side=1, **kw)


def test_the_bracket_is_atr_relative_so_the_price_level_cannot_move_the_answer(tmp_path) -> None:
    # **Bug 1, pinned.** Identical price ACTION at two price levels 4x apart.
    # atr_bp is identical by construction, so a bracket in multiples of ATR
    # must give the identical outcome table. A fixed TICK bracket does not --
    # that is what made a 70-tick target mean 25.6 bp early in the archive and
    # 13.9 bp late, and what moved the <7 bucket's null 0.0360 -> 0.1088 across
    # the split halves while the label stayed the same.
    lo = cells(synthetic(tmp_path / "lo.parquet", level=1000.0, seed=7))
    hi = cells(synthetic(tmp_path / "hi.parquet", level=4000.0, seed=7))

    assert lo["n"].sum() > 200, "fixture must carry enough legs to mean anything"
    pd.testing.assert_series_equal(lo["n"], hi["n"])
    pd.testing.assert_series_equal(lo["target"], hi["target"])
    pd.testing.assert_series_equal(lo["stop"], hi["stop"])


def test_ev_on_a_driftless_walk_is_about_zero(tmp_path) -> None:
    # **The sanity check that would have caught Bug 2 in seconds.** horizon.py
    # measured GC as a directional random walk and ohlcv_edge.py reproduced it
    # on spot to within 0.4%, so EV on a driftless series must come out ~0.
    # Pricing unresolved legs at zero produced -0.28 ATR per leg, contradicting
    # a result this repo already had, and nothing failed.
    c = cells(synthetic(tmp_path / "rw.parquet", level=3000.0, seed=11))
    # Through profile(), not a formula retyped here -- a sanity check that does
    # not exercise the code path it is guarding would have passed Bug 2 too.
    pooled = m3.profile(c, ["phase"])
    ev = float((pooled["ev_lo"] * pooled["n"]).sum() / pooled["n"].sum())
    t = c.sum()
    broken = 3.0 * t["target"] / t["n"] - 1.0 * t["stop"] / t["n"]  # neither priced at 0

    assert abs(ev) < 0.10, f"driftless walk must price near zero, got {ev:+.4f}"
    assert broken < -0.15, (
        "the fixture must actually exercise the bug -- if this fails the walk has too "
        "few unresolved legs to tell the two formulas apart"
    )
