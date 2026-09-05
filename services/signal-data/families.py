"""Two engines instead of one: exhaustion and continuation, measured separately.

**Gate 1, option (c), chosen by Varad 2026-09-05.** `signals/engine.py`'s
3-of-4 checker fires 0 signals on 3,516 training bars, and the reason is not
sparsity: A and B read *exhaustion*, C and D read *continuation*, and B and D
co-fire on 26 bars while agreeing on direction on **zero** of them. A combiner
that needs three of four across two families which contradict each other is
dead before any threshold is argued about.

So this does not combine them. It runs each family as its own arm and measures
both against the archive base rate. `signals/engine.combine` already takes the
conditions and the count, so nothing new is needed to do it -- the split is a
call-site decision, not a new abstraction.

**No number in this file was authored here.** Every threshold is transcribed
from where it was committed, and the source is named beside it. The one thing
this file decides is which conditions go in which arm, which is the decision
being executed.

**The null is mix- and side-matched, and both halves of that matter.**
`analysis/BASE_RATES.md` §3 found the monthly base rate swings 5.6x almost
entirely through the ATR *mix* rather than the buckets moving -- so an arm that
fires mostly in high-ATR bars must be compared against the high-ATR rate, or
the mix does the work and reads as edge. And gold trended over the archive, so
a short's base rate is its own number: scoring a two-sided arm against a
long-only null would credit it with the drift.

Training half only (<= 2026-07-19). The held-out half is not read here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt
import signals.engine as en
from features.expansion import atr
from features.regime_filter import passes, regime_kappa
from horizon import mde_rate

# D3's committed thresholds, transcribed from daily_updates/2026-09-04.md.
# Windows are borrowed, not invented: B and C run on `cvd_divergence`'s Part B
# window, D's ATR is Part D's, and D's two ratios are planfortoday.md's.
BC = {"window": "60min", "min_bars": 6}
RANGE = {"atr_window": "70min", "atr_min_bars": 14, "mult": 1.5, "body_min": 0.60}

# Part D's filter block, from thresholds_selector.md via the same entry.
FILTER = {
    "kappa_min": 0.75,
    "persistence_window": "60min",
    "persistence_min_bars": 6,
    "persistence_min": 0.40,
    "atr_window": "70min",
    "atr_min_bars": 14,
    "atr_min": 40.0,
    "ema_span": 15,
    "edge_minutes": 5,
}

EDGES = [0, 30, 40, 50, 1e9]  # matching analysis/BASE_RATES.md

# Kappa is measured one bar ahead, which is what daily_updates/2026-09-04.md
# recorded: P(stay) 0.866 / 0.875 / 0.927 against shares 15.4 / 21.5 / 63.0,
# giving kappa 0.842 / 0.833 / 0.798. Deriving it from the trade horizon
# instead (6 bars) drops every regime to ~0.3, the gate then passes NOTHING,
# and every arm reads as zero filtered signals -- which looks exactly like a
# finding about the filter. It is not; it is the wrong number.
KAPPA_HORIZON_BARS = 1


def conditions(bars: pd.DataFrame) -> dict[str, pd.Series]:
    """The four, at their committed thresholds. A is still the sanctioned stub."""
    return {
        "A": en.absorption_reversal(bars),
        "B": en.delta_divergence(bars, **BC),  # type: ignore[arg-type]
        "C": en.cvd_shift(bars, **BC),  # type: ignore[arg-type]
        "D": en.range_expansion(bars, **RANGE),  # type: ignore[arg-type]
    }


def arms(bars: pd.DataFrame, cond: dict[str, pd.Series], eligible: pd.Series) -> dict[str, pd.Series]:
    """The split. `3-of-4` stays as the reference that produced zero."""
    return {
        "exhaustion A|B": en.combine([cond["A"], cond["B"]], min_conditions=1, eligible=eligible),
        "continuation C&D": en.combine([cond["C"], cond["D"]], min_conditions=2, eligible=eligible),
        "continuation C|D": en.combine([cond["C"], cond["D"]], min_conditions=1, eligible=eligible),
        "3-of-4 reference": en.combine(list(cond.values()), min_conditions=3, eligible=eligible),
    }


def archive_rates(long_csv: Path, short_csv: Path) -> pd.Series:
    """Pooled archive p_target per (side, ATR bucket) -- the null this measures against."""
    frames = []
    for side, path in ((1, long_csv), (-1, short_csv)):
        counts = pd.read_csv(path).groupby("bucket")[["n", "target"]].sum()
        frames.append(counts.assign(side=side, p=counts["target"] / counts["n"]))
    return pd.concat(frames).reset_index().set_index(["side", "bucket"])["p"]


def measure(bars: pd.DataFrame, entries: pd.Series, rates: pd.Series, *, target: float,
            stop: float, horizon: int) -> dict[str, float]:
    """One arm: what it did, what the matched null says it should have done."""
    trades = bt.evaluate(bars, entries, horizons=(horizon,))
    if trades.empty:
        return {"signals": 0, "legs": 0}

    trades["outcome"] = bt.first_touch(bars, trades, target=target, stop=stop, horizon=horizon)
    measured = atr(bars, window=RANGE["atr_window"], min_bars=RANGE["atr_min_bars"])  # type: ignore[arg-type]
    trades["bucket"] = pd.cut(measured.reindex(trades["t"]).to_numpy(), EDGES).astype(str)
    done = trades.dropna(subset=["outcome"])
    if done.empty:
        return {"signals": int((entries != 0).sum()), "legs": 0}

    # The arm's own (side, bucket) mix, weighted onto the archive's rates. This
    # is the null: what an unselected entry with THIS arm's mix would have done.
    mix = done.groupby(["side", "bucket"]).size()
    expected = float((mix / mix.sum() * rates.reindex(mix.index)).sum())

    p_target = float((done["outcome"] == 1).mean())
    n = len(done)
    return {
        "signals": int((entries != 0).sum()),
        "legs": n,
        "p_target": p_target,
        "p_stop": float((done["outcome"] == -1).mean()),
        "null_matched": expected,
        "lift": p_target - expected,
        "needs": mde_rate(expected, n),
        "clears": float(p_target >= mde_rate(expected, n)),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bars", type=Path,
                   default=Path("analysis/regimes_2026-09-02/regime_labels_window_5min_k3.csv"))
    p.add_argument("--long-null", type=Path, default=Path("analysis/base_rates_70_20_30m.csv"))
    p.add_argument("--short-null", type=Path, default=Path("analysis/base_rates_short_70_20_30m.csv"))
    p.add_argument("--split", default="2026-07-19", help="training half is sessions <= this")
    p.add_argument("--target", type=float, default=70.0)
    p.add_argument("--stop", type=float, default=20.0)
    p.add_argument("--horizon", type=int, default=30)
    p.add_argument("--kappa-horizon-bars", type=int, default=KAPPA_HORIZON_BARS)
    a = p.parse_args()

    bars = pd.read_csv(a.bars, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    bars = bars[bars["session"].astype(str) <= a.split]
    print(f"{len(bars)} training bars, {bars['session'].nunique()} sessions, <= {a.split}")

    cond = conditions(bars)
    print("fires unfiltered: " + "  ".join(
        f"{k} {int((v != 0).sum())}" for k, v in cond.items()))

    kappa = regime_kappa(bars, horizon_bars=a.kappa_horizon_bars)
    passing = passes(bars, kappa=kappa, **FILTER)  # type: ignore[arg-type]
    rates = archive_rates(a.long_null, a.short_null)

    rows = {}
    for gate, eligible in (("unfiltered", pd.Series(True, index=bars.index)), ("filtered", passing)):
        for name, entries in arms(bars, cond, eligible).items():
            rows[f"{name} [{gate}]"] = measure(
                bars, entries, rates, target=a.target, stop=a.stop, horizon=a.horizon
            )

    print(f"\n=== {a.target:g}/{a.stop:g} at {a.horizon}m, against the mix- and side-matched archive null ===")
    with pd.option_context("display.width", 200):
        print(pd.DataFrame(rows).T.round(4).replace(np.nan, "").to_string())
    print("\n`needs` is horizon.mde_rate(null_matched, legs): the p_target this arm's own N could")
    print("separate from its own matched null at 80% power. `clears` is p_target >= needs.")
    print("An arm below `needs` has not failed -- it has not been measured. Check N first.")


if __name__ == "__main__":
    main()
