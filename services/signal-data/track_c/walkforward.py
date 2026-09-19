"""§14's walk-forward, and an honest statement about what it can protect against.

**TRACK C FITS NOTHING, SO THESE WINDOWS ARE NOT GUARDING A FIT.** Every
parameter is a constant in `config/track_c.toml` with a written provenance;
there is no training step, no re-weighting, no nightly optimisation. A
conventional walk-forward exists to stop a fitted parameter being scored on the
data it was fitted to, and that failure mode is absent here by construction.

So what are the windows for? **Stability, and the trial counter.**

  * **Stability.** Five consecutive out-of-sample windows either agree or they
    do not. A strategy that makes its whole result in one six-month window is
    a strategy whose edge is one regime, and C6 (four of five windows
    profitable) is the single best detector of that available here.
  * **The trial counter.** The absence of a fit is not the absence of choices.
    Every threshold in the TOML was chosen by a person, and the deflated Sharpe
    haircuts against how many such configurations the PROGRAMME has evaluated
    -- `tuning.Trials` is unresettable on purpose, and this module records one
    trial per run. A Sharpe quoted without its trial count is not a result.

**THE ENGINE RUNS ONCE OVER THE WHOLE ARCHIVE AND THE WINDOWS SLICE THE
TRADES.** Re-running per window would be identical arithmetic with one
difference that matters in the wrong direction: each window would need its own
warm-up, and a warm-up drawn from inside the window is the leak walk-forward
exists to prevent. Day state resets at every session boundary and folds are
month-aligned, so slicing at a boundary loses nothing.

**THE HOLDOUT IS OPENED ONCE.** `tuning.folds` never returns it. If it
disagrees with the windows, the answer is no, and no re-tune follows -- a
holdout you re-tune against is a validation set with a better name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

import tuning
from track_c import config, metrics


@dataclass(frozen=True, slots=True)
class Split:
    """The validation windows and where the untouched holdout begins."""
    windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    holdout_start: pd.Timestamp


def split(index: pd.DatetimeIndex, cfg: dict[str, Any]) -> Split:
    """§14's 24/6/3 roll over `index`, with the final `holdout_m` months held back.

    `tuning.folds` does the purging and the embargo; this decides only where
    the holdout starts and reduces each fold to the span of its validation
    window, which is all the slicing below needs.
    """
    holdout_start = index.max() - pd.DateOffset(months=config.i(cfg, "walkforward.holdout_m"))
    folds = tuning.folds(
        index, holdout_start=holdout_start,
        train_m=config.i(cfg, "walkforward.train_m"),
        val_m=config.i(cfg, "walkforward.val_m"),
        roll_m=config.i(cfg, "walkforward.roll_m"),
        label_minutes=config.i(cfg, "walkforward.label_minutes"),
        embargo_days=config.i(cfg, "walkforward.embargo_days"))
    return Split(windows=tuple((va.min(), va.max()) for _, va in folds),
                 holdout_start=holdout_start)


def independent(sp: Split, cfg: dict[str, Any]) -> int:
    """How many of the windows do not overlap -- the count the haircut may use.

    §14's own 6-month window rolled 3 months overlaps by half, so consecutive
    windows share three months and a good quarter is scored twice. `tuning`
    documents this; the number is carried into the report so the reader sees
    five windows and the four-or-so independent observations behind them.
    """
    return tuning.independent_folds(len(sp.windows),
                                    val_m=config.i(cfg, "walkforward.val_m"),
                                    roll_m=config.i(cfg, "walkforward.roll_m"))


def window_totals(trades: pd.DataFrame, sp: Split,
                  strategies: tuple[str, ...]) -> dict[str, list[float]]:
    """Each strategy's total R in each validation window. Empty window -> 0.0.

    Zero rather than NaN, and the difference is a C6 decision: a window in
    which a strategy did not trade did not make money, and counting it as
    "not profitable" is the conservative reading. A strategy that trades in
    two windows of five cannot pass C6, which is correct -- four of five
    windows profitable is also a statement about consistency of activity.
    """
    out: dict[str, list[float]] = {s: [] for s in strategies}
    for lo, hi in sp.windows:
        inside = trades[(trades["ts_signal"] >= lo) & (trades["ts_signal"] <= hi)]
        for s in strategies:
            out[s].append(float(inside[inside["strategy"] == s]["r"].sum()))
    return out


def holdout_summary(trades: pd.DataFrame, sp: Split, strategies: tuple[str, ...],
                    cfg: dict[str, Any]) -> dict[str, dict[str, float]]:
    """§7's C8. Opened once, at the end, and never re-tuned against."""
    held = trades[trades["ts_signal"] >= sp.holdout_start]
    return {s: metrics.summarize(held[held["strategy"] == s], cfg) for s in strategies}


def months_needed(cfg: dict[str, Any]) -> int:
    """Months of archive §14's geometry needs before one window can exist.

    Train and validate must both fit BEFORE the holdout starts, so the three
    add rather than overlap.
    """
    return sum(config.i(cfg, f"walkforward.{k}")
               for k in ("train_m", "val_m", "holdout_m"))


def supports_gates(span: tuple[pd.Timestamp, pd.Timestamp], cfg: dict[str, Any]) -> bool:
    """Whether this archive can measure C6 and C8 at all.

    Below `months_needed`, `tuning.folds` returns nothing and `holdout_start`
    lands before the first bar -- so C6 is NaN for every strategy and the
    "holdout" is the whole in-sample run wearing an out-of-sample name. **Both
    gates then read `False` by arithmetic rather than by evidence**, and §7
    makes a KILL final, so `report` refuses a verdict instead of issuing one.

    Same class of error as `TRACK_C_BUILD.md` §3(2) and §17: a quantity scored
    against a horizon that cannot support it.
    """
    return span[0] + pd.DateOffset(months=months_needed(cfg)) <= span[1]
