"""Layers 1 and 2: which bars are worth signalling on at all.

Week 1 D1, `plans/team/week-01.md` §3. Four gates, ANDed:

  * the bar's regime survives the horizon it would be traded over,
  * there is enough range to pay for a stop (ATR),
  * the bar is not in the opening or closing minutes of its session,
  * price and its own trend agree.

**No threshold here has a default**, for the reason `strategies.py` has none:
a number chosen while looking at the answer is not a filter, it is a fit.

The survival table is an *argument*, not something this module computes for
itself. It is the only quantity here that reads forward, so fitting it belongs
at the call site where the training/held-out split is visible -- buried in a
gate it would be lookahead nobody could see.

The three traps `strategies.py` documents apply unchanged, and the machinery
that solves them is imported rather than rewritten: clock-based windows,
grouped by session, nothing reading a bar later than the one it scores.
Re-solving session-grouped trailing windows in a second file is how the two
quietly disagree -- which is also why `atr` moved to `features/expansion.py`
on D2 and is imported here rather than kept in two places.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.expansion import atr


def regime_survival(bars: pd.DataFrame, *, horizon_bars: int) -> pd.Series:
    """P(the regime label still holds `horizon_bars` ahead), per regime.

    Fit on the training half and nowhere else. This reads forward, which is
    what makes it a property of a regime rather than of a bar.

    Bars with no forward bar left in their session are dropped rather than
    counted as a change: a session ending is not a regime ending, and counting
    it as one penalises exactly the regimes that run to the close.
    """
    fwd = bars.groupby("session", sort=False)["regime"].shift(-horizon_bars)
    held = (fwd == bars["regime"]).where(fwd.notna())
    return held.groupby(bars["regime"]).mean()


def trend_aligned(bars: pd.DataFrame, *, span: int) -> pd.Series:
    """Price on the side of its EMA that the EMA is moving towards.

    Above an average that is higher than it was `span` bars ago, or below one
    that is lower. The gate is direction-agnostic: a clean downtrend aligns
    short and passes.

    **The slope is measured over `span` bars, and a one-bar slope would make
    this gate a tautology.** `ema_t` always lies between `close_t` and
    `ema_t-1`, so `close > ema_t` and `ema_t > ema_t-1` are the same statement
    and the comparison can never disagree -- it would pass everything except
    an exactly flat bar and filter nothing at all. Over `span` bars the two
    are independent, which is the whole point: price back above a still-lower
    average is a bounce inside a downtrend, not a trend.

    A flat EMA is not a trend: a slope of exactly zero fails rather than
    counting as agreement.
    """
    ema = bars.groupby("session", sort=False)["close"].transform(
        lambda c: c.ewm(span=span, adjust=False).mean()
    )
    slope = ema.groupby(bars["session"].to_numpy(), sort=False).diff(span)
    return (np.sign(bars["close"] - ema) == np.sign(slope)) & (slope != 0)


def session_interior(bars: pd.DataFrame, *, edge_minutes: int) -> pd.Series:
    """Bars at least `edge_minutes` inside both ends of their own session.

    The open and the close are where the spread is widest and where a fill is
    least like the close it was signalled on.
    """
    t = bars.index.to_series()
    g = t.groupby(bars["session"].to_numpy(), sort=False)
    edge = pd.Timedelta(minutes=edge_minutes)
    return (t >= g.transform("min") + edge) & (t <= g.transform("max") - edge)


def passes(
    bars: pd.DataFrame,
    *,
    survival: pd.Series,
    survival_min: float,
    atr_window: str,
    atr_min_bars: int,
    atr_min: float,
    ema_span: int,
    edge_minutes: int,
) -> pd.Series:
    """The four gates, ANDed. True means the bar is worth signalling on.

    Every gate fails closed. NaN compares False throughout, so a bar with no
    trailing context, no regime label, or a regime missing from the survival
    table is dropped rather than passed on a missing value.
    """
    return (
        (bars["regime"].map(survival) >= survival_min)
        & (atr(bars, window=atr_window, min_bars=atr_min_bars) >= atr_min)
        & trend_aligned(bars, span=ema_span)
        & session_interior(bars, edge_minutes=edge_minutes)
    )
