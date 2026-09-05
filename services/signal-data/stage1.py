"""Every Stage 1 candidate through the harness, with its null and A5's perturbation.

Design: docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md §2, §4, §6.
Commitments: services/signal-data/thresholds_selector.md Part A.

This is the file that turns Part B into results on the day Part B is written.
It holds no thresholds of its own -- the caller supplies each candidate already
bound to its bars, plus the numbers it was committed with:

    candidates = {
        "delta_outlier": (partial(st.delta_outlier, bars),
                          {"window": "30min", "min_bars": 20, "z": 3.0}),
        "footprint_stack": (partial(st.footprint_stack, ticks, bars),
                            {"ratio": 3.0, "min_stack": 3}),
    }

Binding bars (and ticks, for the one candidate that needs them) at the call
site is what lets two strategies with different arities go through one loop.

What it deliberately does NOT do:

  * It does not fit anything, so there is no walk-forward split here. A1's
    split is about regimes, and regimes are Stage 2 -- which exists only if
    Stage 1's kill gate is cleared first.
  * It does not choose between strategies. That is select.py's job and it is
    downstream of a gate that has not been reached.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

import backtest as bt
from instruments import Instrument

type Thresholds = dict[str, float | int | str]
type Candidate = tuple[Callable[..., pd.Series], Thresholds]
type DecisionFilter = Callable[[pd.Series, pd.DataFrame], pd.Series]

# A5 moves DELTA MAGNITUDES, because the ~15-20% error it exists for is in the
# delta measurement itself. A window length, a bar count and a level count are
# not delta magnitudes and inherit nothing, so `window`, `min_bars` and
# `min_stack` are absent here on purpose rather than by oversight.
#
# `z` is listed, but read what it buys with care. A z-score divides by the
# standard deviation of the same series, so it is invariant to a uniform
# rescaling of delta -- perturbing it is a robustness check on the threshold,
# NOT a measurement of the inherited error, which is what A5 is written for.
# `ratio` is a volume ratio and is invariant for the same reason. `min_slope`,
# `min_ratio` and `min_delta` are denominated in contracts and are the two
# candidates that genuinely carry the error. See tests/test_stage1.py.
PERTURB = frozenset({"z", "min_slope", "min_ratio", "min_delta", "ratio"})

PERTURBATIONS = {"thr-20%": 0.8, "thr+20%": 1.2}


def perturb(thresholds: Thresholds, k: float) -> Thresholds:
    """Scale the delta magnitudes by `k`, pass everything else through."""
    out: Thresholds = {}
    for name, value in thresholds.items():
        if name not in PERTURB:
            out[name] = value
        elif isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"{name!r} is named for perturbation but is not numeric: {value!r}")
        else:
            out[name] = value * k
    return out


def run(
    candidates: dict[str, Candidate],
    bars: pd.DataFrame,
    inst: Instrument,
    *,
    horizons: tuple[int, ...] = bt.HORIZONS,
    seed: int = 0,
    decision_filter: DecisionFilter | None = None,
) -> pd.DataFrame:
    """One tidy row per strategy, variant and horizon, N on every one of them.

    Variants are always reported together, because each is only meaningful
    beside the others:

      * `actual`    -- the rule as committed
      * `null`      -- §6.3's stage-1 null: random entry, matched count,
                       holding period and side mix
      * `thr-20%` / `thr+20%` -- A5. An edge that does not survive its own
                       known error bar is not an edge
      * `filtered`  -- A6, and ONLY when a filter is supplied. Its absence is
                       the honest report that no filter has been applied, which
                       is the current state: decision_filter.py is §3's seam and
                       the trader authors it
    """
    rows = []
    for name, (fn, thresholds) in candidates.items():
        entries = fn(**thresholds)
        variants: dict[str, pd.Series] = {
            "actual": entries,
            "null": bt.random_entries(bars, entries, seed=seed),
            **{v: fn(**perturb(thresholds, k)) for v, k in PERTURBATIONS.items()},
        }
        if decision_filter is not None:
            variants["filtered"] = decision_filter(entries, bars)

        for variant, sides in variants.items():
            trades = bt.evaluate(bars, sides, inst, horizons)
            for h in horizons:
                rows.append(
                    {"strategy": name, "variant": variant, "horizon": h, **bt.summarize(trades, inst, h)}
                )
    return pd.DataFrame(rows)
