"""R-based metrics, and the gate table §7 commits to before the first run.

**EVERYTHING IS IN R AND NOT IN DOLLARS**, because a dollar figure is a
statement about the declared equity and the lot size as much as about the
strategy. One R is the risk taken at entry -- `d_usd x lots x value_per_lot`,
which §11's sizing makes equal to `equity x risk_fraction` on every trade -- so
a sum of R-multiples is comparable across trades, strategies and account sizes.
Dollars appear once, in the drawdown, because §7's C5 is stated as a percentage
of starting equity.

WHY DAILY AND NOT PER-TRADE SHARPE. Track C takes roughly one trade a week. A
per-trade Sharpe over 40 observations a year is a number with an enormous
standard error, and `tuning.deflated_sharpe` would then be haircutting a
quantity that is mostly noise. Daily sums include the zeros -- the days the
engine refused everything -- which is the honest denominator: a strategy that
trades twice a month is flat most days, and that is part of its return series
rather than missing from it.

WHAT IS DELIBERATELY ABSENT. No daily win rate. `TRACK_C_ENGINE.md` §7 drops
Quant_trading's G1 for a reason that applies with full force here: at one trade
a week most days have no trade, and "percentage of days finishing >= 0R" would
measure the calendar.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import tuning
from track_c import config, funnel

TRADING_DAYS = 252


def daily_r(trades: pd.DataFrame) -> pd.Series:
    """R summed per session, zeros included for sessions with no trade.

    The zeros are only recoverable from the trade frame's own span, so this is
    a return series over the traded period and not over the archive. A run that
    took its last trade in month three of five would otherwise report a Sharpe
    over a period it had already stopped trading in.
    """
    if trades.empty:
        return pd.Series(dtype="float64")
    by_day = trades.groupby("session")["r"].sum()
    span = pd.date_range(min(by_day.index), max(by_day.index), freq="B").date
    return by_day.reindex(span, fill_value=0.0)


def summarize(trades: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, float]:
    """The metric set, N always present. Empty in, zeros and NaNs out -- never
    an exception: "no trades" is a real result and the commonest one."""
    n = len(trades)
    if n == 0:
        return {"n": 0, "win_rate": float("nan"), "pf": float("nan"), "ev_r": float("nan"),
                "sharpe": float("nan"), "max_dd": 0.0, "worst_day_r": float("nan"),
                "total_r": 0.0, "days": 0}
    r = trades["r"].astype(float)
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    d = daily_r(trades)
    return {
        "n": n,
        "win_rate": float((r > 0).mean()),
        # A run with no losing trade has an undefined profit factor, not an
        # infinite one. NaN fails the C3 gate, which is the correct handling of
        # a sample too small to have lost yet.
        "pf": float(wins / losses) if losses > 0 else float("nan"),
        "ev_r": float(r.mean()),
        "sharpe": sharpe(d),
        "max_dd": max_drawdown(trades, cfg),
        "worst_day_r": float(d.min()),
        "total_r": float(r.sum()),
        "days": len(d),
    }


def sharpe(daily: pd.Series) -> float:
    """Annualised from daily R sums. NaN where there is nothing to divide by."""
    if len(daily) < 2 or daily.std(ddof=1) == 0:
        return float("nan")
    return float(daily.mean() / daily.std(ddof=1) * np.sqrt(TRADING_DAYS))


def max_drawdown(trades: pd.DataFrame, cfg: dict[str, Any]) -> float:
    """Deepest peak-to-trough fall of the equity curve, as a FRACTION of
    starting equity -- §7's C5 is stated that way and a fraction of running
    equity is a different, smaller number."""
    if trades.empty:
        return 0.0
    eq = trades["pnl_usd"].astype(float).cumsum()
    dd = (eq.cummax() - eq).max()
    return float(dd / config.f(cfg, "risk.equity_usd"))


def gate_table(*, per_strategy: dict[str, dict[str, float]], counts: funnel.Counts,
               windows: dict[str, list[float]], holdout: dict[str, dict[str, float]],
               trials: tuning.Trials, cfg: dict[str, Any]) -> pd.DataFrame:
    """§7's C1-C8, one row per strategy per gate, pass/fail against the TOML.

    `windows` is each strategy's per-out-of-sample-window total R and `holdout`
    its final-year summary; both are `walkforward.py`'s. A gate whose input is
    missing reports `NaN` and **fails** -- an unmeasured gate is not a passed
    one, and the commonest way a gate table lies is by quietly omitting the
    rows it could not compute.
    """
    rows = []
    for name, s in per_strategy.items():
        events = counts[(name, funnel.SUGGESTED)]
        w = windows.get(name, [])
        share = float(np.mean([x > 0 for x in w])) if w else float("nan")
        dsr = (tuning.deflated_sharpe(s["sharpe"], n_trials=max(trials.count, 1),
                                      n_obs=max(int(s["days"]), 2))
               if np.isfinite(s["sharpe"]) else float("nan"))
        h = holdout.get(name, {})
        rows += [
            _gate(name, "C1", "funnel events", events, config.i(cfg, "gates.c1_min_funnel_events"), "ge"),
            _gate(name, "C2", "EV per trade (R)", s["ev_r"], config.f(cfg, "gates.c2_min_ev_r"), "gt"),
            _gate(name, "C3", "profit factor", s["pf"], config.f(cfg, "gates.c3_min_pf"), "ge"),
            _gate(name, "C4", "deflated Sharpe", dsr, config.f(cfg, "gates.c4_min_dsr"), "gt"),
            _gate(name, "C5", "max drawdown", s["max_dd"], config.f(cfg, "gates.c5_max_dd"), "le"),
            _gate(name, "C6", "windows profitable", share, config.f(cfg, "gates.c6_min_window_share"), "ge"),
            _gate(name, "C7", "worst day (R)", s["worst_day_r"], config.f(cfg, "gates.c7_worst_day_r"), "ge"),
            _gate(name, "C8", "holdout total R", h.get("total_r", float("nan")), 0.0, "gt"),
        ]
    return pd.DataFrame(rows)


def _gate(strategy: str, gate: str, what: str, value: float, threshold: float,
          op: str) -> dict[str, Any]:
    """One gate row. **NaN never passes**, whichever direction the test runs."""
    ok = False
    if np.isfinite(value):
        ok = {"ge": value >= threshold, "gt": value > threshold,
              "le": value <= threshold}[op]
    return {"strategy": strategy, "gate": gate, "what": what, "value": value,
            "threshold": threshold, "op": op, "pass": ok}
