"""The served table's two promises: it never guesses, and its key round-trips.

**Written before the 19-month build finished and before any served number was
read.** `reach.lookup` is the last thing between the archive and a trader, so
what is tested here is not arithmetic -- `m1_sweep` owns that and has its own
suite -- but the two ways this module could hand out a number it has no right
to:

  * **answering from a different population than the one asked about**, which
    is what any fallback to a coarser bucket does, and
  * **labelling a live bar into a bucket the build never used**, which makes
    every lookup miss and the product silently serve nothing at all.

The second is the quieter failure. A fallback at least shows up as a number
that behaves oddly; a key mismatch shows up as `forecast: null` on every bar,
which looks exactly like an honest, empty table.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest
from conftest import bars_at

import m1_sweep
import reach
from features.portable import ATR_BP_EDGES, atr_bp, session_phase
from instruments import GC
from m2_magnitude import vol_state

CELL = reach.Cell("GC", "(7.0, 10.0]", "London-NY", "EXPANDING", 1)


def table(*rows: dict[str, object]) -> pd.DataFrame:
    base: dict[str, object] = {
        "instrument": "GC", "bucket": "(7.0, 10.0]", "phase": "London-NY",
        "vol_state": "EXPANDING", "side": 1,
        "target_atr": 3.0, "stop_atr": 1.0, "horizon": 30,
        "n": 1000, "p_target": 0.2, "p_target_max": 0.24, "p_stop": 0.5,
        "p_neither": 0.3, "ev_lo": 0.01, "ev_sym": -0.02, "passes": True,
    }
    return pd.DataFrame([{**base, **r} for r in (rows or ({},))])


def get(t: pd.DataFrame, cell: reach.Cell = CELL) -> dict[str, float] | None:
    return reach.lookup(t, cell, target_atr=3.0, stop_atr=1.0, horizon=30)


# --------------------------------------------------------------------------
# It never guesses
# --------------------------------------------------------------------------
def test_a_thin_cell_is_none_and_not_a_number() -> None:
    assert get(table({"n": 400})) is not None
    assert get(table({"n": 399})) is None, "the floor is precommit §3's, and it binds here"


def test_a_thin_cell_does_not_fall_back_to_a_coarser_bucket() -> None:
    # **The failure this exists to stop.** The parent -- same bucket and side,
    # phase and vol_state pooled out -- is enormous and would give a confident
    # answer. Serving it under this cell's label is a forecast computed from a
    # different population, which is the same error class as `has_flow`
    # degrading instead of raising, and it looks exactly like the real one.
    t = table(
        {"n": 50},                                        # the cell asked about
        {"phase": "Asia", "vol_state": "STABLE", "n": 90_000},   # a fat sibling
    )
    assert get(t) is None
    assert t["n"].sum() > 90_000, "the fat rows are there to be found, and are not"


def test_a_cell_the_archive_has_no_row_for_is_none() -> None:
    unseen = dataclasses.replace(CELL, phase="Asia-London")
    assert get(table(), unseen) is None


def test_two_rows_for_one_key_is_none_rather_than_the_first_one() -> None:
    # A duplicated key means the build is wrong. Answering from row zero would
    # hide that behind a plausible number for as long as nobody checked.
    assert get(table({}, {})) is None


def test_only_the_served_columns_come_back() -> None:
    got = get(table())
    assert got is not None
    assert set(got) == set(reach.SERVED)
    assert "ev_lo" not in got and "passes" not in got, (
        "EV and the pass line are M1's tools for reading a surface, not numbers "
        "a trader audits a forecast with"
    )


def test_the_tie_band_survives_to_the_caller() -> None:
    got = get(table({"p_target": 0.2, "p_target_max": 0.31}))
    assert got is not None
    assert got["p_target"] == 0.2 and got["p_target_max"] == 0.31
    assert "p" not in got, "there is no single p; the band is the answer"


def test_a_key_cannot_be_edited_after_it_is_built() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        CELL.bucket = "(14.0, inf]"  # type: ignore[misc]


def test_reach_omits_thin_brackets_and_returns_empty_rather_than_none() -> None:
    t = pd.concat([
        table({"target_atr": 3.0, "stop_atr": 1.0, "n": 1000}),
        table({"target_atr": 4.0, "stop_atr": 1.0, "n": 12}),
    ], ignore_index=True)
    got = reach.reach(t, CELL, horizon=30)
    assert [(r["target_atr"], r["stop_atr"]) for r in got] == [(3.0, 1.0)]

    thin = table({"n": 3})
    assert reach.reach(thin, CELL, horizon=30) == [], (
        "an empty list is a real answer -- this bucket is too thin at every bracket"
    )


# --------------------------------------------------------------------------
# The key round-trips. The quiet failure.
# --------------------------------------------------------------------------
def test_the_live_key_is_labelled_exactly_as_the_build_labels_it() -> None:
    # If `cell_of` and `month_counts` disagree about how a bucket, a phase or a
    # vol state is spelled, every lookup misses and the product serves
    # `forecast: null` on every bar -- indistinguishable from an honest empty
    # table. This asserts the three labels are produced by the same expressions.
    # 150 minutes, because a complete key needs two chained 60-minute windows:
    # rv_slope compares this hour's Parkinson vol against the previous hour's.
    bars = bars_at(list(range(150)), [100.0 + (i % 5) * 0.4 for i in range(150)],
                   ranges=[0.5 + (i % 3) * 0.5 for i in range(150)])
    cells = reach.cell_of(bars, GC, side=1)

    want_bucket = pd.cut(
        atr_bp(bars, GC, window="60min", min_bars=6).to_numpy(), list(ATR_BP_EDGES)
    ).astype(str)
    want_phase = session_phase(bars, GC).astype("object")
    want_state = vol_state(bars).astype("object")

    seen = 0
    for i, c in enumerate(cells):
        if c is None:
            continue
        seen += 1
        assert c.bucket == want_bucket[i]
        assert c.phase == want_phase.iloc[i]
        assert c.vol_state == want_state.iloc[i]
        assert c.instrument == GC.name and c.side == 1
    assert seen, "the fixture must exercise at least one complete key"


def test_a_bar_whose_window_is_not_full_gets_no_key_at_all() -> None:
    # None rather than a guess at which bucket it would have been in. Every
    # session's opening bars land here, and they must not be filed into the
    # middle of any axis by default.
    bars = bars_at(list(range(6)), [100.0] * 6, ranges=[1.0] * 6)
    assert reach.cell_of(bars, GC).isna().all()


def test_the_key_and_the_builds_group_columns_are_the_same_five() -> None:
    # KEY is what lookup filters on; m1_sweep.keys is what the build groups by.
    # Drift between them is a silent miss on every row.
    built = m1_sweep.keys(reach.AXES)
    assert [k for k in reach.KEY if k != "instrument"] == [c for c in built
                                                           if c not in m1_sweep.GEOMETRY]
    assert reach.MIN_SAMPLES == m1_sweep.MIN_SAMPLES == 400


# --------------------------------------------------------------------------
# The build resumes, and refuses a cache built under other rules.
# Added 9 Sep after a 26-minute run was interrupted and lost everything.
# --------------------------------------------------------------------------
def test_a_cache_built_under_different_parameters_is_refused_not_reused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # **The failure this exists to stop.** Reusing counts across a change to the
    # grid or the bucket edges pools two different definitions into one table.
    # Every row still has an n and a p, nothing downstream can see it, and the
    # served number is wrong. Loud refusal is the only safe behaviour.
    cache = tmp_path / "c"
    reach._checked_cache(cache)
    assert (cache / "_stamp.json").exists()
    reach._checked_cache(cache), "the same parameters reuse it silently, as they should"

    stale = json.loads((cache / "_stamp.json").read_text())
    stale["edges"] = [0.0, 8.0, 12.0, 18.0, float("inf")]
    (cache / "_stamp.json").write_text(json.dumps(stale))
    with pytest.raises(SystemExit, match="different parameters"):
        reach._checked_cache(cache)


def test_the_stamp_covers_everything_the_counts_depend_on() -> None:
    # A stamp that omits an input is a stamp that passes while the cache is
    # stale. These five are every parameter month_counts is called with.
    s = reach._stamp()
    assert set(s) == {"grid", "edges", "axes", "bars", "atr_window", "atr_min_bars"}
    assert s["grid"] == [list(g) for g in m1_sweep.GRID]
    assert s["edges"] == list(ATR_BP_EDGES)
    assert s["axes"] == list(reach.AXES)


# The desktop app ships a JSON copy of the served table -- 8,256 rows of
# probabilities, hand-produced, with no generator script and nothing checking
# it. A number that drifts there is a wrong number in front of a trader with a
# right one on disk, and it is invisible from either side.
FIXTURE = Path(__file__).resolve().parents[3] / "apps/desktop/public/fixtures/reach_table.json"


def test_the_apps_fixture_still_says_what_the_table_says() -> None:
    """Every served number the desktop app ships must equal the CSV's, exactly."""
    if not FIXTURE.exists():
        pytest.skip(f"no app fixture at {FIXTURE}")
    table = Path("analysis/reach_table.csv")
    if not table.exists():
        pytest.skip("reach_table.csv not built")

    live = pd.read_csv(table)
    live = live[live["n"] >= reach.MIN_SAMPLES]
    served = {
        (r["bucket"], r["phase"], r["vol_state"], int(r["side"]),
         r["target_atr"], r["stop_atr"], r["horizon"]):
            [int(r["n"]), *(round(float(r[c]), 4) for c in
                            ("p_target", "p_target_max", "p_stop", "p_neither"))]
        for r in live.to_dict("records")
    }
    shipped = json.loads(FIXTURE.read_text())

    assert shipped["minSamples"] == reach.MIN_SAMPLES
    assert shipped["_row"] == ["targetAtr", "stopAtr", "horizonMinutes",
                               "n", "p", "pMax", "pStop", "pNeither"]

    seen = 0
    for key, rows in shipped["cells"].items():
        bucket, phase, state, side = key.split("|")
        for tgt, stp, hz, n, *probs in rows:
            assert [n, *probs] == served[(bucket, phase, state, int(side), tgt, stp, hz)], \
                f"{key} {tgt}/{stp}/{hz}"
            seen += 1
    assert seen == len(served), "the fixture ships a different number of rows than the table serves"
