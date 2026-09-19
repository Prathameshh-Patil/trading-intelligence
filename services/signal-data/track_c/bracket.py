"""The last three conditions every strategy shares: the stop bounds and cost.

**WHY THE STOP IS NEVER CLIPPED INTO §10'S BOUNDS.** Clipping would be the
obvious move -- `max(2, min(5, d))` -- and it is wrong in a way that is hard to
see afterwards: each strategy's stop sits behind a *structure* (the far side of
a broken range, the swept extreme, the last hour's low), and a clipped stop
sits behind nothing. It is a different trade with the same name, and it is the
version the backtest would then score. So a stop outside [$2, $5] is a
**refusal**, and the refusal is counted -- which also means the attrition table
says how much of the archive §10's bounds cost, instead of hiding it.

`stop_too_tight` exists for the reason `TRACK_C_ENGINE.md` §2.1 records: a
$0.50 stop still takes `clip(2.5D, $10, $15)` and buys a $10 target, a 20:1
nominal R that comes from the target floor rather than from anything anyone
chose.

Sizing is `fsm.size_lots` -- imported, never re-spelled. It carries §15's
no-martingale rule (never larger after a loss), which a second copy here would
eventually not.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

import fsm
from track_c import config, fills
from track_c.suggestion import Refusal, Suggestion, refuse

# Every strategy's ordered condition list ends with these four, in this order,
# so the attrition tables of four structurally different strategies are
# comparable at the bottom even though nothing above it is.
#
# `no_atr` leads because §10's bounds became ATR multiples on 2026-09-19 and a
# bar with no ATR has no bounds to check against. Each strategy's `inputs`
# stage already refuses a NaN `atr_usd`, so this catches the case that is
# finite and still unusable -- a flat window measuring exactly zero -- rather
# than duplicating that guard. **It should sit at zero in every attrition
# table; a non-zero count here means `inputs` stopped covering what it claims.**
TAIL: tuple[str, ...] = ("no_atr", "stop_too_tight", "stop_too_wide", "slippage")


def limit(*, close: float, side: int, atr: float, pullback: float) -> float:
    """The entry limit: `pullback` ATRs BACK from the close, against the trade.

    Never at market and never through the close. §9's limit is a passive order
    with a 20-second life; an engine that entered at the close would be
    measuring a market order and calling it a limit, and every fill would be
    granted by construction rather than by the book.
    """
    return close - side * pullback * atr


def build(*, strategy: str, conditions: tuple[str, ...], ts: pd.Timestamp, side: int,
          close: float, atr: float, stop: float, spread_usd: float, news: bool,
          confidence: float, cfg: dict[str, Any], day: fsm.Day) -> Suggestion | Refusal:
    """A structural stop and a side in; §10's bracket and §11's size out."""
    entry = limit(close=close, side=side, atr=atr,
                  pullback=config.f(cfg, f"{strategy}.entry_pullback_atr"))
    d = (entry - stop) * side
    # §10's bounds are multiples of THIS bar's ATR, not dollars. `atr` is
    # already the argument the entry pullback is measured in, so the stop and
    # the entry are now scaled by the same quantity.
    if not atr > 0:
        return refuse(strategy, ts, "no_atr", conditions)
    if d < config.f(cfg, "risk.d_min_atr") * atr:
        # Includes d <= 0: a stop the pullback has walked past is not a tight
        # stop, it is an inverted trade, and it must not reach `Suggestion`.
        return refuse(strategy, ts, "stop_too_tight", conditions)
    if d > config.f(cfg, "risk.d_max_atr") * atr:
        return refuse(strategy, ts, "stop_too_wide", conditions)
    if fills.round_trip_usd(spread_usd, cfg, news=news) / d > config.f(cfg, "cost.max_slippage_share"):
        return refuse(strategy, ts, "slippage", conditions)
    return Suggestion(
        strategy=strategy,
        ts=ts,
        side=side,
        entry=entry,
        stop=stop,
        target=entry + side * config.target_usd(d, cfg),
        lots=fsm.size_lots(equity=config.f(cfg, "risk.equity_usd"),
                           risk_frac=config.f(cfg, "risk.risk_fraction"),
                           d_usd=d, day=day,
                           value_per_lot=config.f(cfg, "risk.value_per_lot")),
        expires_at=ts + pd.Timedelta(seconds=config.f(cfg, "risk.limit_life_s")),
        confidence=confidence,
    )
