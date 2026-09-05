"""Track B's feature surface: the intersection of GC and spot, and nothing else.

Contract: `docs/strategy/ARCHITECTURE.md` §4.3. **The admission rule is one
sentence: if it cannot be computed on both instruments, it does not go in this
file.** Order flow fails that test on spot -- no tape, no aggregate volume, no
aggressor -- which is why `features/orderflow.py` is a separate, GC-only module
rather than a section of this one.

**Everything here is in BASIS POINTS of price** (§4.6), and that is not a
presentation choice. GC's tick is 0.10; an MT5 broker may call a XAUUSD pip
0.01 or 0.10, a 10x spread in what "40" means. A mis-scaled display renders
visibly wrong. A mis-scaled *bucket* silently pools two populations and reports
the average as a base rate, which is the error that cannot be seen in the
output. Conversion to whatever the trader's platform calls a pip happens once,
at stage 9, labelled.

Most functions here take no `Instrument` at all, and that is the point: a
quantity in basis points of price is already instrument-free. `atr_bp` is the
exception, because it wraps a tick-denominated function it must not re-derive.

STATUS. `atr_bp` ships with the seam (`plans/team/strategy-split.md` §3), so
the clock lane has its bucket axis on day one. **Every other function here is a
committed SIGNATURE with no body.** Ownership is by function name and is listed
in split.md §4; the order below is that table's order. Never reorder, never
rename, never add a function without standup -- two people fill in disjoint
bodies in this file and none of that works against a moving target.
"""

from __future__ import annotations

import pandas as pd

from features.expansion import atr
from instruments import Instrument


def to_bp(move: pd.Series, price: pd.Series) -> pd.Series:
    """A price-denominated quantity as basis points of the price it moved from.

    `price` is the bar's own close, contemporaneous. Anything later is
    lookahead, and a fixed reference price would make the bp figure drift with
    the level over 19 months -- which is exactly the pooling error §4.6 names.
    """
    return 1e4 * move / price


# --------------------------------------------------------------------------
# Varad -- the vol axis
# --------------------------------------------------------------------------
def atr_bp(bars: pd.DataFrame, inst: Instrument, *, window: str, min_bars: int) -> pd.Series:
    """ATR as basis points of price. **The bucket axis the whole track keys on.**

    `features.expansion.atr` is imported and rescaled, never re-derived --
    `regime_filter.py`'s rule, which carries double force now that two people
    are writing trailing windows: re-solving session-grouped windows in a
    second file is how the two quietly disagree about the London open.

    That import is also why this is the one function here needing an
    `Instrument`: `atr` answers in ticks, so the tick multiplies back out
    before the close divides in.
    """
    ticks = atr(bars, inst, window=window, min_bars=min_bars)
    return to_bp(ticks * inst.tick, bars["close"])


def range_bp(bars: pd.DataFrame) -> pd.Series:
    """High minus low as basis points of the close. Step 2."""
    raise NotImplementedError("range_bp -- Varad, step 2")


def rv_parkinson(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Parkinson realized volatility over a trailing session-grouped window.

    High-low rather than close-close, because it uses the whole bar and is the
    lower-variance estimator of the two on the same sample -- which matters
    when the claim M2 makes is about scale. Step 4.
    """
    raise NotImplementedError("rv_parkinson -- Varad, step 4")


def rv_slope(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Signed change in `rv_parkinson` across the window: the vol_state axis.

    **Signed, so the three states are EXPANDING / CONTRACTING / STABLE.** An
    absolute slope collapses the first two into one bucket, and compression
    before a move and decay after one are not the same regime. Step 4.
    """
    raise NotImplementedError("rv_slope -- Varad, step 4")


def efficiency_ratio(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Net directional move over total path travelled across the window.

    Near 1 the window went one way; near 0 it covered the same ground twice.
    This is the shape half of the vol axis -- `rv_parkinson` cannot tell a
    trend from a fight, and the two want different geometry. Step 4.
    """
    raise NotImplementedError("efficiency_ratio -- Varad, step 4")


# --------------------------------------------------------------------------
# Prathamesh -- the clock axis
# --------------------------------------------------------------------------
def session_phase(bars: pd.DataFrame, inst: Instrument) -> pd.Series:
    """Which of the six phases each bar sits in. `strategy-architecture.md` §2.

    **The six boundaries are in UTC and are pre-committed to Varad, in a
    commit, before M3 runs** (split.md §7). A boundary moved after the EV
    surface is visible is a fit, and `reach.py` is written against this column
    exactly as delivered. Step 3.
    """
    raise NotImplementedError("session_phase -- Prathamesh, step 3")


def event_proximity(
    bars: pd.DataFrame, calendar: pd.DatetimeIndex, *, window_minutes: int
) -> pd.Series:
    """Whether a bar falls within `window_minutes` either side of a release.

    `calendar` is the BLS release schedule and the Fed's FOMC dates -- both
    public, both free, and both known in advance, which is what makes this
    usable live rather than only in a backtest. The window is pre-committed
    (split.md §7). Step 3.
    """
    raise NotImplementedError("event_proximity -- Prathamesh, step 3")


def anchors(bars: pd.DataFrame, inst: Instrument) -> pd.DataFrame:
    """The reference prices of `inst.anchors`, one column each, aligned to bars.

    Session open, prior close, session high/low, opening range, TWAP. Every one
    is causal by construction -- a cumulative or a completed extreme over bars
    that have already closed. **`inst.anchors` is the authority on which are
    defined**: a 24x5 spot instrument's "session open" is a named boundary
    somebody chose, not a bell, and an anchor that means something different on
    the second instrument is worse than one that is absent. Step 3.
    """
    raise NotImplementedError("anchors -- Prathamesh, step 3")


def mid(quotes: pd.DataFrame) -> pd.Series:
    """(bid + ask) / 2. Spot-native; GC has no quote data in this repo. Step 6."""
    raise NotImplementedError("mid -- Prathamesh, step 6")


def spread_bp(quotes: pd.DataFrame) -> pd.Series:
    """(ask - bid) as basis points of the mid.

    **Read the result with §7's caveat attached.** Spot spread is a broker
    pricing decision, not a market outcome: a dealer widens on its own risk
    policy and its own client flow, so two brokers disagree about the same
    instant. This yields a legitimate yes/no on whether spread structure
    predicts anything. It is never a threshold that transfers. Step 6.
    """
    raise NotImplementedError("spread_bp -- Prathamesh, step 6")


def quote_rate_z(quotes: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Quote updates per interval, z-scored on a trailing window.

    **Within instrument AND within vendor, never a raw threshold.** An
    absolute quote rate measures the vendor's throttling and aggregation as
    much as the market's activity, so a level that transfers between two feeds
    does not exist. A trailing z within one feed does. Step 6.
    """
    raise NotImplementedError("quote_rate_z -- Prathamesh, step 6")
