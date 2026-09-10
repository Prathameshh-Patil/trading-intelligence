"""Stage 7: the served reach table. What happened in this bucket, at this bracket.

`docs/strategy/ARCHITECTURE.md` §3 stage 7 and §6 step 7; the rejoin of
`plans/team/strategy-split.md` §6. **Decisions in `strategy-precommit.md` §10,
committed before this file existed.** Nothing here chooses anything.

    key = (instrument x atr_bp x phase x vol_state x side)

**This module is a LOOKUP, not a chooser.** It answers "how often did the
target come before the stop, in this bucket, at this bracket, and on how many
legs". It does not pick the bracket, does not pick a side, and has no opinion
about whether a trade is worth taking. Stage 9 decides that; the numbers here
are what it decides from.

THE THREE RULES, precommit §10, and each one is a way the table could lie.

  * **Below MIN_SAMPLES the answer is None -- and NOT a coarser bucket.** No
    falling back to the same cell with `phase` dropped, no pooling up to the
    parent. A forecast computed from a different population wearing this
    cell's label is the same error class as `has_flow` degrading instead of
    raising: it looks exactly like the real one. `forecast: null` is a valid
    and common answer, and it is the honest one here.
  * **Every answer carries the tie band.** `p_target` reads same-bar ties to
    the stop and `p_target_max` to the target; the truth is inside and no bar
    frame can say where. M1 measured 10.2% of cells undecided by that band and
    20.45% of bars wide enough to tie at the grid's tight corner, so a single
    `p` there is a precision the data does not have.
  * **The build tabulates and does not select**, which is why it runs on all
    19 months. Its validation is forward calibration -- `calibration.py`, does
    61% happen 61% of the time -- rather than a held-out split, because the
    table fits nothing for a split to protect against.

The counting is `m1_sweep`'s, called with both axes rather than reimplemented.
A second EV and first-touch convention is how two files quietly disagree about
what a leg is worth, which M3's two bugs already demonstrated once.

    PYTHONPATH=. uv run python reach.py              # ~1.6h, 19 months, both sides
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import m1_sweep
from features.portable import ATR_BP_EDGES, atr_bp, session_phase
from instruments import GC, Instrument
from m2_magnitude import vol_state

AXES = ("phase", "vol_state")
MIN_SAMPLES = m1_sweep.MIN_SAMPLES        # 400, precommit §3
KEY = ["instrument", "bucket", "phase", "vol_state", "side"]

# What stage 9 is served. Deliberately NOT the analysis columns -- `ev_lo`,
# `ev_sym` and the pass line are M1's tools for reading a surface, not numbers
# a trader audits a forecast with.
SERVED = ["n", "p_target", "p_target_max", "p_stop", "p_neither"]


@dataclass(frozen=True)
class Cell:
    """One bucket key. Frozen: a key that can be edited after a lookup is a key
    that can be edited to find a better answer."""

    instrument: str
    bucket: str
    phase: str
    vol_state: str
    side: int


def cell_of(bars: pd.DataFrame, inst: Instrument, *, window: str = "60min",
            min_bars: int = 6, side: int = 1) -> pd.Series:
    """The bucket key for every bar, as a Series of `Cell` (or None).

    This is the live path's half of the table: it turns a bar into the key the
    lookup is made with, using the same features the build used. A bar whose
    window is not full has no key and gets no forecast -- None rather than a
    guess at which bucket it would have been in.

    **The warm-up is about two hours, not one, and stage 9 has to budget for
    it.** `vol_state` reads `rv_slope`, which compares this hour's Parkinson
    volatility against the previous hour's -- two chained 60-minute windows. So
    a feed that has just connected serves `forecast: null` for its first ~120
    minutes, which is correct rather than broken, and is worth saying out loud
    because it is otherwise discovered as "the product does not work at the
    open".
    """
    bp = atr_bp(bars, inst, window=window, min_bars=min_bars)
    bucket = pd.cut(bp.to_numpy(), list(ATR_BP_EDGES)).astype(str)
    phase = session_phase(bars, inst).astype("object")
    state = vol_state(bars).astype("object")
    out = [
        None if pd.isna(b) or pd.isna(p) or pd.isna(v) or b == "nan"
        else Cell(inst.name, str(b), str(p), str(v), side)
        for b, p, v in zip(bucket, phase, state, strict=True)
    ]
    return pd.Series(out, index=bars.index, dtype="object")


def lookup(table: pd.DataFrame, cell: Cell, *, target_atr: float, stop_atr: float,
           horizon: int) -> dict[str, float] | None:
    """One bucket, one bracket -> the served numbers, or **None**.

    None means one of two things and the caller must not distinguish them into
    a forecast: the cell is below `MIN_SAMPLES`, or the archive has no row for
    it at all. **Both are "we do not know", and neither is answered by widening
    the bucket.**
    """
    m = table[
        (table["instrument"] == cell.instrument)
        & (table["bucket"] == cell.bucket)
        & (table["phase"] == cell.phase)
        & (table["vol_state"] == cell.vol_state)
        & (table["side"] == cell.side)
        & (table["target_atr"] == target_atr)
        & (table["stop_atr"] == stop_atr)
        & (table["horizon"] == horizon)
    ]
    if len(m) != 1:
        return None
    row = m.iloc[0]
    if row["n"] < MIN_SAMPLES:
        return None
    return {k: float(row[k]) for k in SERVED}


def reach(table: pd.DataFrame, cell: Cell, *, horizon: int) -> list[dict[str, float]]:
    """Every bracket this cell can answer at one horizon, thin ones omitted.

    The shape S7's `PipForecast.reach` wants -- with `p_target_max` beside
    `p_target`, which the S7 draft has no field for. `strategy-precommit.md`
    §10 flags that as a seam mismatch for the room rather than reshaping the
    frozen-by-agreement contract here.

    An empty list is a real and expected answer: it says this bucket is too
    thin at every bracket, which stage 9 renders as `forecast: null`.
    """
    rows = []
    for tgt, stp, _hz in m1_sweep.GRID:
        if _hz != horizon:
            continue
        got = lookup(table, cell, target_atr=tgt, stop_atr=stp, horizon=horizon)
        if got is not None:
            rows.append({"target_atr": tgt, "stop_atr": stp, **got})
    return rows


# What the cached counts were produced under. A cache reused across a change to
# any of these is a table built from two different definitions, which is a wrong
# number that nothing downstream can see -- so the stamp is checked, not trusted.
def _stamp() -> dict[str, object]:
    return {
        "grid": [list(g) for g in m1_sweep.GRID],
        "edges": list(ATR_BP_EDGES),
        "axes": list(AXES),
        "bars": "5min", "atr_window": "60min", "atr_min_bars": 6,
    }


def _checked_cache(cache: Path) -> Path:
    """The cache directory, or a loud refusal if it was built under other rules."""
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / "_stamp.json"
    if f.exists():
        was = json.loads(f.read_text())
        if was != _stamp():
            raise SystemExit(
                f"{cache} was built under different parameters. Delete it and rebuild.\n"
                f"  cached: {was}\n     now: {_stamp()}"
            )
    else:
        f.write_text(json.dumps(_stamp(), indent=2))
    return cache


def build(data: Path, *, months: list[str] | None = None,
          sides: tuple[int, ...] = (1, -1),
          cache: Path = Path("analysis/.reach_cache")) -> pd.DataFrame:
    """Count the archive into the five-axis table. m1_sweep does the counting.

    **Checkpointed per (month, side), because the full build is ~1.7 hours and
    a run that writes nothing until the end loses all of it to one interruption
    -- which is exactly what happened on 9 Sep at 26 minutes in.** A restart
    costs only the month-sides that are missing.

    The cache is stamped with the grid, edges and axes it was produced under and
    **refuses to be reused across a change to any of them.** A stale cache would
    pool counts from two different definitions into one table, and nothing
    downstream could see it.
    """
    dirs = sorted(d for d in data.iterdir() if (d / "gc_trades.parquet").exists())
    if months:
        dirs = [d for d in dirs if d.name in set(months)]
    if not dirs:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {data}")
    cache = _checked_cache(cache)

    frames, t0 = [], time.perf_counter()
    for d in dirs:
        bars = None  # loaded once per month, and not at all if both sides are cached
        for side in sides:
            part = cache / f"{d.name}_{side:+d}.parquet"
            if part.exists():
                frames.append(pd.read_parquet(part))
                print(f"{d.name} side {side:+d}  cached", flush=True)
                continue
            if bars is None:
                bars = m1_sweep.gc_bars(d / "gc_trades.parquet", "5min")
            c = m1_sweep.month_counts(
                bars, GC, side=side,
                atr_window="60min", atr_min_bars=6, edges=ATR_BP_EDGES, axes=AXES,
            )
            c.to_parquet(part)
            frames.append(c)
            print(f"{d.name} side {side:+d}  {time.perf_counter() - t0:6.0f}s", flush=True)

    t = m1_sweep.surface(pd.concat(frames, ignore_index=True), axes=AXES)
    # GC only for now. The axis is present and carries one value, so a spot
    # table is appended later without touching a line of this file -- which is
    # the whole point of the seam step 1 built.
    t.insert(0, "instrument", GC.name)
    return t


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--months", nargs="+")
    p.add_argument("--out", type=Path, default=Path("analysis/reach_table.csv"))
    p.add_argument("--cache", type=Path, default=Path("analysis/.reach_cache"),
                   help="per-(month, side) counts, so an interrupted build resumes")
    a = p.parse_args()

    t = build(a.data, months=a.months, cache=a.cache)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out, index=False)

    cells = t.groupby(KEY, observed=True)["n"].max()
    live = cells[cells >= MIN_SAMPLES]
    print(f"\n=== {len(t)} rows over {len(cells)} cells; {len(live)} clear "
          f"MIN_SAMPLES={MIN_SAMPLES} ({len(live) / len(cells):.0%}) ===")
    print(f"written to {a.out}\n")
    print("cells clearing the floor, by phase x vol_state (both sides, all buckets):")
    ok = cells.reset_index().assign(live=lambda d: d["n"] >= MIN_SAMPLES)
    print(pd.crosstab(ok["phase"], ok["vol_state"], values=ok["live"], aggfunc="sum").to_string())
    print("\nthinnest cells that still clear, and the fattest that do not:")
    edge = cells.sort_values()
    print(f"  smallest clearing : {int(edge[edge >= MIN_SAMPLES].iloc[0])}")
    print(f"  largest not clearing: {int(edge[edge < MIN_SAMPLES].iloc[-1]) if (edge < MIN_SAMPLES).any() else 0}")
    print("\n**A cell below the floor returns None, never a coarser bucket.** precommit §10.")


if __name__ == "__main__":
    main()
