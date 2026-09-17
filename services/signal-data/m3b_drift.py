"""M3b -- is there a time-of-day drift at all?  `strategy-precommit.md` §12.

`M3_CLOCK.md` §6 logged a pattern it explicitly refused to claim: `London-NY`
runs -0.018 long / +0.035 short and `Asia-London` +0.036 long / -0.031 short --
large, opposite, growing with a wider stop, over a period gold rose 84%. Its own
words: *"M3 is non-directional and its null controls for side but not for
time-of-day drift. It needs its own experiment and its own null."* This is that
experiment, and §12 committed its prediction before this file existed.

TWO DESIGN CHOICES ARE THE WHOLE EXPERIMENT.

**Returns, not brackets.** M3's numbers reached us through a bracket, and a
bracket confounds direction with volatility -- the `atr_bp` quiet-hour artefact
`M1_SURFACE.md` §3, `M3_CLOCK.md` §2 and `REACH.md` have each found
independently. Asking a drift question through a bracket asks a bracket question
again, so this file never builds one. No `evaluate`, no `first_touch`, no
barriers -- plain forward log-returns in bp.

**Disjoint windows, and the elapsed-time check that makes them real.**
Overlapping forward returns share bars and are autocorrelated by construction;
pooling them would inflate n about sixfold and manufacture significance. Windows
here step by the full horizon. AND `resample_bars` DROPS EMPTY BARS, so bar N+6
is not necessarily 30 minutes after bar N -- `s1.minute_bars`' standing rule, the
same one `backtest.py` slices the index for. A window whose ends are not exactly
one horizon apart spans a weekend or a session break and is dropped rather than
counted as a 30-minute return.

THE NULL IS THE POINT. M3's null pooled over phases, so a drift shared by all of
them was invisible to it. Subtracting the POOLED mean is what separates a phase
claim from a period claim, and it is the thing M3 said it did not have.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from features.portable import PHASES, session_phase
from instruments import GC, Instrument
from m1_sweep import COST_TICKS, gc_bars

HORIZON_BARS = 6        # 30 minutes at 5-min bars -- M3's own horizon
BAR = "5min"


def windows(bars: pd.DataFrame, inst: Instrument, *,
            horizon_bars: int = HORIZON_BARS, bar: str = BAR) -> pd.DataFrame:
    """Disjoint forward returns in bp, labelled by the phase each one STARTS in.

    Stepping by `horizon_bars` is what makes them disjoint. The `whole` filter
    is what makes them thirty MINUTES rather than six BARS -- see the module
    docstring; a dropped-bar gap would otherwise be priced as a quiet half hour.
    """
    close = bars["close"].to_numpy()
    t = bars.index.to_series()
    w = pd.DataFrame(
        {
            "phase": session_phase(bars, inst).to_numpy(),
            # roll wraps the last `horizon_bars` rows, but `whole` is already
            # False there -- shift(-n) yields NaT and NaT == Timedelta is False.
            "ret_bp": np.log(np.roll(close, -horizon_bars) / close) * 1e4,
            "cost_bp": (COST_TICKS * inst.tick / close) * 1e4,
            "whole": (t.shift(-horizon_bars) - t).to_numpy()
            == pd.Timedelta(bar) * horizon_bars,
        },
        index=bars.index,
    )
    return w[w["whole"]].iloc[::horizon_bars].drop(columns="whole").dropna()


def drift(w: pd.DataFrame) -> pd.DataFrame:
    """§12's statistic: each phase's mean MINUS the pooled mean, net of cost.

    `edge_lo` is the residual's two-sigma LOWER bound, which is `m1_sweep`'s
    `ev_lo` convention -- a cell is credited with what it can defend, not with
    its point estimate. A phase clears only if that bound exceeds its own cost.

    The standard error treats the pooled mean as known, which is slightly
    CONSERVATIVE (it ignores that estimate's own variance). Conservative is the
    right direction for a kill condition, and it is stated rather than hidden.
    """
    pooled = w["ret_bp"].mean()
    g = w.assign(resid=w["ret_bp"] - pooled).groupby("phase")
    out = pd.DataFrame({
        "n": g.size(),
        "mean_bp": g["ret_bp"].mean(),
        "resid_bp": g["resid"].mean(),
        "se_bp": g["resid"].std(ddof=1) / np.sqrt(g.size()),
        "cost_bp": g["cost_bp"].median(),
    })
    out["t"] = out["resid_bp"] / out["se_bp"]
    out["edge_lo"] = out["resid_bp"].abs() - 2 * out["se_bp"]
    out["clears"] = out["edge_lo"] > out["cost_bp"]
    out.attrs["pooled_bp"] = pooled
    return out.reindex(list(PHASES))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("analysis/m3b_drift.csv"))
    a = p.parse_args()

    months = sorted(d for d in a.data.iterdir() if (d / "gc_trades.parquet").exists())
    if not months:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {a.data}")

    frames = []
    for m in months:
        w = windows(gc_bars(m / "gc_trades.parquet", BAR), GC)
        frames.append(w)
        print(f"{m.name}  {len(w):5d} disjoint {HORIZON_BARS*5}m windows", flush=True)

    w = pd.concat(frames, ignore_index=True)
    t = drift(w)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out)

    pooled = t.attrs["pooled_bp"]
    print(f"\n=== {len(w):,} disjoint windows, {len(months)} months ===")
    print(f"POOLED drift {pooled:+.4f} bp per {HORIZON_BARS*5}m window "
          f"-- the bull market every phase inherits")
    print(f"cost floor   {w['cost_bp'].median():.4f} bp round trip\n")
    with pd.option_context("display.width", 200):
        print(t.round(4).to_string())
    print(f"\nphases clearing cost on the residual: {int(t['clears'].sum())} of {len(t)}")
    print(f"written to {a.out}")


if __name__ == "__main__":
    main()
