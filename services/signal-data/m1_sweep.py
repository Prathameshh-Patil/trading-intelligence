"""M1, the geometry frontier: what bracket has positive EV, per bucket and phase.

Step 2 of `docs/strategy/ARCHITECTURE.md` §6, the vol lane of
`plans/team/strategy-split.md`. **Every number this file takes as input was
committed before it ran** -- `plans/team/strategy-precommit.md` §1 (the grid,
the cost floor, the pass line), §2 (`ATR_BP_EDGES`), §3 (`MIN_SAMPLES`), and
Prathamesh's §4 (the phase boundaries). Nothing here chooses anything.

WHAT IS MEASURED. Enter EVERY bar on one side, draw a target `t x ATR` above
and a stop `s x ATR` below, and ask which came first inside `h` minutes. There
is no entry rule and that is deliberate: M1 asks what geometry the tape
supports, which is a property of the tape rather than of a signal. The answer
is the corrected null every later lift in this track is quoted against.

THREE THINGS THAT ARE EASY TO GET WRONG AND ARE NOT GOT WRONG HERE.

  * **A leg that touched neither barrier is not a leg that made nothing.** It
    is marked at its realized move at the horizon. Scoring those at 0 charges
    the strategy for every stop and credits it for no part of the tape it
    actually held. `m3_profile.py` states this first; it is the same rule.
  * **Same-bar ties are reported as a BAND, never a midpoint.** `first_touch`
    resolves a tie to the stop, so `p_target` is a lower bound; `ties="target"`
    is the same measurement at the other extreme. The band is not decoration
    at this grid: Prathamesh measured **20.45% of bars wide enough to tie at
    0.75x/0.5x** against 0.13% at 3.0x/1.0x (`M3_CLOCK.md` §3.2). At the tight
    corner the band IS the uncertainty, and a cell whose two ends disagree
    about profitability is **undecided**, not a finding.
  * **Counts are pooled across the archive; the rate is computed once, at the
    end.** Months differ in bucket mix by 25x -- 2025-08 puts 69% of its bars
    in `<7 bp` and 2026-03 puts 66% in `14+` -- so a mean of monthly rates
    weights a 19-leg cell like a 13,000-leg one. `base_rates.py`'s rule.

WHY THE BRACKET IS SCALAR PER CELL. `backtest.first_touch` takes one target and
one stop, not a per-bar pair, so each `(month x bucket x phase)` cell is sized
off its own median `atr_bp` and median close. That is `m3_profile.py`'s
convention and it is kept rather than re-invented -- a second sizing rule is
how two files start disagreeing about what "1x ATR" means.

    PYTHONPATH=. uv run python m1_sweep.py                     # both sides, 19 months
    PYTHONPATH=. uv run python m1_sweep.py --months 2026-07    # one month, quick
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence
from itertools import product
from pathlib import Path

import pandas as pd

from backtest import evaluate, excursions, first_touch_from
from features.portable import ATR_BP_EDGES, atr_bp, session_phase
from horizon import mde_rate
from instruments import GC, Instrument

# `vol_state` lives with SLOPE_MIN, the threshold that defines it, rather than
# being re-cut here. It is not in features/portable.py because that file's
# function list is frozen by strategy-split.md §4 and adding a name to it needs
# standup, not a unilateral import convenience.
from m2_magnitude import vol_state
from regimes import resample_bars
from s1 import load_ticks, minute_bars
from strategies import m1_geometry

# strategy-precommit.md §1, committed 2026-09-06 before this file existed.
TARGETS = (0.75, 1.0, 1.5, 2.0, 3.0, 4.0)   # x the cell's ATR
STOPS = (0.5, 0.75, 1.0, 1.5)               # x the cell's ATR
HORIZONS = (15, 30, 60)                     # minutes
GRID = tuple(product(TARGETS, STOPS, HORIZONS))

# The round trip an edge has to clear before it is worth having: one tick of
# spread/slippage ($10) plus ~$4 commission. `horizon.py --cost-ticks`'s default,
# stated rather than buried. Converted to ATR units per cell, because 1.4 ticks
# is a different fraction of the move in a quiet month than in a loud one.
COST_TICKS = 1.4

# strategy-precommit.md §3. Below this a cell cannot separate the archive null
# (0.1644) from the highest per-bucket breakeven in it (0.224), so it reports
# nothing rather than a wide something. NOT backtest.MIN_SAMPLES, which is 30
# and is Track A's reporting flag -- a different object, on purpose.
MIN_SAMPLES = 400

# The conditioning axis is a parameter because precommit §9 asks the same
# sweep the same question against `vol_state` instead of `phase`. One sweep and
# one EV convention, rather than a second driver that could quietly disagree
# with this one about what a leg is worth.
AXES = ("phase", "vol_state")
GEOMETRY = ["target_atr", "stop_atr", "horizon"]


def keys(axes: Sequence[str]) -> list[str]:
    return ["bucket", *axes, "side", *GEOMETRY]


def gc_bars(path: Path, bar_size: str) -> pd.DataFrame:
    """One month of Databento GC trades -> the bar frame. The flow path.

    Separate from `month_counts` because loading a month and counting a grid
    are different jobs, and a second instrument shares only the second. Spot
    arrives through `spot.minute_bars` instead -- no `delta`, no `volume`, no
    `cvd`, because it has none.
    """
    return resample_bars(minute_bars(load_ticks(path)), bar_size)


def month_counts(bars: pd.DataFrame, inst: Instrument, *, side: int, atr_window: str,
                 atr_min_bars: int, edges: tuple[float, ...],
                 axes: Sequence[str] = ("phase",)) -> pd.DataFrame:
    """Counts, never rates, for one frame and one side. Every grid point.

    **Takes bars rather than a path, and an instrument rather than assuming
    one.** `GC` was hardcoded here in six places; step 1 injected `TICK`
    through the repo but this file still reached for the instrument itself,
    which is the same class of assumption one level up. The counts are
    tick-free either way -- measured, see `instruments.py` -- but `cost_atr`
    is not, and a borrowed cost floor is how a spot surface would quietly be
    scored against gold's commission.
    """
    trades = evaluate(bars, m1_geometry(bars, inst, side=side), inst, horizons=HORIZONS)
    if trades.empty:
        return pd.DataFrame(columns=[*keys(axes), "n", "target", "stop", "target_max",
                                     "stop_min", "open_pnl", "cost_atr"])

    at = pd.DatetimeIndex(trades["t"])
    trades["atr_bp"] = atr_bp(bars, inst, window=atr_window, min_bars=atr_min_bars).reindex(at).to_numpy()
    trades["close"] = bars["close"].reindex(at).to_numpy()
    for name in axes:
        trades[name] = (
            session_phase(bars, inst) if name == "phase" else vol_state(bars)
        ).reindex(at).to_numpy()
    trades["bucket"] = pd.cut(trades["atr_bp"].to_numpy(), list(edges)).astype("object")
    sized = trades.dropna(subset=["bucket", *axes, "atr_bp", "close"])

    rows = []
    for key, sub in sized.groupby(["bucket", *axes], observed=True):
        bucket, cell = key[0], key[1:]
        # The cell's own scale. Median rather than mean: bucket edges are
        # quantiles and the tails inside a bucket are long.
        atr_ticks = (sub["atr_bp"].median() / 1e4) * sub["close"].median() / inst.tick
        cost_atr = COST_TICKS / atr_ticks
        # The window a leg is judged over depends on the horizon and not on the
        # barriers, so it is built three times here rather than 144.
        win = {hz: excursions(bars, sub, inst, horizon=hz) for hz in HORIZONS}
        for tgt_a, stp_a, hz in GRID:
            tgt, stp = tgt_a * atr_ticks, stp_a * atr_ticks
            out = first_touch_from(win[hz], target=tgt, stop=stp)
            best = first_touch_from(win[hz], target=tgt, stop=stp, ties="target")
            n = int(out.notna().sum())
            if not n:
                continue
            # Legs that touched neither barrier are marked at what they were
            # actually worth, in ATR units so the archive can be pooled.
            open_pnl = float((sub[f"move_{hz}m"] / atr_ticks).where(out == 0, 0.0).sum())
            rows.append({
                "bucket": str(bucket), **dict(zip(axes, map(str, cell), strict=True)),
                "side": side,
                "target_atr": tgt_a, "stop_atr": stp_a, "horizon": hz,
                "n": n,
                "target": int((out == 1).sum()), "stop": int((out == -1).sum()),
                "target_max": int((best == 1).sum()), "stop_min": int((best == -1).sum()),
                "open_pnl": open_pnl, "cost_atr": n * cost_atr,
            })
    return pd.DataFrame(rows)


def _ev(t: pd.DataFrame) -> pd.Series:
    """EV per leg in ATR units, net of cost. One definition, used twice."""
    return (t["target_atr"] * t["target"] - t["stop_atr"] * t["stop"]
            + t["open_pnl"] - t["cost_atr"]) / t["n"]


def surface(counts: pd.DataFrame, axes: Sequence[str] = ("phase",)) -> pd.DataFrame:
    """Pooled counts -> rates, EV, the tie band, the null and the pass line."""
    t = counts.groupby(keys(axes), as_index=False).sum()

    t["p_target"] = t["target"] / t["n"]
    t["p_target_max"] = t["target_max"] / t["n"]
    t["p_stop"] = t["stop"] / t["n"]
    t["p_neither"] = 1 - t["p_target"] - t["p_stop"]

    # EV per leg in ATR units, split into the two things it is made of.
    # `ev_barrier` is REALIZED -- a leg that reached a barrier is a closed
    # trade. `ev_open` is MARK-TO-MARKET on legs still open at the horizon,
    # and it is not the same kind of number: the surviving set is selected
    # (a leg that never touched the tight stop is biased toward the target),
    # so `ev_open` is structurally positive on BOTH sides. Reporting the split
    # is what stops a cell whose EV is all mark-to-market being read as a
    # cell that made money.
    t["ev_barrier"] = (t["target_atr"] * t["target"] - t["stop_atr"] * t["stop"]) / t["n"]
    t["ev_open"] = t["open_pnl"] / t["n"]
    # `ev_lo` reads same-bar ties to the stop and `ev_hi` to the target; the
    # truth is inside and no bar frame can say where.
    cost = t["cost_atr"] / t["n"]
    ev_hi = (t["target_atr"] * t["target_max"] - t["stop_atr"] * t["stop_min"] + t["open_pnl"]) / t["n"]
    t["ev_lo"], t["ev_hi"], t["cost"] = _ev(t), ev_hi - cost, cost

    # The null is this cell's own geometry and side, pooled over PHASES. That
    # is what makes a phase's lift a statement about the clock rather than
    # about the bracket, and it is the mix-matched null §5 of ARCHITECTURE asks
    # every lift to carry.
    by = ["bucket", "side", *GEOMETRY]
    null = t.groupby(by, as_index=False)[
        ["n", "target", "stop", "open_pnl", "cost_atr"]
    ].sum()
    null["p_null"] = null["target"] / null["n"]
    # The SAME cell with the axis pooled out -- i.e. the unconditioned EV, on
    # the same months and the same geometry. `ev_delta` is therefore what
    # conditioning ADDED, which is the whole question precommit §9 asks. A cell
    # can clear the pass line with ev_delta ~ 0, meaning the bucket was already
    # there and the axis contributed nothing.
    null["ev_null"] = _ev(null)
    t = t.merge(null[[*by, "p_null", "ev_null"]], on=by, how="left")
    t["ev_delta"] = t["ev_lo"] - t["ev_null"]
    t["lift"] = t["p_target"] - t["p_null"]
    t["mde"] = [mde_rate(p, n) for p, n in zip(t["p_null"], t["n"], strict=True)]

    # strategy-precommit.md §1's pass line, all three required.
    t["thin"] = t["n"] < MIN_SAMPLES
    t["beats_mde"] = t["p_target"] > t["mde"]
    t["passes"] = ~t["thin"] & (t["ev_lo"] > 0) & t["beats_mde"]
    # A cell profitable on one tie convention and not the other is not a
    # finding. At 0.75x/0.5x one bar in five is wide enough to tie.
    t["undecided"] = ~t["thin"] & (t["ev_lo"] <= 0) & (t["ev_hi"] > 0)

    # THE SIDE MIRROR. Added as a REPORTED COLUMN, not as a fourth condition --
    # the pass line is strategy-precommit.md §1's and it is not moved after the
    # fact. But entering every bar on one side inherits the archive's drift,
    # and drift is not geometry: measured on 2026-07, a 1.0x/1.0x cell reads
    # +0.088 ATR long and -0.095 short. **A cell that passes while its mirror
    # fails is the month's direction wearing a bracket's clothes.** `ev_sym` is
    # the mean of the two sides, which is the only figure a non-directional
    # claim is entitled to.
    mirror = t[[*keys(axes), "ev_lo"]].copy()
    mirror["side"] *= -1
    t = t.merge(mirror.rename(columns={"ev_lo": "ev_mirror"}), on=keys(axes), how="left")
    t["ev_sym"] = (t["ev_lo"] + t["ev_mirror"]) / 2
    return t.sort_values("ev_lo", ascending=False).reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--months", nargs="+", help="YYYY-MM names; default is every month on disk")
    p.add_argument("--sides", type=int, nargs="+", default=[1, -1], choices=[1, -1])
    p.add_argument("--bar-size", default="5min")
    p.add_argument("--atr-window", default="60min")
    p.add_argument("--atr-min-bars", type=int, default=6)
    p.add_argument("--out", type=Path, default=Path("analysis/m1_surface.csv"))
    p.add_argument("--axes", nargs="+", choices=AXES, default=["phase"],
                   help="what to condition on beside the atr_bp bucket. precommit §9 runs "
                        "vol_state on the training half; both together is reach.py's key (§10); "
                        "the default reproduces M1_SURFACE.md")
    a = p.parse_args()

    months = sorted(d for d in a.data.iterdir() if (d / "gc_trades.parquet").exists())
    if a.months:
        months = [d for d in months if d.name in set(a.months)]
    if not months:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {a.data}")

    print(f"M1 sweep on ({' x '.join(a.axes)}): {len(GRID)} grid points x {len(months)} months "
          f"x {len(a.sides)} side(s)")
    print(f"grid target {TARGETS} / stop {STOPS} / horizon {HORIZONS}  (x ATR, x minutes)")
    print(f"buckets {ATR_BP_EDGES} bp   cost {COST_TICKS} ticks   MIN_SAMPLES {MIN_SAMPLES}\n")

    frames, t0 = [], time.perf_counter()
    for month in months:
        bars = gc_bars(month / "gc_trades.parquet", a.bar_size)  # once, not once per side
        for side in a.sides:
            c = month_counts(bars, GC, side=side,
                             atr_window=a.atr_window, atr_min_bars=a.atr_min_bars,
                             edges=ATR_BP_EDGES, axes=tuple(a.axes))
            frames.append(c)
            legs = int(c["n"].sum()) // len(GRID) if len(c) else 0
            print(f"{month.name} side {side:+d}  cells {len(c):4d}  legs {legs:6d}"
                  f"  {time.perf_counter() - t0:6.0f}s", flush=True)

    t = surface(pd.concat(frames, ignore_index=True), axes=tuple(a.axes))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out, index=False)

    live = t[~t["thin"]]
    print(f"\n=== {len(t)} cells, {len(live)} with n >= {MIN_SAMPLES}, "
          f"{int(t['passes'].sum())} passing all three conditions ===")
    print(f"written to {a.out}\n")

    cols = ["bucket", *a.axes, "side", "target_atr", "stop_atr", "horizon", "n",
            "p_target", "p_neither", "p_null", "mde", "ev_barrier", "ev_open",
            "ev_lo", "ev_null", "ev_delta", "ev_sym", "passes"]
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print("TOP 15 BY EV NET OF COST (lower tie bound):")
        print(live[cols].head(15).round(4).to_string(index=False))
        if int(t["passes"].sum()):
            print("\nCELLS CLEARING ALL THREE:")
            print(t[t["passes"]][cols].round(4).to_string(index=False))
        else:
            print("\nNO CELL CLEARS ALL THREE. That is the kill condition in "
                  "strategy-split.md §2, fired on data already paid for.")
        print(f"\nundecided by the tie band (ev_lo <= 0 < ev_hi): {int(t['undecided'].sum())} cells")
        print(f"ev_delta -- what conditioning on {'/'.join(a.axes)} ADDED, against the same cell with it "
              f"pooled out:\n  mean {t['ev_delta'].mean():+.4f}   median {t['ev_delta'].median():+.4f}"
              f"   > +0.042 (M1's cost) in {int((t['ev_delta'] > 0.0423).sum())} of {len(t)} cells")
        mirrored = t[t["passes"] & (t["ev_sym"] > 0)]
        print(f"of the {int(t['passes'].sum())} passing cells, {len(mirrored)} also have "
              f"ev_sym > 0 -- the rest are the archive's drift, not geometry")
        print(f"mean ev_open share of |ev| on cells with n >= {MIN_SAMPLES}: "
              f"{(live['ev_open'].abs() / (live['ev_barrier'].abs() + live['ev_open'].abs())).mean():.1%}"
              "  (mark-to-market on legs still open at the horizon, not realized)")


if __name__ == "__main__":
    main()
