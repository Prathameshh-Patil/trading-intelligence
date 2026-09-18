"""What a fill costs, and whether a bar can be said to have produced one.

PESSIMISTIC BY CONSTRUCTION. A strategy that needs better execution than this
model should fail, and that is the correct outcome -- `TRACK_C_ENGINE.md` §6.1
and `Quant_trading/backtest.md` §3.

**THE BARS ARE MID BARS AND THAT IS THE WHOLE ARITHMETIC HERE.** `spot.py`
builds `open/high/low/close` from the mid and carries `spread_bp` in its own
column precisely so the spread can be charged explicitly rather than hidden in
the prices. So:

    a limit BUY at L fills when the ASK reaches L, i.e. when mid <= L - s/2
    a limit SELL at L fills when the BID reaches L, i.e. when mid >= L + s/2
    a market SELL at the stop fills at the BID: mid - s/2, minus slippage

Requiring the mid to reach the limit would be the classic optimistic fill: it
grants a fill the book never offered, on every trade, in the direction that
flatters the strategy. Charging half the spread at each end totals **one full
spread per round trip**, which is `e3_cost.py`'s rule -- the round trip crosses
one spread, and charging a whole one at each end is the double-count that
manufactures a loss out of a real edge.

**SLIPPAGE IS AN ASSUMPTION AND IS LABELLED ONE EVERYWHERE.** There is no live
trade journal, so there is nothing to measure. The model is `frac x margin x
spread` -- half a spread, scaled by a 1.5x margin of safety -- and it is
charged only on the MARKET exit, because the entry and the target are passive
limits that fill at their own price or not at all. Every report header states
it. If a live journal ever exists, this is the one function that changes.

⚠️ WHAT A 5-MINUTE BAR CANNOT SAY, STATED WHERE THE CODE SAYS IT. §9 gives the
limit a 20-second life. A 5-minute bar cannot resolve a 20-second order, and
neither can a 1-minute one. `limit_filled` therefore answers a WEAKER question
-- "did this bar trade through the limit at all" -- and every fill it grants
carries `unresolved=True` up to the report, where the numbers are labelled
upper bounds. `audit.py` measures the size of the gap by re-running the same
trades at `[data].audit_bar`; it does not close it.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from track_c import config


def bar_seconds(bar: str) -> float:
    """`"5min"` -> 300.0. The bar size as a number, for the resolution check."""
    return pd.Timedelta(bar).total_seconds()


def resolves_limit(cfg: dict[str, Any]) -> bool:
    """Can bars of this size resolve the limit's own life? At 5min: no.

    Kept as a function returning False today rather than a comment saying so,
    because the day tick-resolution replay exists this is the one call that
    flips and every "upper bound" label downstream follows it.
    """
    return bar_seconds(config.get(cfg, "data.bar")) <= config.f(cfg, "risk.limit_life_s")


def half_spread(spread_usd: float, cfg: dict[str, Any], *, news: bool) -> float:
    """Half the measured spread, tripled inside a news window.

    `news` is `ctx["news_lock"]`: §6.1 widens the spread even where the trade
    is not blocked outright, because a release moves the book whether or not
    the strategy was allowed to act.
    """
    mult = config.f(cfg, "cost.news_spread_mult") if news else 1.0
    return 0.5 * spread_usd * mult


def slippage(spread_usd: float, cfg: dict[str, Any], *, news: bool) -> float:
    """The assumed adverse move on a MARKET exit. See the module docstring."""
    mult = config.f(cfg, "cost.news_spread_mult") if news else 1.0
    return (config.f(cfg, "cost.slippage_spread_frac")
            * config.f(cfg, "cost.slippage_margin") * spread_usd * mult)


def round_trip_usd(spread_usd: float, cfg: dict[str, Any], *, news: bool) -> float:
    """Cost of one round trip in USD per ounce: one spread plus one slippage.

    One spread, not two: half on the passive entry and half on the exit. The
    slippage term is charged once because only the stop leg is a market order
    -- a target fill is a passive limit and pays none.
    """
    return 2 * half_spread(spread_usd, cfg, news=news) + slippage(spread_usd, cfg, news=news)


def limit_filled(bar: pd.Series, *, limit: float, side: int, spread_usd: float,
                 cfg: dict[str, Any], news: bool) -> bool:
    """Did a resting limit fill inside this bar? Mid bars, so the spread crosses.

    Last in queue, no positive slippage, fills at its own price: a touch that
    does not clear the half-spread is not a fill. The bar's own extreme is the
    test because a limit is either reached or it is not -- there is no partial
    fill in this model and no price improvement in it either.
    """
    s = half_spread(spread_usd, cfg, news=news)
    return bool(bar["low"] <= limit - s) if side > 0 else bool(bar["high"] >= limit + s)


def stop_fill_price(bar: pd.Series, *, stop: float, side: int, spread_usd: float,
                    cfg: dict[str, Any], news: bool) -> float:
    """Where a stop actually fills: the worse of the stop and the bar's extreme.

    **Gappy stops must hurt.** A bar that opens straight through the stop fills
    at the bar's extreme, not at the stop -- reporting a clean stop-out there
    is the single most flattering assumption a bar backtest can make, because
    it caps the loss at exactly 1R on the days that do not.
    """
    through = min(stop, float(bar["low"])) if side > 0 else max(stop, float(bar["high"]))
    return through - side * (half_spread(spread_usd, cfg, news=news)
                             + slippage(spread_usd, cfg, news=news))


def target_filled(bar: pd.Series, *, target: float, side: int, spread_usd: float,
                  cfg: dict[str, Any], news: bool) -> bool:
    """A passive limit at the target: same crossing rule as the entry."""
    s = half_spread(spread_usd, cfg, news=news)
    return bool(bar["high"] >= target + s) if side > 0 else bool(bar["low"] <= target - s)


def exit_price(*, price: float, side: int, spread_usd: float, cfg: dict[str, Any],
               news: bool) -> float:
    """A market exit at a known mid price -- the time stop and the end of day.

    Half the spread against us plus slippage, same as the stop leg. A time stop
    that exits at the mid is a free exit, and there is no such thing.
    """
    return price - side * (half_spread(spread_usd, cfg, news=news)
                           + slippage(spread_usd, cfg, news=news))
