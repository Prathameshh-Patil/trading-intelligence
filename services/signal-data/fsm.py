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

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

import numpy as np
import pandas as pd

from e3_cost import TARGET_CAP_USD, TARGET_FLOOR_USD, to_bp
from features.frame import TradeCandidate
from features.structure import MAX_RECLAIM_S

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


ROW: tuple[str, ...] = (*WEIGHTS, "r_hat_60_usd", "h_agree_value", "has_sweep",
                        "d_usd", "slippage_usd", "news_lockout", "p_e")


def _unit(x: float) -> float:
    """Clip into [0, 1]. NaN survives -- `fsm_row` is what rejects it."""
    return float(np.clip(x, 0.0, 1.0))


def fsm_row(row: Mapping[str, float], *, p_e: float, d_usd: float,
            slippage_usd: float) -> dict[str, float]:
    """One S13 frame row -> the row `score`, `exclusions` and `admit` consume.

    This is the seam between `pipeline.build`'s frame and this module, and it
    exists because the two do not share names: the frame carries `h_agree`,
    `swept_level`, `reclaim_dt_s` and `wick_w`, and §13 asks for
    `h_agree_value`, `has_sweep` and six normalised score components. Every
    caller inventing that mapping privately is how two backtests come to
    disagree about what `Score >= 0.72` means.

    `p_e`, `d_usd` and `slippage_usd` are NOT in the frame and are required
    rather than defaulted: `p_e` is `classifier`'s calibrated output, `d_usd`
    is §10's stop distance and `slippage_usd` is an execution estimate. A
    defaulted `p_e` is a trade admitted on a probability nobody computed.

    NORMALISERS ARE A CHOICE, AND THIS IS WHERE THE CHOICE LIVES. §13 says
    "normalize each component to [0,1]" and gives no formula for any of the
    nine. Each of the six below is anchored on a constant the spec does give --
    $15/oz, 30 seconds, and H = 0.5 for a random walk against H = 1 for full
    persistence -- so none of them introduces a tuning knob. They are still a
    decision the room should ratify rather than a derivation from the spec.

    THE CONSERVATIVE HURST. §9 condition 7 reads one `H_15m`; there are two
    estimators and on real GC data they agree on only 25.3% of bars. The lower
    is used, so neither estimator alone can carry a bar past 0.58. `h_agree`
    stays in the frame for the classifier and is deliberately not consulted
    here -- `min` already refuses everything a boolean gate would.

    NaN IS REFUSED, AND THAT IS THE POINT OF THE FUNCTION. §7's `p_expand` is
    NaN on every row today, so this raises on every real row until E4 settles
    whether the HMM is identifiable at all. That is correct. `score` sums to
    NaN on a NaN component, `NaN < SCORE_MIN` is False, and `admit` would then
    return a live `TradeCandidate` on a score that does not exist.

    The one defined zero is the sweep. No sweep is an OBSERVATION -- §9 looked
    and there was none -- so `has_sweep` is 0.0 and `exclusions` refuses with
    `no_sweep`. A missing HMM is an absent measurement and is not the same
    thing, which is why one is a zero and the other is an exception.
    """
    if d_usd <= 0:
        raise ValueError(
            f"d_usd must be positive, got {d_usd}; §13 divides slippage by it and "
            "a zero stop reports every candidate as having no slippage at all")
    h = min(row["h_dfa_15m"], row["h_vt_15m"])
    swept = bool(np.isfinite(row["swept_level"]) and np.isfinite(row["reclaim_dt_s"]))
    news = float(bool(row["news_lockout"]))
    out = {
        "s_vol": _unit((row["r_hat_60_usd"] - R_HAT_MIN_USD) / R_HAT_MIN_USD),
        "s_sweep": _unit(1.0 - row["reclaim_dt_s"] / MAX_RECLAIM_S) if swept else 0.0,
        "s_hurst": _unit((h - 0.5) / 0.5),
        "s_hmm": _unit(row["p_expand"]),
        # A spread that eats the whole stop is a full penalty. `spread_bp` is
        # bp of `mid`, so it has to come back to USD before it can be compared
        # to one -- bp against USD is how a 3000x error looks reasonable.
        "s_spread": _unit(row["spread_bp"] * row["mid"] / 1e4 / d_usd),
        "s_news": news,
        "r_hat_60_usd": float(row["r_hat_60_usd"]),
        "h_agree_value": float(h),
        "has_sweep": float(swept),
        "d_usd": float(d_usd),
        "slippage_usd": float(slippage_usd),
        "news_lockout": news,
        "p_e": float(p_e),
    }
    if bad := sorted(k for k, v in out.items() if not np.isfinite(v)):
        raise ValueError(
            f"fsm row is not finite at {bad}; a NaN score compares False against "
            "SCORE_MIN and would be admitted as a trade rather than refused")
    return out


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
