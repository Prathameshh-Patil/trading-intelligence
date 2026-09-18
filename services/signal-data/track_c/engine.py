"""The event loop: bars in, trades and an attrition table out.

WHY THIS IS NOT `backtest.py`. That module is a vectorised grid sweep -- every
bar an entry, first touch against a `(target, stop, horizon)` lattice -- and it
is the right shape for the question Track B asks. Track C asks a different one:
a handful of candidates a week, each a passive limit with a life, one position
at a time, a stop that moves to break-even, and daily caps that refuse. None of
that is expressible as a lattice, and forcing one engine to be both would make
`backtest.py` worse at the thing it is already proven at.

**THE ONE CONVENTION BORROWED RATHER THAN RE-DECIDED IS THE SAME-BAR TIE.**
`backtest.first_touch` resolves a bar that clears both barriers to the STOP,
because the order is not in the bar and the worse of the two is the honest
answer. This loop does the same, in the same direction, for the same reason.
The function itself cannot be called here -- it takes a static bracket and this
engine's stop moves to break-even at 1.5D -- so what is shared is the rule, and
`test_track_c_engine.py` pins this loop's answer against `first_touch_from` on
a fixture where the stop does not move, which is where the two must agree.

FOUR THINGS THE LOOP ENFORCES THAT NO STRATEGY CAN OVERRIDE (§11, layer 4):
two trades a day, two losses a day, one position at a time, and a daily loss
cap. **They can only refuse.** A risk layer that could shrink a position to make
it fit is a risk layer that eventually shrinks to zero.

⚠️ EVERY FILL IN THIS ENGINE IS AN ASSUMPTION AT 5-MINUTE BARS. §9's limit
lives 20 seconds; a 5-minute bar cannot say whether it was touched inside that
life, and neither can a 1-minute bar. `Result.unresolved` counts them -- which
is all of them until tick replay exists -- and every number derived from this
run is an UPPER BOUND, labelled as one wherever it is quoted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

import fsm
from instruments import Instrument
from track_c import config, context, fills, funnel, strategies, suggest
from track_c.suggestion import Suggestion

# Layer-4 veto reasons. Not strategy conditions: they are refusals of a
# suggestion that already passed every condition its strategy has, which is a
# different fact about the archive and belongs in its own table.
VETOES: tuple[str, ...] = ("position_open", "trade_limit", "loss_limit",
                           "daily_loss_cap", "limit_expired")

TRADE_COLUMNS: tuple[str, ...] = (
    "strategy", "session", "ts_signal", "ts_entry", "side", "entry", "stop", "target",
    "lots", "d_usd", "ts_exit", "exit_price", "exit_reason", "pnl_usd", "r", "confidence",
    "unresolved", "be_moved")


@dataclass
class Position:
    """One open trade. Mutable, because the stop moves and nothing else does."""
    sug: Suggestion
    ts_entry: pd.Timestamp
    entry: float          # the traded price, which is the limit -- see `fills.py`
    stop: float
    bars_held: int = 0
    be_moved: bool = False   # carried so `audit.py` can exclude moved-stop trades


@dataclass
class Result:
    trades: pd.DataFrame
    counts: funnel.Counts
    vetoes: Counter[tuple[str, str]] = field(default_factory=Counter)
    unresolved: int = 0
    bars: int = 0


def run(bars: pd.DataFrame, inst: Instrument, cfg: dict[str, Any], *,
        events: pd.DatetimeIndex) -> Result:
    """Build the context over `bars` and walk it. The command-line entry point."""
    return loop(context.build(bars, inst, cfg, events=events), cfg)


def loop(ctx: pd.DataFrame, cfg: dict[str, Any]) -> Result:
    """One pass over an already-built context. Deterministic: same frame in,
    same trades out.

    Separate from `run` so a test can hand it a context whose every column is
    chosen -- steering a 2,880-bar percentile window into position through real
    bars would make the fixture, rather than the loop, the thing under test.
    """
    res = Result(trades=pd.DataFrame(columns=list(TRADE_COLUMNS)), counts=funnel.new(),
                 bars=len(ctx))
    rows: list[dict[str, Any]] = []
    day, session, day_pnl = fsm.Day(), None, 0.0
    pos: Position | None = None
    pending: Suggestion | None = None

    for i in range(len(ctx)):
        bar = ctx.iloc[i]
        if bar["session"] != session:
            session, day, day_pnl, pending = bar["session"], fsm.Day(), 0.0, None
        last_of_session = i + 1 == len(ctx) or ctx.iloc[i + 1]["session"] != session

        if pos is not None:
            done = _manage(pos, bar, cfg, last_of_session=last_of_session)
            if done is not None:
                rows.append(done)
                day_pnl += float(done["pnl_usd"])
                day = fsm.Day(trades=day.trades + 1,
                              losses=day.losses + (1 if done["pnl_usd"] < 0 else 0),
                              position_open=False)
                pos = None
        elif pending is not None:
            pos = _fill(pending, bar, cfg)
            if pos is not None:
                res.unresolved += 0 if fills.resolves_limit(cfg) else 1
            # Filled or not, the limit is dead: §9 gives it 20 seconds and this
            # bar is 5 minutes. It is never re-rested and never becomes a market
            # order.
            if pos is None:
                res.vetoes[(pending.strategy, "limit_expired")] += 1
            pending = None

        # The strategies are evaluated on EVERY bar, open position or not, so
        # the attrition table describes the archive rather than the subset of
        # it the engine happened to be flat for. `position_open` then refuses
        # at layer 4 and is counted there, where it is a fact about the risk
        # rules rather than about the market.
        day = fsm.Day(trades=day.trades, losses=day.losses, position_open=pos is not None)
        outcomes = suggest.row(ctx, i, cfg=cfg, day=day)
        for o in outcomes:
            funnel.record(res.counts, o)
        if pending is None and not last_of_session:
            pending = _choose(outcomes, day=day, day_pnl=day_pnl, cfg=cfg, vetoes=res.vetoes)

    funnel.check(res.counts, strategies.CONDITIONS)
    res.trades = pd.DataFrame(rows, columns=list(TRADE_COLUMNS))
    return res


def _choose(outcomes: tuple[Any, ...], *, day: fsm.Day, day_pnl: float,
            cfg: dict[str, Any], vetoes: Counter[tuple[str, str]]) -> Suggestion | None:
    """The first suggestion of the bar that layer 4 does not veto.

    **First, not best.** Ranking by `confidence` would compare four ordinal
    scores built from four different sets of conditions -- a number that is
    comparable within a strategy and meaningless across them. S1..S4 order is
    arbitrary and is written down as arbitrary; a same-bar collision is rare
    enough that the report counts them rather than resolving them cleverly.
    """
    veto = _veto(day=day, day_pnl=day_pnl, cfg=cfg)
    for o in outcomes:
        if not isinstance(o, Suggestion):
            continue
        if veto is None:
            return o
        vetoes[(o.strategy, veto)] += 1
    return None


def _veto(*, day: fsm.Day, day_pnl: float, cfg: dict[str, Any]) -> str | None:
    """§11's caps. They refuse; they never resize."""
    if day.position_open:
        return "position_open"
    if day.trades >= config.i(cfg, "risk.max_trades_per_day"):
        return "trade_limit"
    if day.losses >= config.i(cfg, "risk.max_losses_per_day"):
        return "loss_limit"
    if day_pnl <= -config.f(cfg, "risk.daily_loss_cap_usd"):
        return "daily_loss_cap"
    return None


