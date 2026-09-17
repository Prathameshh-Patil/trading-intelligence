"""E3 -- what a trade costs, and which of §10's (D, R) pairs survive it.

THE UNIT TRAP THIS MODULE EXISTS TO PIN. One basis point is 1e-4. A $0.30
spread on $3,400 gold is 0.88 bp, not 8.8 -- and the 10x version turns a
+6 bp expectancy into a -2 bp one, which reverses the decision about whether
the strategy is viable at all. A draft of the design made exactly that slip.
So every conversion goes through `to_bp`, and `to_bp` is tested against two
values this repo published independently: one GC tick is $0.10, and
`M3B_DRIFT.md` prices the GC round trip at 0.3504 bp including commission.

COST IS CHARGED ONCE. A round trip crosses one full spread. Charging half on
entry and half on exit is the same number; charging a full spread at each end
is the classic double-count and it manufactures a loss out of a real edge.

WHAT IS NOT HERE, AND WHY. The realised per-session spread distribution is the
empirical half of E3 and it is gated on §16's prediction being written. This
module is the arithmetic half, which §16 records as settled and not a
prediction. Nothing here reads the archive.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

# §13's hard exclusion: a trade is rejected when estimated slippage exceeds
# this share of intended risk. Spread alone is charged against the budget, so
# it also sets a floor under the stop distance -- see `d_floor_usd`.
MAX_SLIPPAGE_SHARE = 0.25

# §10's target floor and cap, in USD per ounce. `mathematical.md` states them
# as 100 and 150 GC ticks; the design §2 restates them in the unit that
# survives a change of venue.
TARGET_FLOOR_USD = 10.00
TARGET_CAP_USD = 15.00


def to_bp(usd_per_oz: float, price: float) -> float:
    """A distance in USD per ounce, as basis points of price."""
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    return usd_per_oz / price * 1e4


def ev_bp(*, p: float, d_bp: float, r_bp: float, cost_bp: float) -> float:
    """Expectancy per trade, net of cost. `p` is the win rate."""
    return p * r_bp - (1.0 - p) * d_bp - cost_bp


def breakeven(*, d_bp: float, r_bp: float, cost_bp: float) -> float:
    """The win rate at which `ev_bp` is exactly zero: (D + c) / (R + D)."""
    return (d_bp + cost_bp) / (r_bp + d_bp)


def d_floor_usd(*, cost_bp: float, price: float) -> float:
    """The tightest stop §13 does not exclude, in USD per ounce.

    Spread alone consumes `cost_bp / d_bp` of the risk budget, so the floor is
    where that ratio hits `MAX_SLIPPAGE_SHARE` -- before any slippage estimate
    is added, which is why it is a floor and not the answer.
    """
    return cost_bp / MAX_SLIPPAGE_SHARE / 1e4 * price


def surface(*, price: float, cost_bp: float, p: float,
            d_usd: Sequence[float], r_mult: Sequence[float]) -> pd.DataFrame:
    """EV over §10's (D, R) rectangle, with §13's exclusion marked.

    `R = max(mult * D, TARGET_FLOOR_USD)` capped at `TARGET_CAP_USD`, per §10.
    The floor is why a tight stop does not give a tight target: at D = $2.00
    the multiple leg yields $5.00, the floor lifts it to $10.00, and the
    realised payoff is 5:1 rather than the 2.5:1 the multiple names.
    """
    if any(d <= 0 for d in d_usd):
        # A zero-width stop is not an excluded trade, it is invalid input, and
        # `ZeroDivisionError` names neither. Found by review 2026-09-18.
        raise ValueError(f"every d_usd must be positive, got {list(d_usd)}")
    rows = []
    for d in d_usd:
        d_bp = to_bp(d, price)
        for m in r_mult:
            r_usd = min(max(m * d, TARGET_FLOOR_USD), TARGET_CAP_USD)
            r_bp = to_bp(r_usd, price)
            rows.append({
                "d_usd": d,
                "r_mult": m,
                "r_usd": r_usd,
                "d_bp": d_bp,
                "r_bp": r_bp,
                "ev_bp": ev_bp(p=p, d_bp=d_bp, r_bp=r_bp, cost_bp=cost_bp),
                "breakeven_p": breakeven(d_bp=d_bp, r_bp=r_bp, cost_bp=cost_bp),
                "excluded_by_s13": cost_bp / d_bp > MAX_SLIPPAGE_SHARE,
            })
    return pd.DataFrame(rows)
