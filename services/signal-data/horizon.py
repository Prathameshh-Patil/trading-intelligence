"""How much edge each of backtest.py's horizons could even PROVE -- the kill gate's power.

Design: docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md §2 (the
kill gate), §4 (magnitude), §6.3 (the matched null), §6.5 (the n<30 floor).

The question here is not "does a strategy work". No threshold is committed yet
(§6.1, thresholds_selector.md Part B) and nothing in this file reads a strategy.
It is the question that comes first and was left open on 26 Aug: **at which of
(5, 15, 30) minutes is the kill gate decidable at all.** Noise in a forward move
grows with the horizon; the edge that has to clear that noise does not obviously
grow as fast. If 30 minutes cannot resolve a tradeable edge on the data that
exists, judging Stage 1 there kills strategies for being unmeasurable rather
than for being wrong -- and that is a decision about the instrument, not about
any threshold, so it is answerable before Part B rather than after.

Every forward move is measured THROUGH backtest.evaluate, so the leg semantics
here are the kill gate's own: clock-based horizons, session-bounded, entry at
the close of the signalling bar. Entering long on every bar is not a strategy --
it is the population §6.3's null draws from, and its dispersion is the noise
floor any strategy is measured against.

WHAT THIS CANNOT SEE
    5-minute bars, so entries land on the 5-minute grid and the 5m leg is one
    bar. A strategy firing intra-bar is not represented. The grid itself is
    not the problem -- measured below at 1.1% on sigma -- but re-run against
    1-minute bars once data/gc_trades.parquet is on this machine.

MEASURED -- GC July 2026, 6,276 five-minute bars, 23 sessions, every bar entered

        horizon      5m      15m      30m
        sigma      34.53   59.86    84.68   ticks
        sigma/sqrt(h)  1.000   1.001    1.001
        median |move| 17      28       40    ticks
        overlap rho   -0.009   0.659    0.831   (adjacent bars)
        mde @ n=100   13.68   23.72    33.55  ticks
        n for 3 ticks  2,081   6,251   12,507  signals

    THE PRICE SERIES IS A RANDOM WALK AT THESE HORIZONS, from two independent
    directions that were not fitted to each other. Dispersion grows as
    sqrt(h) to within 0.1%, and the overlap correlation between adjacent
    bars' legs lands at 0.659 and 0.831 against a random walk's predicted
    (h-5)/h = 0.667 and 0.833. Nothing unconditional is reverting or trending
    here, so a longer horizon buys variance at exactly the rate that makes an
    edge harder to prove and returns no structure for it.

    Robustness, because one month and one instrument is not much:
      - Both walk-forward halves scale the same (0.992-1.016) even though
        their volatility LEVELS differ by 19% -- sigma_5 is 37.02 before the
        19 Jul split and 31.09 after. The level moves; the exponent does not.
      - The 2026-07-16 session, rebuilt at 1-MINUTE resolution from the raw
        S1 fixture through a different code path, gives 1.000/1.011/1.019.
      - That same session sampled on the 5-minute grid gives sigma_5 32.31
        against 31.96 on every minute, so the grid costs 1.1%.

    WHAT IT MEANS FOR THE KILL GATE. Judged at 30 minutes, Stage 1 needs an
    edge 2.45x larger IN TICKS than at 5 minutes to reach the same
    significance, and the overlap penalty compounds it for any rule that
    fires in bursts -- which order-flow rules do. Against a month holding
    6,253 usable bars, proving a 3-tick edge needs 12,507 signals at 30m and
    2,081 at 5m. Only one of those is inside a plausible data budget.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import HORIZONS, MIN_SAMPLES, evaluate
from s1 import TICK_VALUE

# Two-sided alpha = 0.05 at 80% power. Both terms, because the test has to
# clear the critical value AND land past it often enough to be worth running.
ZA, ZB = 1.959964, 0.841621
Z = ZA + ZB

BAR_COLS = ["timestamp", "open", "high", "low", "close", "session"]


def load_bars(path: Path) -> pd.DataFrame:
    """Bars from any frame carrying the OHLC + session columns evaluate() needs.

    The committed regime labels carry them, and are the only month-wide bar
    frame in this working copy -- data/gc_trades.parquet is on Prathamesh's
    machine. Their DERIVED columns are stale twice over (871690f dropped a
    feature, d3c896f fixed the straddling window); OHLC and session are
    resampled straight off the ticks and neither change touched them, which is
    why only those are read here.
    """
    df = (
        pd.read_csv(path, parse_dates=["timestamp"])
        if path.suffix == ".csv"
        else pd.read_parquet(path)
    )
    missing = sorted(set(BAR_COLS) - set(df.columns))
    if missing:
        raise ValueError(f"{path}: not a bar frame, missing {missing}")
    return df[BAR_COLS].set_index("timestamp").sort_index()


def mde_ticks(sigma: float, n: int) -> float:
    """Smallest mean edge separable from a matched-count null at 80% power.

    Two samples of n at the same dispersion, so the SE of the difference is
    sigma*sqrt(2/n). Strategy and null are drawn from the same month and their
    entries overlap, which makes a real paired test slightly more powerful --
    read this as the pessimistic bound, not the exact one.
    """
    return Z * sigma * float(np.sqrt(2 / n))


def n_for(sigma: float, edge: float) -> int:
    """Signals needed before `edge` ticks becomes provable. Inverse of mde_ticks."""
    return int(np.ceil(2 * (Z * sigma / edge) ** 2))


def _se(p: float, n: int) -> float:
    return float(np.sqrt(p * (1 - p) / n))


def mde_rate(p0: float, n: int) -> float:
    """Smallest hit rate `n` signals could separate from a base rate of `p0`.

    The reach table's number is a RATE, so `mde_ticks` does not apply to it --
    the noise on a proportion is p(1-p)/n, not a dispersion in ticks, and using
    the wrong one is the kind of error that reads as a plausible answer.

    One-sample, because `p0` is measured on the whole unconditional population
    (3,438 legs at 30m, SE ~0.006) while a signal arm is tens. Treating the
    base rate as known is the honest simplification there; treating it as a
    second small sample would understate the power available.

    Solved by iteration rather than by holding the variance at `p0`: p1 > p0
    in this range means p1(1-p1) > p0(1-p0), so the fixed-variance shortcut
    understates the lift needed by about a point -- small, but it errs toward
    flattering the strategy, which is the direction that must not be free.

    **Optimistic in one way that matters and is not in the arithmetic.**
    Adjacent signals share most of their leg, and order-flow rules fire in
    bursts, so the effective sample inside a burst is far below the count.
    Read every number off this as a floor on what is needed.
    """
    p1 = p0
    for _ in range(32):
        p1 = min(p0 + ZA * _se(p0, n) + ZB * _se(p1, n), 1.0)
    return p1


def n_for_rate(p0: float, p1: float) -> int:
    """Signals needed before a lift from `p0` to `p1` is provable. Inverse of mde_rate."""
    if p1 <= p0:
        raise ValueError(f"p1 must exceed p0; got {p1} <= {p0}")
    num = ZA * np.sqrt(p0 * (1 - p0)) + ZB * np.sqrt(p1 * (1 - p1))
    return int(np.ceil((num / (p1 - p0)) ** 2))


def power_table(trades: pd.DataFrame, edges: tuple[float, ...], counts: tuple[int, ...]) -> pd.DataFrame:
    """One row per horizon: what the noise is, and what it takes to beat it."""
    base = float(trades["move_5m"].dropna().std())
    rows = []
    for h in HORIZONS:
        move = trades[f"move_{h}m"]
        legs = move.dropna()
        sigma = float(legs.std())
        row = {
            "n_bars": len(move),
            "n_legs": len(legs),
            "lost_to_session_end_pct": round(move.isna().mean() * 100, 1),
            "sigma_ticks": round(sigma, 2),
            "sigma_vs_sqrt_h": round(sigma / (base * np.sqrt(h / 5)), 3),
            "median_abs_move": round(float(legs.abs().median()), 2),
            "mfe_median": round(float(trades[f"mfe_{h}m"].median()), 2),
            "mae_median": round(float(trades[f"mae_{h}m"].median()), 2),
            # Adjacent signals share all but five minutes of their leg, so their
            # outcomes are not independent draws. Harmless for a rule that fires
            # a few times a day; NOT harmless for order-flow rules, which fire in
            # bursts -- inside a burst the effective sample is far below the count.
            "overlap_rho_1bar": round(float(move.corr(move.shift(1))), 3),
        }
        row |= {f"mde_n{n}": round(mde_ticks(sigma, n), 2) for n in counts}
        row |= {f"n_for_{e:g}t": n_for(sigma, e) for e in edges}
        rows.append(row)
    return pd.DataFrame(rows, index=[f"{h}m" for h in HORIZONS])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bars", type=Path, default=Path("analysis/regimes/regime_labels_window_5min_k3.csv"))
    p.add_argument("--cost-ticks", type=float, default=1.4,
                   help="round-trip cost an edge must clear: 1 tick of spread/slippage "
                        "($10) plus ~$4 commission = 1.4 ticks. State it, do not bury it.")
    p.add_argument("--counts", type=int, nargs="+", default=[MIN_SAMPLES, 50, 100, 250, 500],
                   help="signal counts to report the detectable edge at")
    p.add_argument("--edges", type=float, nargs="+", default=[3.0, 5.0, 10.0],
                   help="edge sizes, in ticks, to report the required signal count for")
    a = p.parse_args()

    bars = load_bars(a.bars)
    trades = evaluate(bars, pd.Series(1, index=bars.index))
    table = power_table(trades, (a.cost_ticks, *a.edges), tuple(a.counts))

    print(f"\n{len(bars)} bars, {bars.index[0].date()} -> {bars.index[-1].date()}, "
          f"{bars['session'].nunique()} sessions, entry on every bar (the null's population)")
    print(f"cost floor {a.cost_ticks} ticks = ${a.cost_ticks * TICK_VALUE:.2f} round trip\n")
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print(table.T)
    print("\nmde_nN is the smallest mean edge, in ticks, that N signals could separate from a")
    print(f"matched-count null at 80% power. Below the {a.cost_ticks}-tick cost floor it is not")
    print("worth having; above the month's supply of signals it is not provable here.")
    print(f"n_for_Et is the reverse: signals needed to prove an edge of E ticks. Against "
          f"{len(bars)} bars\nin the month, anything far above that count is a data ask, not a "
          f"modelling choice.")


if __name__ == "__main__":
    main()
