"""§13's trade score and §15's execution state machine. Prathamesh's lane.

§15 is written as a chain of transitions, but its value is the list of things
it PREVENTS: more than two trades a day, more than one open position, a
widened stop, a size increased after a loss, and a limit order turned into a
market order once it expires. Every one of those is a rule someone adds back
under pressure, so every one is a refusal with a test behind it rather than a
comment.

THE RENORMALISATION IS THE SUBTLE PART. §13 scores nine components and three
of them -- `S_OFI`, `S_CVD`, `S_Hawkes` -- died with the tape when execution
moved to spot. Feeding them 0.0 with their original weights intact would lower
every score by the sum of three weights, and `Score >= 0.72` would then mean
something stricter than §13 wrote: not a high bar but an unreachable one. So
they are ABSENT from `WEIGHTS` and the survivors are renormalised to sum to 1.

WHAT IS NOT HERE. No order routing, no broker, no fills. `place_limit` and
`expire` model the lifecycle so the prohibitions can be tested; the thing that
talks to a venue does not exist and is not in this block's scope.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

import pandas as pd

from e3_cost import TARGET_CAP_USD, TARGET_FLOOR_USD, to_bp
from features.frame import TradeCandidate

# §13's components that survive on spot, renormalised to sum to 1 over the
# positives. The originals were nine; S_OFI, S_CVD and S_Hawkes are gone.
# Ratios between the survivors are kept as §13 wrote them -- volatility and
# the sweep carry the most, Hurst and the regime less.
WEIGHTS: dict[str, float] = {
    "s_vol": 0.30,
    "s_sweep": 0.30,
    "s_hurst": 0.20,
    "s_hmm": 0.20,
    "s_spread": -0.10,
    "s_news": -0.10,
}

SCORE_MIN = 0.72              # §13
P_E_MIN = 0.62                # §8
HURST_MIN = 0.58              # §9 condition 7, high-conviction
R_HAT_MIN_USD = 15.00         # §Objective, restated per design §2
D_MAX_USD = 5.00              # §10
MAX_SLIPPAGE_SHARE = 0.25     # §13
MAX_TRADES_PER_DAY = 2        # §11
MAX_LOSSES_PER_DAY = 2        # §11
LIMIT_EXPIRY_S = 20.0         # §9
DEFAULT_RISK_FRACTION = 0.004  # §11: "should default to 0.4%, not 0.7%"


class State(Enum):
    FLAT = "FLAT"
    PENDING = "PENDING"
    FILLED = "FILLED"


@dataclass(frozen=True, slots=True)
class Day:
    """The per-day counters §11 and §15 gate on. Reset at the session boundary."""
    trades: int = 0
    losses: int = 0
    position_open: bool = False


@dataclass(frozen=True, slots=True)
class Order:
    candidate: TradeCandidate
    state: State = State.PENDING
    expiry_s: float = LIMIT_EXPIRY_S
    filled: bool = False


def score(row: dict[str, float]) -> float:
    """§13's weighted score. Every component in `WEIGHTS` must be present.

    A missing component raises rather than defaulting to zero: a score
    computed on fewer terms is a different threshold wearing the same number.
    """
    return sum(w * row[k] for k, w in WEIGHTS.items())


def exclusions(row: dict[str, float], day: Day) -> tuple[str, ...]:
    """§13's hard exclusions, which override the score outright.

    `no_cvd_confirmation` is in §13's list and is absent here: there is no
    tape on spot, so it can neither pass nor fail. Dropping it is recorded in
    the design rather than silently defaulted either way.
    """
    out = []
    if row["r_hat_60_usd"] <= R_HAT_MIN_USD:
        out.append("forecast_range")
    if row["h_agree_value"] <= HURST_MIN:
        out.append("hurst")
    if not row["has_sweep"]:
        out.append("no_sweep")
    if row["d_usd"] > D_MAX_USD:
        out.append("stop_too_wide")
    if row["slippage_usd"] / row["d_usd"] > MAX_SLIPPAGE_SHARE:
        out.append("slippage")
    if row["news_lockout"]:
        out.append("news_lockout")
    if row["p_e"] < P_E_MIN:
        out.append("p_e")
    if day.trades >= MAX_TRADES_PER_DAY:
        out.append("trade_limit")
    if day.losses >= MAX_LOSSES_PER_DAY:
        out.append("loss_limit")
    if day.position_open:
        out.append("position_open")
    return tuple(out)


def limit_price(*, sweep_extreme: float, wick_w: float, side: int) -> float:
    """§9: `P_entry = P_s + 0.50W`, mirrored for a short."""
    return sweep_extreme + 0.5 * wick_w * side


def admit(row: dict[str, float], day: Day, *,
          ts: pd.Timestamp, entry: float, side: int, cost_bp: float) -> TradeCandidate | None:
    """The gate. `None` means no trade, and the reason is in `exclusions`.

    `ts`, `entry`, `side` and `cost_bp` are REQUIRED rather than defaulted out
    of the row. An earlier version defaulted `ts` to `0.0` behind a
    `type: ignore` and left the three bp fields at zero -- a candidate that
    type-checks, reads plausibly, and carries a timestamp of 1970 into
    whatever consumes it. A missing input should stop the trade, not be
    invented.
    """
    if exclusions(row, day) or score(row) < SCORE_MIN:
        return None
    d = row["d_usd"]
    r = min(max(2.5 * d, TARGET_FLOOR_USD), TARGET_CAP_USD)
    return TradeCandidate(
        ts=ts,
        side=side,
        p_e=row["p_e"],
        score=score(row),
        entry=entry,
        stop=entry - d * side,
        target=entry + r * side,
        # Carried rather than recomputed downstream, so a backtest and a live
        # path cannot disagree about the price they divided by.
        d_bp=to_bp(d, entry),
        r_bp=to_bp(r, entry),
        cost_bp=cost_bp,
    )


def place_limit(candidate: TradeCandidate | None) -> Order:
    """§9's limit, with its 20-second expiry."""
    if candidate is None:
        raise ValueError("no candidate to place; `admit` refused it")
    return Order(candidate=candidate)


def expire(order: Order) -> Order:
    """§9: "Never convert an unfilled limit order into a market order."

    Expiry returns to FLAT. There is deliberately no branch here that takes
    the trade anyway -- the missing branch IS the rule.
    """
    return replace(order, state=State.FLAT, filled=False)


def move_stop(order: Order, *, new_stop: float) -> Order:
    """Tighten only. §15 forbids widening, so widening raises.

    "Tighter" is toward entry on the side traded, which is why this needs the
    candidate's side rather than a bare comparison.
    """
    c = order.candidate
    if (new_stop - c.stop) * c.side < 0:
        raise ValueError(
            f"refusing to widen the stop from {c.stop} to {new_stop}; §15 forbids it")
    return replace(order, candidate=replace(c, stop=new_stop))


def size_lots(*, equity: float, risk_frac: float, d_usd: float, day: Day,
              value_per_lot: float = 100.0) -> float:
    """§11's sizing. Never larger after a loss -- §15 forbids martingale.

    `value_per_lot` is $100 per $1.00/oz for a 100-ounce standard lot. A
    fractional result is correct on a CFD; rounding to a broker minimum is
    the broker layer's job and not this function's.
    """
    if day.losses > 0:
        risk_frac = min(risk_frac, DEFAULT_RISK_FRACTION)
    return equity * risk_frac / (d_usd * value_per_lot)
