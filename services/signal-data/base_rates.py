"""The unconditional reach baseline across the archive -- the null, month by month.

Design: docs/superpowers/specs/2026-09-05-live-signal-pipeline-design.md §6.3.

`backtest.reach_table` answers "how often did the target come first" for one
frame. This asks the prior question: **what is that number when nothing is
selecting the entries at all, and is it stable enough to be a null.**

Two reasons it has to be measured over the archive rather than over July:

  * A base rate from one month is a base rate for one month. If p_target swings
    across the 19, then conditioning on ATR alone is not enough to make a
    forecast mean anything, and that is a finding about the product rather than
    about the data.
  * `horizon.py`'s rate power says a 70/20 bracket needs ~454 signals to prove
    it has moved off the base rate. July's training half supplies 46. The
    sample is the binding constraint and it is already on disk.

**Pooling is a sum of counts, never a mean of rates.** Months differ in bar
count by more than 2x, so averaging their rates weights a short month like a
long one. Every function here returns counts and the rate is computed once, at
the end, from the pooled counts.

Nothing here selects, tunes or fits. It is the population being measured, the
same class of statistic as `horizon.py`'s sigma -- which is why running it over
every month costs no out-of-sample data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest import evaluate, first_touch
from features.expansion import atr
from instruments import GC
from regimes import resample_bars
from s1 import load_ticks, minute_bars


def month_counts(
    path: Path,
    *,
    target: float,
    stop: float,
    horizon: int,
    bar_size: str,
    edges: list[float],
    atr_window: str,
    atr_min_bars: int,
    side: int = 1,
) -> pd.DataFrame:
    """Per-ATR-bucket outcome counts for one month of ticks. Counts, not rates.

    `side` matters and is not a symmetry. Gold trended over this archive, so a
    short's base rate is its own number -- comparing a two-sided signal arm to
    a long-only null would credit the arm with the drift.
    """
    # GC is pinned, not injected: `path` is an S1 parquet and only GC produces one.
    bars = resample_bars(minute_bars(load_ticks(path)), bar_size)
    trades = evaluate(bars, pd.Series(side, index=bars.index), GC, horizons=(horizon,))
    trades["outcome"] = first_touch(bars, trades, GC, target=target, stop=stop, horizon=horizon)
    measured = atr(bars, GC, window=atr_window, min_bars=atr_min_bars).reindex(trades["t"])
    trades["bucket"] = pd.cut(measured.to_numpy(), edges)

    done = trades.dropna(subset=["outcome", "bucket"])
    by_bucket = done.groupby("bucket", observed=False)["outcome"]
    return pd.DataFrame(
        {
            "n": by_bucket.size(),
            "target": by_bucket.apply(lambda s: int((s == 1).sum())),
            "stop": by_bucket.apply(lambda s: int((s == -1).sum())),
        }
    )


def rates(counts: pd.DataFrame) -> pd.DataFrame:
    """Counts -> rates, with the N that produced them kept alongside."""
    out = counts.copy()
    out["p_target"] = (out["target"] / out["n"]).where(out["n"] > 0)
    out["p_stop"] = (out["stop"] / out["n"]).where(out["n"] > 0)
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--data", type=Path, default=Path("data"), help="dir of YYYY-MM/gc_trades.parquet")
    p.add_argument("--target", type=float, default=70.0, help="ticks")
    p.add_argument("--stop", type=float, default=20.0, help="ticks")
    p.add_argument("--horizon", type=int, default=30, help="minutes")
    p.add_argument("--bar-size", default="5min")
    p.add_argument("--atr-window", default="60min")
    p.add_argument("--atr-min-bars", type=int, default=6)
    p.add_argument("--edges", type=float, nargs="+", default=[0, 30, 40, 50, 1e9])
    p.add_argument("--out", type=Path, help="write per-month per-bucket counts to CSV")
    p.add_argument("--side", type=int, choices=[1, -1], default=1, help="+1 long, -1 short")
    a = p.parse_args()

    months = sorted(d for d in a.data.iterdir() if (d / "gc_trades.parquet").exists())
    if not months:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {a.data}")

    per_month, total = {}, None
    for month in months:
        counts = month_counts(
            month / "gc_trades.parquet",
            target=a.target, stop=a.stop, horizon=a.horizon, bar_size=a.bar_size,
            edges=a.edges, atr_window=a.atr_window, atr_min_bars=a.atr_min_bars, side=a.side,
        )
        per_month[month.name] = counts
        total = counts if total is None else total.add(counts, fill_value=0)
        pooled = rates(counts.sum().to_frame().T)
        print(f"{month.name}  n={int(counts['n'].sum()):6d}  "
              f"p_target={pooled.loc[0, 'p_target']:.4f}  p_stop={pooled.loc[0, 'p_stop']:.4f}",
              flush=True)

    assert total is not None
    side_name = "long" if a.side > 0 else "short"
    print(f"\n=== pooled, {len(months)} months, {side_name}, {a.target:g}/{a.stop:g} at {a.horizon}m ===")
    print(rates(total).round(4).to_string())

    monthly = pd.Series(
        {m: c["target"].sum() / c["n"].sum() for m, c in per_month.items() if c["n"].sum()}
    )
    print(f"\nmonthly p_target: min {monthly.min():.4f} ({monthly.idxmin()})  "
          f"max {monthly.max():.4f} ({monthly.idxmax()})  spread {monthly.max()-monthly.min():.4f}")

    # **A spread in the line above is NOT evidence that any bucket's rate moved.**
    # A quiet month spends most of its bars in the low-ATR buckets and a violent
    # one in the high, so the pooled monthly number moves with the MIX even if
    # every bucket is constant. Only the table below separates the two, and the
    # distinction decides whether ATR is a sufficient conditioner or only the
    # first of several.
    by_bucket = pd.DataFrame(
        {m: c["target"] / c["n"].where(c["n"] > 0) for m, c in per_month.items()}
    ).T
    print("\n=== p_target by month x ATR bucket ===")
    print(by_bucket.round(3).to_string())
    spread = (by_bucket.max() - by_bucket.min()).round(3)
    print("\nwithin-bucket spread (max-min across months):")
    print(spread.to_string())
    print("\nIf these are small next to the monthly spread above, ATR is doing the work and the")
    print("headline swing is mix. If they are comparable, ATR alone is not a sufficient")
    print("conditioner and a forecast built on it inherits the rest as error it does not report.")

    if a.out:
        long = pd.concat({m: c for m, c in per_month.items()}, names=["month"]).reset_index()
        long.to_csv(a.out, index=False)
        print(f"\ncounts written to {a.out}")


if __name__ == "__main__":
    main()
