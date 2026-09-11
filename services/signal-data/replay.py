"""Step 5: tick replay. Which barrier actually came first, when the bar cannot say.

`docs/strategy/ARCHITECTURE.md` §6 step 5 and `plans/team/strategy-split.md` §5.
Time budget set in that file before this one was written: **3 days.**

THE POPULATION THIS EXISTS FOR IS SMALL AND EXACTLY DEFINED. `backtest.
first_touch_from` walks a leg's window bar by bar and asks which barrier was
cleared first. Usually one bar clears one of them and there is nothing to
decide. Sometimes a single bar's high clears the target AND its low clears the
stop, and then **the order is not in the bar** -- an OHLC bar records four
prices and no sequence. `first_touch` resolves that by RULE: ties go to the
stop, which makes every `p_target` in this repo a stated lower bound, and
`ties="target"` is the same measurement at the other extreme. The truth is
inside that band and bar data cannot say where.

**This module says where.** It takes the legs a bracket ties on, walks the
trade prints inside that one bar in timestamp order, and reports which price
level printed first. That is the whole idea; everything else here is care about
not answering when the tape cannot either.

WHAT IT DOES NOT DO, and this is a constraint rather than an omission.
`strategy-split.md` §5: *"It ships as `replay.py`, standalone, producing an
intrabar ordering table. It does not change `backtest.first_touch`."* Changing
that function is a shared-spine change with Track A's tests as the gate, it is
Varad's, and it happens later and **only if the number here says it is worth
making**. So this module measures and does not fix. There is still exactly one
first-touch convention in the repo and it stays in `backtest.py`.

WHY THE TAPE CAN REFUSE TOO. Two prints can carry the same nanosecond, and a
bar can be tied by two prints that share one. `resolve` reports those as
`unresolved` rather than picking, because a tape that does not order two events
is in the same position the bar was -- and inventing an order there would be
the bar's rule wearing a tick-resolution label, which is worse than the rule.

    PYTHONPATH=. uv run python replay.py            # every month on disk
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import excursions
from instruments import GC, Instrument
from s1 import load_ticks

# What a tie resolved to. `unresolved` is a real answer, not a failure -- see
# the module docstring.
TARGET_FIRST = 1
STOP_FIRST = -1
UNRESOLVED = 0

# The bar the tape is walked inside. `m1_sweep` builds 5-minute bars, and a
# window wider than the bar would let a print from the NEXT bar decide this
# one's tie.
BAR = pd.Timedelta(minutes=5)


@dataclass(frozen=True)
class Bracket:
    """One point of `m1_sweep.GRID`, in TICKS rather than ATR multiples.

    Ticks because that is what `first_touch_from` takes and what a price level
    is computed from. The ATR scaling is `m1_sweep.month_counts`' job and is
    deliberately not repeated here -- a second copy of `atr_ticks` is a second
    place the bracket can drift.
    """

    target: float
    stop: float
    horizon: int


def tied(bars: pd.DataFrame, trades: pd.DataFrame, inst: Instrument,
         b: Bracket) -> pd.DataFrame:
    """The legs this bracket ties on, and the bar each one ties in.

    The single-bracket spelling of `tied_from`, exactly as `backtest.
    first_touch` is of `first_touch_from`. One convention, and it lives in the
    `_from` version -- the same shape `d78d3c1` kept when it split that pair,
    and for the same reason: a second way to decide what a tie is would be a
    second answer to what a leg is worth.
    """
    return tied_from(excursions(bars, trades, inst, horizon=b.horizon), bars, trades, b)


def tied_from(ex, bars: pd.DataFrame, trades: pd.DataFrame, b: Bracket) -> pd.DataFrame:
    """`tied`'s answer off a window already built.

    A tie is `first_touch_from`'s own `both & (hit_t == hit_s)` branch, found
    the same way that function finds it. **Not re-derived from the frame** --
    reproducing the condition by hand is how this module would end up measuring
    a different population than the one the rule is applied to.

    The window is taken as an argument for the reason `excursions` exists at
    all: it depends on `(t, side, horizon)` and not on the barriers, so a sweep
    that rebuilds it per bracket does the same work 48 times.

    Returns one row per tied leg: its index, entry, side, and the bar the two
    barriers meet in.
    """
    hit_t = _first_true(ex.up >= b.target)
    hit_s = _first_true(ex.dn <= -b.stop)
    tie = (hit_t >= 0) & (hit_s >= 0) & (hit_t == hit_s) & ex.valid

    cols = ["leg", "t", "entry", "side", "bar"]
    if not tie.any():
        return pd.DataFrame(columns=cols)

    # `excursions` slices bars strictly after entry, so column j is the bar at
    # position `pos + 1 + j`. Recomputed here rather than returned by that
    # function, whose shape is Varad's and is not being changed for this.
    pos = bars.index.searchsorted(pd.DatetimeIndex(trades["t"]))
    bar_pos = pos[tie] + 1 + hit_t[tie]
    return pd.DataFrame({
        "leg": ex.legs[tie],
        "t": trades["t"].to_numpy()[tie],
        "entry": trades["entry"].to_numpy()[tie],
        "side": trades["side"].to_numpy()[tie],
        "bar": bars.index[bar_pos],
    })


def resolve(ticks: pd.DataFrame, tie: pd.DataFrame, inst: Instrument, b: Bracket,
            *, bar: pd.Timedelta = BAR) -> pd.DataFrame:
    """Walk the tape inside each tied bar. Which price level printed first.

    The barriers are the same two numbers `first_touch_from` compares against,
    turned back into prices the way `excursions` turned prices into them:
    `side * (price - entry) / tick`, so a long and a short read identically and
    nothing here needs to know which it is looking at.

    **A print AT the barrier counts as touching it**, matching `>= target` and
    `<= -stop` in `first_touch_from`. The bar said both were reached; this is
    only asking in which order, so a different threshold here would resolve
    ties the bar never had.

    Adds `gap_ns`: how far apart the two touches were. A tie decided by a
    handful of microseconds is a different kind of fact from one decided by
    two minutes, and the write-up needs to be able to tell them apart.
    """
    if tie.empty:
        return tie.assign(first=pd.Series(dtype="int64"), gap_ns=pd.Series(dtype="float64"))

    t = pd.DatetimeIndex(ticks["timestamp"])
    price = ticks["price"].to_numpy(dtype="float64")
    # Columns rather than `itertuples`: the tuple's fields are untyped, and the
    # arithmetic below is the whole point of the module.
    at = pd.DatetimeIndex(tie["bar"])
    entry = tie["entry"].to_numpy(dtype="float64")
    side = tie["side"].to_numpy(dtype="int64")
    out: list[int] = []
    gaps: list[float] = []

    for k in range(len(tie)):
        lo, hi = t.searchsorted(at[k]), t.searchsorted(at[k] + bar)
        # In the trade's own favour, exactly as `excursions` signs it.
        moved = side[k] * (price[lo:hi] - entry[k]) / inst.tick
        i_t = _first(moved >= b.target)
        i_s = _first(moved <= -b.stop)

        if i_t < 0 or i_s < 0:
            # The bar clears a barrier its own trades never print at. Real and
            # expected: a bar's extreme can come from a print the window's
            # edges exclude, and it is reported rather than smoothed into one
            # of the two answers.
            out.append(UNRESOLVED)
            gaps.append(np.nan)
            continue

        stamps = t[lo:hi]
        gaps.append(float(abs(stamps[i_t].value - stamps[i_s].value)))
        if stamps[i_t] < stamps[i_s]:
            out.append(TARGET_FIRST)
        elif stamps[i_s] < stamps[i_t]:
            out.append(STOP_FIRST)
        else:
            # Two prints, one nanosecond. The tape is in the bar's position and
            # this module will not do what it exists to stop being done.
            out.append(UNRESOLVED)

    return tie.assign(first=out, gap_ns=gaps)


def summarize(resolved: pd.DataFrame, b: Bracket, *, n: int) -> dict[str, float]:
    """One bracket's line: how often the tie mattered, and which way it fell.

    `p_target` and `p_target_max` are the bounds `first_touch_from` produces by
    rule; `p_target_replay` is what the tape says, and it is only defined for
    the ties the tape could order. **`unresolved` legs stay at the lower bound**
    rather than being dropped or split -- dropping them would quietly select the
    legs the tape happened to be able to answer.
    """
    ties = len(resolved)
    won = int((resolved["first"] == TARGET_FIRST).sum()) if ties else 0
    unresolved = int((resolved["first"] == UNRESOLVED).sum()) if ties else 0
    return {
        # TICKS, and named so. `Bracket` carries the barriers already scaled by
        # the cell's ATR, and calling them `target_atr` here would collide with
        # the multiple the caller groups by -- two quantities one word apart,
        # which is ARCHITECTURE §4.6's error inside the file reporting it.
        "target_ticks": b.target, "stop_ticks": b.stop, "horizon": b.horizon,
        "n": n, "ties": ties, "tie_rate": ties / n if n else np.nan,
        "target_first": won,
        "stop_first": ties - won - unresolved,
        "unresolved": unresolved,
        "gap_ns_median": float(resolved["gap_ns"].median()) if ties else np.nan,
    }


def cell_atr_ticks(sub: pd.DataFrame, inst: Instrument) -> float:
    """One cell's own scale, in ticks. **`m1_sweep.month_counts`' line, mirrored.**

    Not imported, because there it is an inline expression rather than a
    function, and this module may not reshape a file in the other lane to reach
    it. Mirrored code is the thing this repo has twice paid for -- so
    `test_cell_scale_matches_m1_sweep` asserts the two agree on real cells, the
    same way `reach_table.json` got a test instead of a promise.

    Median rather than mean because bucket edges are quantiles and the tails
    inside a bucket are long.
    """
    return float((sub["atr_bp"].median() / 1e4) * sub["close"].median() / inst.tick)


def _first_true(hit: np.ndarray) -> np.ndarray:
    """Column of each row's first True, or -1. `backtest._first_true`'s rule,
    spelled again rather than imported: that one is private to a module this
    file is forbidden to change, and reaching into it would couple them."""
    any_hit = hit.any(axis=1)
    return np.where(any_hit, hit.argmax(axis=1), -1)


def _first(hit: np.ndarray) -> int:
    """Index of the first True in a 1-D mask, or -1."""
    return int(hit.argmax()) if hit.any() else -1


def month_ties(path: Path, inst: Instrument = GC) -> pd.DataFrame:
    """Every cell x bracket in one month, with its ties resolved off the tape.

    Cells are `m1_sweep.month_counts`' cells, formed the same way and scaled by
    the same `atr_ticks` -- see `cell_atr_ticks`. The window is built three
    times per cell rather than 144, because `excursions` depends on the horizon
    and not on the barriers.
    """
    import m1_sweep
    from backtest import evaluate
    from features.portable import ATR_BP_EDGES, atr_bp, session_phase
    from m2_magnitude import vol_state
    from strategies import m1_geometry

    ticks = load_ticks(path)
    bars = m1_sweep.gc_bars(path, "5min")
    rows = []

    for side in (1, -1):
        legs = evaluate(bars, m1_geometry(bars, inst, side=side), inst,
                        horizons=m1_sweep.HORIZONS)
        if legs.empty:
            continue
        at = pd.DatetimeIndex(legs["t"])
        legs["atr_bp"] = atr_bp(bars, inst, window="60min", min_bars=6).reindex(at).to_numpy()
        legs["close"] = bars["close"].reindex(at).to_numpy()
        legs["phase"] = session_phase(bars, inst).reindex(at).to_numpy()
        legs["vol_state"] = vol_state(bars).reindex(at).to_numpy()
        legs["bucket"] = pd.cut(legs["atr_bp"].to_numpy(), list(ATR_BP_EDGES)).astype("object")
        sized = legs.dropna(subset=["bucket", "phase", "vol_state", "atr_bp", "close"])

        for key, sub in sized.groupby(["bucket", "phase", "vol_state"], observed=True):
            atr_ticks = cell_atr_ticks(sub, inst)
            win = {hz: excursions(bars, sub, inst, horizon=hz) for hz in m1_sweep.HORIZONS}
            for tgt_a, stp_a, hz in m1_sweep.GRID:
                b = Bracket(tgt_a * atr_ticks, stp_a * atr_ticks, hz)
                got = resolve(ticks, tied_from(win[hz], bars, sub, b), inst, b)
                rows.append({
                    "bucket": str(key[0]), "phase": str(key[1]), "vol_state": str(key[2]),
                    "side": side, "target_atr": tgt_a, "stop_atr": stp_a,
                    **summarize(got, b, n=int(win[hz].valid.sum())),
                })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# M4b -- the path-ordering measurement. precommit §11, committed before this
# code existed.
# --------------------------------------------------------------------------

MFE_FIRST = 1
MAE_FIRST = -1


def path_bars(ex) -> pd.DataFrame:
    """Per leg: which bar holds the MFE, which holds the MAE, and whether the
    bars can order them at all.

    **This is about ORDER, not magnitude, and the distinction is the whole
    reason the measurement is narrow.** `backtest.evaluate` takes MFE from
    `leg["high"].max()`, and a bar's high IS the maximum tick price inside it,
    so bar MFE and tick MFE are the same number and no replay can improve it.
    What a bar cannot carry is WHEN inside itself the extreme happened --
    which is exactly what every PDE rule reads, since `retracement after mfe`
    and `mae in the first five bars` are both sequence claims.

    `unorderable` is the population M4b exists to size: MFE and MAE falling in
    the same bar, where bar data has no sequence to offer. It is the same shape
    as the tie in `tied_from` and is found the same way -- off `excursions`,
    not re-derived from the frame.
    """
    mfe_bar = ex.up.argmax(axis=1)
    mae_bar = ex.dn.argmin(axis=1)
    return pd.DataFrame({
        "leg": ex.legs,
        "mfe_bar": mfe_bar,
        "mae_bar": mae_bar,
        "unorderable": (mfe_bar == mae_bar) & ex.valid,
        "valid": ex.valid,
    })


def resolve_path(ticks: pd.DataFrame, unorderable: pd.DataFrame, inst: Instrument,
                 *, bar: pd.Timedelta = BAR) -> pd.DataFrame:
    """For legs whose MFE and MAE share a bar, walk the tape: which came first.

    The extremes are read in the trade's own favour, the way `excursions` signs
    them, so a long and a short are handled by the same two lines. **A print at
    the extreme counts as the extreme** -- the bar already said both happened;
    this asks only in which order, and a stricter test here would refuse legs
    the bar never doubted.

    Same refusal discipline as `resolve`: two prints in one nanosecond is
    `UNRESOLVED`, not a guess.
    """
    cols = ["first", "gap_ns"]
    if unorderable.empty:
        return unorderable.assign(**{c: pd.Series(dtype="float64") for c in cols})

    t = pd.DatetimeIndex(ticks["timestamp"])
    price = ticks["price"].to_numpy(dtype="float64")
    at = pd.DatetimeIndex(unorderable["bar"])
    entry = unorderable["entry"].to_numpy(dtype="float64")
    side = unorderable["side"].to_numpy(dtype="int64")
    out: list[int] = []
    gaps: list[float] = []

    for k in range(len(unorderable)):
        lo, hi = t.searchsorted(at[k]), t.searchsorted(at[k] + bar)
        moved = side[k] * (price[lo:hi] - entry[k]) / inst.tick
        if not len(moved):
            out.append(UNRESOLVED)
            gaps.append(np.nan)
            continue
        stamps = t[lo:hi]
        i_f = int(moved.argmax())   # the favourable extreme
        i_a = int(moved.argmin())   # the adverse one
        gaps.append(float(abs(stamps[i_f].value - stamps[i_a].value)))
        if stamps[i_f] < stamps[i_a]:
            out.append(MFE_FIRST)
        elif stamps[i_a] < stamps[i_f]:
            out.append(MAE_FIRST)
        else:
            out.append(UNRESOLVED)

    return unorderable.assign(first=out, gap_ns=gaps)


def month_path(path: Path, inst: Instrument = GC) -> pd.DataFrame:
    """One month of M4b: per leg, whether the bars can order MFE against MAE.

    **Far cheaper than the tie work, and the reason is structural.** A tie is a
    property of a BRACKET, so it needed the 72-point grid inside every cell.
    MFE and MAE are properties of the LEG and its horizon alone -- no barrier
    enters -- so `excursions` is built once per (side, horizon) over every leg
    rather than once per cell.

    The cell columns ride along unused by the headline, so the same table can
    answer "where" without a second pass over the archive.

    ⚠️ **`side` is a relabelling here, not a second observation, and both halves
    of that are asserted in the tests.** A long and a short entered on the same
    bar read the SAME two prices: the bar's high is the long's favourable
    extreme and the short's adverse one. So `unorderable` is identical across
    sides, and long `mfe_first` IS short `mae_first`, exactly. **The ordering
    carries one number -- did the high come before the low -- and pooling the
    sides forces it to 50/50**, which is the symmetric-bracket artefact of
    `REPLAY.md` §4 arriving a second time in the same module. Report it once.
    """
    import m1_sweep
    from backtest import evaluate
    from features.portable import ATR_BP_EDGES, atr_bp, session_phase
    from m2_magnitude import vol_state
    from strategies import m1_geometry

    ticks = load_ticks(path)
    bars = m1_sweep.gc_bars(path, "5min")
    rows = []

    for side in (1, -1):
        legs = evaluate(bars, m1_geometry(bars, inst, side=side), inst,
                        horizons=m1_sweep.HORIZONS)
        if legs.empty:
            continue
        at = pd.DatetimeIndex(legs["t"])
        legs["atr_bp"] = atr_bp(bars, inst, window="60min", min_bars=6).reindex(at).to_numpy()
        legs["phase"] = session_phase(bars, inst).reindex(at).to_numpy()
        legs["vol_state"] = vol_state(bars).reindex(at).to_numpy()
        legs["bucket"] = pd.cut(legs["atr_bp"].to_numpy(), list(ATR_BP_EDGES)).astype("object")
        pos = bars.index.searchsorted(at)

        for hz in m1_sweep.HORIZONS:
            ex = excursions(bars, legs, inst, horizon=hz)
            pb = path_bars(ex)
            # The shared bar, for the legs that have one. `excursions` slices
            # strictly after entry, so column j is position pos + 1 + j.
            un = pb[pb["unorderable"]].copy()
            if len(un):
                idx = un.index.to_numpy()
                un["bar"] = bars.index[pos[idx] + 1 + un["mfe_bar"].to_numpy()]
                un["entry"] = legs["entry"].to_numpy()[idx]
                un["side"] = side
                got = resolve_path(ticks, un, inst)
            else:
                got = un.assign(first=pd.Series(dtype="float64"))

            valid = int(pb["valid"].sum())
            rows.append({
                "side": side, "horizon": hz,
                "legs": valid,
                "unorderable": int(pb["unorderable"].sum()),
                "mfe_first": int((got["first"] == MFE_FIRST).sum()) if len(got) else 0,
                "mae_first": int((got["first"] == MAE_FIRST).sum()) if len(got) else 0,
                "tape_unresolved": int((got["first"] == UNRESOLVED).sum()) if len(got) else 0,
            })
    return pd.DataFrame(rows)



def _stamp() -> dict[str, object]:
    """What the cached months were produced under. `reach._stamp`'s discipline:
    a cache reused across a change to any of these pools two definitions into
    one table, and nothing downstream can see it."""
    import m1_sweep
    from features.portable import ATR_BP_EDGES
    return {
        "grid": [list(g) for g in m1_sweep.GRID],
        "edges": list(ATR_BP_EDGES),
        "bars": "5min", "atr_window": "60min", "atr_min_bars": 6,
        "bar_window": str(BAR),
    }


def _checked_cache(cache: Path) -> Path:
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
          cache: Path = Path("analysis/.replay_cache")) -> pd.DataFrame:
    """Every month, checkpointed per month so an interrupted run resumes."""
    dirs = sorted(d for d in data.iterdir() if (d / "gc_trades.parquet").exists())
    if months:
        dirs = [d for d in dirs if d.name in set(months)]
    if not dirs:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {data}")
    cache = _checked_cache(cache)

    frames, t0 = [], time.perf_counter()
    for d in dirs:
        part = cache / f"{d.name}.parquet"
        if part.exists():
            frames.append(pd.read_parquet(part))
            print(f"{d.name}  cached", flush=True)
            continue
        got = month_ties(d / "gc_trades.parquet")
        got.insert(0, "month", d.name)
        got.to_parquet(part)
        frames.append(got)
        print(f"{d.name}  {int(got['ties'].sum()):>6,} ties  "
              f"{time.perf_counter() - t0:6.0f}s", flush=True)
    return pd.concat(frames, ignore_index=True)


def build_path(data: Path, *, months: list[str] | None = None,
               cache: Path = Path("analysis/.replay_path_cache")) -> pd.DataFrame:
    """M4b over every month, checkpointed. `build`'s shape, different question."""
    dirs = sorted(d for d in data.iterdir() if (d / "gc_trades.parquet").exists())
    if months:
        dirs = [d for d in dirs if d.name in set(months)]
    if not dirs:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {data}")
    cache = _checked_cache(cache)

    frames, t0 = [], time.perf_counter()
    for d in dirs:
        part = cache / f"{d.name}.parquet"
        if part.exists():
            frames.append(pd.read_parquet(part))
            print(f"{d.name}  cached", flush=True)
            continue
        got = month_path(d / "gc_trades.parquet")
        got.insert(0, "month", d.name)
        got.to_parquet(part)
        frames.append(got)
        print(f"{d.name}  {int(got['unorderable'].sum()):>5,} unorderable of "
              f"{int(got['legs'].sum()):>7,}   {time.perf_counter() - t0:6.0f}s", flush=True)
    return pd.concat(frames, ignore_index=True)


