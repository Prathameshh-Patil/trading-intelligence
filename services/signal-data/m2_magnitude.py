"""M2, vol momentum: does an EXPANDING vol state predict how far price travels?

Step 4 of `docs/strategy/ARCHITECTURE.md` §6, the vol lane of
`plans/team/strategy-split.md`. **Every threshold is imported from
`plans/team/strategy-precommit.md` §8, committed 2026-09-07 before this file
existed and before anything read a forward move.** Nothing here chooses
anything.

WHAT IS MEASURED. `P(|move| >= T x ATR within H minutes)`, per
`(atr_bp bucket x vol_state)`, against the **ATR-matched null** -- the same
bucket with `vol_state` pooled out. `vol_state` is `rv_slope` cut at +/-0.20:
EXPANDING, STABLE, CONTRACTING.

FOUR THINGS THIS FILE DOES DIFFERENTLY FROM `m1_sweep.py`, EACH FOR A REASON.

  * **One side.** A long and a short entered on the same bar have the same
    `|move|` by construction, so a magnitude claim has no side and a
    side-matched null would measure the same legs twice.
  * **Per-BAR ATR normalisation, not a scalar per cell.** `m1_sweep` sizes a
    scalar bracket per cell because `backtest.first_touch` takes scalars. A
    magnitude threshold takes no such argument, so each leg is divided by its
    own bar's ATR and the cell approximation is not needed. Exact, and stated
    because the two files would otherwise look inconsistent.
  * **No EV, and no cost.** M2's output is not a trade -- there is no bracket
    and no round trip to clear. Prathamesh's correction (a kill condition is
    stated in EV net of cost) is right for M1 and M3 and does not reach here.
    **What it costs is that a real M2 result is a FORECASTING result**: the
    moment it becomes a bracket it meets M1's surface, where gross EV is
    -0.0032 ATR against a cost of +0.0423.
  * **Training half only** -- 2025-01..09, `SPLIT` per precommit §6. Step 4
    selects, so unlike M1 and M3 it spends out-of-sample data.

The direction columns are the check that makes the claim honest. If EXPANDING
raises `P(move >= +T)` and `P(move <= -T)` together, that is scale and it is
consistent with `horizon.py`'s random walk. If it raises one and not the
other, it is a directional claim wearing a magnitude claim's clothes.

    PYTHONPATH=. uv run python m2_magnitude.py
"""

from __future__ import annotations

import argparse
import time
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import evaluate
from features.portable import ATR_BP_EDGES, atr_bp, rv_slope
from horizon import mde_rate
from instruments import GC
from regimes import resample_bars
from s1 import load_ticks, minute_bars

# strategy-precommit.md §8, committed before this file existed.
WINDOW, MIN_BARS = "60min", 6      # atr_bp's window, not a second one
SLOPE_MIN = 0.20                   # symmetric; EXPANDING >= +0.20, CONTRACTING <= -0.20
TARGETS = (1.0, 1.5, 2.0)          # x the bar's own atr_bp; three of M1's committed six
HORIZONS = (15, 30, 60)            # M1's horizons exactly
MIN_SAMPLES = 400                  # precommit §3

# precommit §6's committed SPLIT. Frozen as a constant and not a flag, for the
# reason m3_profile.py froze its own: a split that can be passed at the prompt
# is a split that can be tried twice.
TRAIN = tuple(f"2025-{m:02d}" for m in range(1, 10))

STATES = ("CONTRACTING", "STABLE", "EXPANDING")
KEYS = ["bucket", "vol_state", "target_atr", "horizon"]


def vol_state(bars: pd.DataFrame) -> pd.Series:
    """`rv_slope` cut at +/-SLOPE_MIN. Three states, categorical, all present.

    Categorical with every state declared so a bucket table has a row for a
    state a month never visited. A state absent from the index is a hole
    nobody sees; a state present with n=0 is a fact.
    """
    s = rv_slope(bars, window=WINDOW, min_bars=MIN_BARS)
    state = pd.Series(pd.NA, index=bars.index, dtype="object")
    state[s <= -SLOPE_MIN] = "CONTRACTING"
    state[(s > -SLOPE_MIN) & (s < SLOPE_MIN)] = "STABLE"
    state[s >= SLOPE_MIN] = "EXPANDING"
    # A bar with no slope yet keeps pd.NA and is dropped rather than filed
    # under STABLE, which would put the opening of every session -- where the
    # window is not full -- into the middle state by default.
    return pd.Series(pd.Categorical(state, categories=STATES), index=bars.index)


