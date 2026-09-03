"""Layers 1 and 2: which bars are worth signalling on at all.

Week 1 D1, `plans/team/week-01.md` §3. Four gates, ANDed:

  * the bar's regime is persistent ABOVE ITS OWN BASE RATE (kappa),
  * there is enough range to pay for a stop (ATR),
  * the bar is not in the opening or closing minutes of its session,
  * price and its own trend agree.

**No threshold here has a default**, for the reason `strategies.py` has none:
a number chosen while looking at the answer is not a filter, it is a fit.

**The regime gate is kappa, not raw survival, and that is a correction.** D1
specified `survival >= 0.92`. Reviewed against the plot on 2026-09-04, raw
survival turned out to select on *prevalence*: a regime holding 63% of bars
scores 0.63 by shuffling alone, so the threshold kept the one regime with no
directional flow and dropped both that had it. Normalised for base rate the
ranking inverts -- the two flow regimes are the MORE persistent ones. The 0.92
number is retired; see `analysis/regimes_2026-09-02/README.md`.

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


def regime_kappa(bars: pd.DataFrame, *, horizon_bars: int) -> pd.Series:
    """Persistence above what the regime's own base rate already buys.

    `(P(stay) - share) / (1 - share)`, which is Cohen's kappa against a
    shuffled-label null. Raw survival is not comparable across regimes of
    different size: a state occupying 63% of bars scores 0.63 by chance and a
    state occupying 15% scores 0.15, so an absolute threshold on survival is a
    threshold on prevalence wearing a different name.

    A single-regime frame has no base rate to beat and comes back NaN rather
    than dividing by zero -- which fails closed at the gate, correctly.
    """
    surv = regime_survival(bars, horizon_bars=horizon_bars)
    share = bars["regime"].value_counts(normalize=True).reindex(surv.index)
    return (surv - share) / (1 - share).where(share < 1)


def passes(
    bars: pd.DataFrame,
    *,
    kappa: pd.Series,
    kappa_min: float,
    atr_window: str,
    atr_min_bars: int,
    atr_min: float,
    ema_span: int,
    edge_minutes: int,
) -> pd.Series:
    """The four gates, ANDed. True means the bar is worth signalling on.

    Every gate fails closed. NaN compares False throughout, so a bar with no
    trailing context, no regime label, or a regime missing from the kappa
    table is dropped rather than passed on a missing value.
    """
    return (
        (bars["regime"].map(kappa) >= kappa_min)
        & (atr(bars, window=atr_window, min_bars=atr_min_bars) >= atr_min)
        & trend_aligned(bars, span=ema_span)
        & session_interior(bars, edge_minutes=edge_minutes)
    )