def path_summary(t: pd.DataFrame) -> pd.DataFrame:
    """Per horizon, and per horizon only.

    **Not per side.** See `month_path` -- the two sides are the same two prices
    with the labels swapped, so a per-side table would report one measurement
    twice and a pooled ordering would be forced to 50/50. `high_first` is taken
    from the long leg's `mfe_first`, which IS the bar's high coming first.
    """
    long = t[t["side"] == 1].groupby("horizon", as_index=False)[
        ["legs", "unorderable", "mfe_first", "mae_first", "tape_unresolved"]].sum()
    long = long.rename(columns={"mfe_first": "high_first", "mae_first": "low_first"})
    long["unorderable_rate"] = long["unorderable"] / long["legs"]
    ordered = (long["high_first"] + long["low_first"]).replace(0, np.nan)
    long["high_first_share"] = long["high_first"] / ordered
    return long


def by_bracket(t: pd.DataFrame) -> pd.DataFrame:
    """Cells and months summed away. The question is per BRACKET: how often did
    the tie matter, and which way did the tape send it."""
    by = t.groupby(["target_atr", "stop_atr", "horizon"], as_index=False)[
        ["n", "ties", "target_first", "stop_first", "unresolved"]].sum()
    by["tie_rate"] = by["ties"] / by["n"]
    ordered = (by["ties"] - by["unresolved"]).replace(0, np.nan)
    by["target_share"] = by["target_first"] / ordered
    return by.sort_values(["horizon", "target_atr", "stop_atr"]).reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--what", choices=("ties", "path"), default="ties",
                   help="ties = step 5's tie resolution; path = M4b's MFE/MAE ordering")
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--months", nargs="+", help="default: every month on disk")
    p.add_argument("--out", type=Path, default=Path("analysis/replay_ties.csv"))
    p.add_argument("--cache", type=Path, default=Path("analysis/.replay_cache"),
                   help="per-month rows, so an interrupted build resumes")
    a = p.parse_args()

    a.out.parent.mkdir(parents=True, exist_ok=True)

    if a.what == "path":
        t = build_path(a.data, months=a.months)
        out = a.out if a.out != Path("analysis/replay_ties.csv") else Path("analysis/replay_path.csv")
        t.to_csv(out, index=False)
        by = path_summary(t)
        print(f"\n{by.to_string(index=False)}\n\nwritten to {out}")
        legs, un = int(by["legs"].sum()), int(by["unorderable"].sum())
        print(f"\n=== {un:,} of {legs:,} legs have MFE and MAE in the same bar "
              f"-- {un / legs:.2%}; precommit §11 predicted under 10% ===")
        print("`side` is a relabelling, not a second observation -- see month_path.")
        return

    t = build(a.data, months=a.months, cache=a.cache)
    t.to_csv(a.out, index=False)

    by = by_bracket(t)
    print(f"\n{by.to_string(index=False)}")
    ties, unres = int(by["ties"].sum()), int(by["unresolved"].sum())
    won = int(by["target_first"].sum())
    print(f"\nwritten to {a.out}")
    print(f"\n=== {ties:,} ties over {int(by['n'].sum()):,} leg-brackets; "
          f"{ties - unres:,} ordered by the tape, {unres:,} it could not ===")
    if ties - unres:
        print(f"the rule sends every one to the stop. The tape sends {won:,} "
              f"({won / (ties - unres):.1%}) to the target.")


if __name__ == "__main__":
    main()
