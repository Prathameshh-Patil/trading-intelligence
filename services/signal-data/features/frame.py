"""S13 -- the one frame both lanes write and the scorer reads.

WHY A TUPLE AND NOT A DATACLASS. The lanes produce columns, not objects, and
`require` is the whole contract. S9 froze the bars frame the same way. A
dataclass here would mean converting a 100k-row frame into rows to check a
header, which is a lot of machinery to answer a question about column names.

WHY EXTRA COLUMNS ARE AN ERROR AND NOT A WARNING. A lane that adds a column
has changed the seam without the other lane knowing. S2's history is the
argument: the seams that held were the ones that failed loudly, and
`strategy-split.md` §9 records the two-definitions-of-one-quantity bug that
came from a seam that did not.

WHAT THE THREE DEAD COLUMNS ARE NOT. `mathematical.md` §3-§5 specify OFI, CVD
and Hawkes intensity, and none of them appear here. Spot XAUUSD has no tape,
no aggregate size and no aggressor -- `instruments.XAUUSD.has_flow` is False
and `require_flow` raises on it. They are absent rather than present-and-NaN
so that a lane cannot quietly start writing a proxy into them.

THE UNIT RULE IS PART OF THE CONTRACT. No column is named in ticks or pips.
Distances are USD per ounce, rates are basis points. `mathematical.md` §1 is
explicit that pip conventions are broker-dependent, and this is where that
stops being advice and becomes a check.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FEATURES: tuple[str, ...] = (
    # frame identity -- Prathamesh
    "ts", "mid", "spread_bp",
    # §2 volatility ensemble -- Varad
    "r_hat_60_bp", "r_ratio",
    "sigma_yz_12", "sigma_yz_48", "sigma_yz_288", "sigma_garch",
    # §6 Hurst, two estimators and their agreement -- Varad
    "h_dfa_15m", "h_vt_15m", "h_agree",
    # §7 HMM -- Varad. NaN throughout if E4's kill fires; dropping them is a
    # seam change and needs both lanes, so they stay and carry NaN instead.
    "p_build", "p_expand",
    # §1 session windows and §12 news lockout -- Prathamesh
    "session", "phase", "news_lockout",
    # §9 sweep and reclaim -- Prathamesh
    "swept_level", "reclaim_dt_s", "wick_w",
)


def require(df: pd.DataFrame) -> None:
    """Exact column set. Missing and extra are both errors, and both name names.

    Naming the column is the point. "S13 frame invalid" sends someone diffing
    two 20-column frames by eye; "missing ['r_hat_60_bp']" does not.
    """
    got, want = set(df.columns), set(FEATURES)
    if missing := sorted(want - got):
        raise ValueError(f"S13 frame is missing {missing}")
    if extra := sorted(got - want):
        raise ValueError(f"S13 frame has columns not in the seam: {extra}")


@dataclass(frozen=True, slots=True)
class TradeCandidate:
    """What the FSM emits and the risk engine consumes.

    Distances are USD per ounce; `d_bp`, `r_bp` and `cost_bp` are the same
    quantities in basis points at the entry price, carried alongside rather
    than recomputed, so a backtest and a live path cannot disagree about the
    price they divided by.
    """

    ts: pd.Timestamp
    side: int            # +1 long, -1 short
    p_e: float
    score: float
    entry: float
    stop: float
    target: float
    d_bp: float
    r_bp: float
    cost_bp: float