def month_counts(path: Path) -> pd.DataFrame:
    """Counts, never rates, for one month. Every (bucket x state x T x H)."""
    bars = resample_bars(minute_bars(load_ticks(path)), "5min")
    trades = evaluate(bars, pd.Series(1, index=bars.index), GC, horizons=HORIZONS)
    at = pd.DatetimeIndex(trades["t"])

    bp = atr_bp(bars, GC, window=WINDOW, min_bars=MIN_BARS).reindex(at).to_numpy()
    close = bars["close"].reindex(at).to_numpy()
    trades["bucket"] = pd.cut(bp, list(ATR_BP_EDGES)).astype(str)
    trades["vol_state"] = vol_state(bars).reindex(at).to_numpy()
    # Each leg divided by ITS OWN bar's ATR. No cell-level approximation is
    # needed here because no scalar bracket is being passed to first_touch.
    atr_ticks = (bp / 1e4) * close / GC.tick

    rows = []
    keep = trades.dropna(subset=["vol_state"])
    keep = keep[np.isfinite(atr_ticks[trades.index.isin(keep.index)])]
    scale = pd.Series(atr_ticks, index=trades.index).reindex(keep.index)
    for (bucket, state), sub in keep.groupby(["bucket", "vol_state"], observed=True):
        sc = scale.reindex(sub.index)
        for t_atr, hz in product(TARGETS, HORIZONS):
            move = sub[f"move_{hz}m"] / sc
            ok = move.notna()
            n = int(ok.sum())
            if not n:
                continue
            rows.append({
                "bucket": str(bucket), "vol_state": str(state),
                "target_atr": t_atr, "horizon": hz, "n": n,
                "hit": int((move.abs() >= t_atr).sum()),
                "up": int((move >= t_atr).sum()),
                "down": int((move <= -t_atr).sum()),
            })
    return pd.DataFrame(rows)


def surface(counts: pd.DataFrame) -> pd.DataFrame:
    """Pooled counts -> rates, the ATR-matched null, lift and mde."""
    t = counts.groupby(KEYS, as_index=False).sum()
    t["p_hit"] = t["hit"] / t["n"]
    t["p_up"] = t["up"] / t["n"]
    t["p_down"] = t["down"] / t["n"]
    # The null is the same bucket, target and horizon with vol_state POOLED
    # OUT. That is what makes the lift a statement about the vol state rather
    # than about volatility, which the bucket axis already conditions on.
    by = ["bucket", "target_atr", "horizon"]
    null = t.groupby(by, as_index=False)[["n", "hit"]].sum()
    null["p_null"] = null["hit"] / null["n"]
    t = t.merge(null[[*by, "p_null"]], on=by, how="left")
    t["lift"] = t["p_hit"] - t["p_null"]
    t["mde"] = [mde_rate(p, n) for p, n in zip(t["p_null"], t["n"], strict=True)]
    t["thin"] = t["n"] < MIN_SAMPLES
    t["beats_mde"] = t["p_hit"] > t["mde"]
    t["passes"] = ~t["thin"] & t["beats_mde"]
    # The honesty check: scale raises both tails together, direction does not.
    t["dir_gap"] = (t["p_up"] - t["p_down"]).abs()
    return t.sort_values(["target_atr", "horizon", "bucket", "vol_state"]).reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("analysis/m2_magnitude.csv"))
    a = p.parse_args()

    months = [a.data / m for m in TRAIN if (a.data / m / "gc_trades.parquet").exists()]
    if len(months) != len(TRAIN):
        raise SystemExit(f"training half incomplete: found {len(months)} of {len(TRAIN)} months")

    print(f"M2: training half only, {len(months)} months ({TRAIN[0]}..{TRAIN[-1]})")
    print(f"slope_min +/-{SLOPE_MIN}  window {WINDOW}/{MIN_BARS}  T {TARGETS}  H {HORIZONS}")
    print(f"buckets {ATR_BP_EDGES} bp   MIN_SAMPLES {MIN_SAMPLES}\n")

    frames, t0 = [], time.perf_counter()
    for m in months:
        c = month_counts(m / "gc_trades.parquet")
        frames.append(c)
        print(f"{m.name}  cells {len(c):3d}  legs {int(c['n'].sum()) // (len(TARGETS)*len(HORIZONS)):6d}"
              f"  {time.perf_counter() - t0:5.0f}s", flush=True)

    t = surface(pd.concat(frames, ignore_index=True))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out, index=False)

    live = t[~t["thin"]]
    exp = live[live["vol_state"] == "EXPANDING"]
    print(f"\n=== {len(t)} cells, {len(live)} with n >= {MIN_SAMPLES} ===")
    print(f"EXPANDING cells clearing their own mde: {int(exp['passes'].sum())} of {len(exp)}")
    print(f"written to {a.out}\n")

    cols = ["bucket", "vol_state", "target_atr", "horizon", "n", "p_hit", "p_null",
            "lift", "mde", "p_up", "p_down", "dir_gap", "passes"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("P(|move| >= T) BY VOL STATE, pooled over buckets:")
        g = t.groupby(["target_atr", "horizon", "vol_state"], observed=True)[["n", "hit"]].sum()
        g["p_hit"] = (g["hit"] / g["n"]).round(4)
        print(g["p_hit"].unstack().to_string())
        print("\nEXPANDING, per bucket:")
        print(exp[cols].round(4).to_string(index=False))
    print("\ndir_gap is |P(move>=+T) - P(move<=-T)|. Small means the state moves SCALE,")
    print("which is consistent with horizon.py's random walk. Large means it is a")
    print("directional claim wearing a magnitude claim's clothes.")


if __name__ == "__main__":
    main()