def _fill(sug: Suggestion, bar: pd.Series, cfg: dict[str, Any]) -> Position | None:
    """Did the resting limit fill on this bar? If so, at its own price."""
    if not fills.limit_filled(bar, limit=sug.entry, side=sug.side,
                              spread_usd=float(bar["spread_usd"]), cfg=cfg,
                              news=bool(bar["news_lock"])):
        return None
    return Position(sug=sug, ts_entry=pd.Timestamp(str(bar.name)), entry=sug.entry,
                    stop=sug.stop)


def _manage(pos: Position, bar: pd.Series, cfg: dict[str, Any], *,
            last_of_session: bool) -> dict[str, Any] | None:
    """One bar against an open position. Stop first, then target, then the clocks.

    Stop before target is the same-bar tie rule, and it is the whole of what
    this loop borrows from `backtest.first_touch`.
    """
    pos.bars_held += 1
    s, side = float(bar["spread_usd"]), pos.sug.side
    news = bool(bar["news_lock"])
    adverse = float(bar["low"]) if side > 0 else float(bar["high"])

    if (adverse - pos.stop) * side <= 0:
        price = fills.stop_fill_price(bar, stop=pos.stop, side=side, spread_usd=s,
                                      cfg=cfg, news=news)
        return _close(pos, bar, price, "stop", cfg)
    if fills.target_filled(bar, target=pos.sug.target, side=side, spread_usd=s,
                           cfg=cfg, news=news):
        return _close(pos, bar, pos.sug.target, "target", cfg)

    stop_bars = config.opt_i(cfg, f"{pos.sug.strategy}.time_stop_bars")
    if last_of_session or (stop_bars is not None and pos.bars_held >= stop_bars):
        price = fills.exit_price(price=float(bar["close"]), side=side, spread_usd=s,
                                 cfg=cfg, news=news)
        return _close(pos, bar, price, "eod" if last_of_session else "time_stop", cfg)

    # Break-even at 1.5D, applied at the bar's close and therefore never within
    # the bar that earned it -- the conservative direction, because a stop that
    # moves later keeps risk on for longer.
    favourable = (float(bar["high"]) if side > 0 else float(bar["low"])) - pos.entry
    if favourable * side >= config.f(cfg, "risk.be_at_r") * pos.sug.d_usd:
        pos.stop, pos.be_moved = pos.entry, True
    return None


def _close(pos: Position, bar: pd.Series, price: float, reason: str,
           cfg: dict[str, Any]) -> dict[str, Any]:
    """The trade record. PnL is in TRADED prices at both ends -- see `fills.py`."""
    lot = config.f(cfg, "risk.value_per_lot")
    pnl = (price - pos.entry) * pos.sug.side * pos.sug.lots * lot
    return {
        "strategy": pos.sug.strategy, "session": bar["session"], "ts_signal": pos.sug.ts,
        "ts_entry": pos.ts_entry, "side": pos.sug.side, "entry": pos.entry,
        "stop": pos.sug.stop, "target": pos.sug.target, "lots": pos.sug.lots,
        "d_usd": pos.sug.d_usd, "ts_exit": bar.name, "exit_price": price,
        "exit_reason": reason, "pnl_usd": pnl,
        "r": pnl / (pos.sug.d_usd * pos.sug.lots * lot),
        "confidence": pos.sug.confidence, "unresolved": not fills.resolves_limit(cfg),
        "be_moved": pos.be_moved,
    }
