"""S4 -- momentum continuation out of a volatility contraction.

THE IDEA, IN ONE LINE. Volatility is the one property of this series with
strong serial dependence: quiet begets quiet until it does not, and the bar
that breaks the quiet is the start of the move rather than the end of it.

WHAT MAKES IT DIFFERENT FROM S1, WHICH IS THE COMPARISON THAT MATTERS, since
both are breakouts:

    S1's level is the CLOCK's           the Asian range, fixed 02:00 New York
    S4's level is VOLATILITY's          the last 20 bars' extreme, moving

    S1 fires when vol is ALREADY HOT    vol_ratio >= 1.15
    S4 fires when vol has been COLD     bb_width in its own bottom fifth

So S1 takes the expansion that is under way and S4 takes the one that is
starting. On a day that opens hot S1 fires and S4's squeeze condition refuses;
on a day that grinds sideways into the New York morning and then goes, S4 fires
and S1's Asian range has usually already been broken hours earlier. They are
not two settings of one strategy, and `test_strategies.py` asserts the two
gates are mutually exclusive on the volatility axis rather than asserting it
here in prose.

THE LIQUIDITY CONDITION IS A DECLARED PROXY. `ticks` is a quote-update count,
not traded volume -- spot has no tape. Requiring the count to be at or above
its own 10-day median is a statement about how actively the broker is
REPRICING, which correlates with liquidity and is not a measurement of it. It
is the second of Track C's two proxy assumptions (S3's VWAP weighting is the
other) and every report header names both.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import fsm
from features.structure import reclaim_delta
from track_c import bracket, config, context
from track_c.suggestion import Refusal, Suggestion, refuse

NAME = "s4"

CONDITIONS: tuple[str, ...] = (
    "window", "news_lock", "inputs", "squeeze", "hurst_agree", "hurst_trending",
    "liquidity", "breakout", *bracket.TAIL,
)

INPUTS: tuple[str, ...] = ("close", "atr_usd", "h_dfa", "h_vt", "bb_pct", "ticks_pct",
                           "s4_dc_high", "s4_dc_low", "spread_usd")


def evaluate(ctx: pd.DataFrame, i: int, *, cfg: dict[str, Any],
             day: fsm.Day) -> Suggestion | Refusal:
    r = ctx.iloc[i]
    ts = ctx.index[i]

    def no(reason: str) -> Refusal:
        return refuse(NAME, ts, reason, CONDITIONS)

    if not r[f"in_{NAME}"]:
        return no("window")
    if r["news_lock"]:
        return no("news_lock")
    if not context.finite(r, INPUTS):
        return no("inputs")
    if float(r["bb_pct"]) > config.f(cfg, "s4.squeeze_pct_max"):
        return no("squeeze")
    if not bool(r["h_agree"]):
        return no("hurst_agree")
    if float(r["h_dfa"]) < config.f(cfg, "s4.hurst_min"):
        return no("hurst_trending")
    if float(r["ticks_pct"]) < config.f(cfg, "s4.liquidity_pct_min"):
        return no("liquidity")

    atr = float(r["atr_usd"])
    delta = reclaim_delta(atr)
    close = float(r["close"])
    # The Donchian levels are shifted by one bar in `levels.donchian`, so the
    # breaking bar is not part of the level it breaks.
    if close > float(r["s4_dc_high"]) + delta:
        side, far = 1, float(r["s4_dc_low"])
    elif close < float(r["s4_dc_low"]) - delta:
        side, far = -1, float(r["s4_dc_high"])
    else:
        return no("breakout")

    # The stop sits behind the OPPOSITE edge of the squeeze -- the structure
    # being broken is the whole band, not the one edge. That is why this
    # strategy's `stop_pad_atr` is the largest of the four: a squeeze is by
    # definition a narrow thing to hide a stop behind, and a stop just under
    # the broken edge is a stop inside the noise that produced the squeeze.
    return bracket.build(
        strategy=NAME, conditions=CONDITIONS, ts=ts, side=side, close=close, atr=atr,
        stop=far - side * config.f(cfg, "s4.stop_pad_atr") * atr,
        spread_usd=float(r["spread_usd"]), news=bool(r["news_lock"]),
        confidence=_confidence(r, cfg=cfg), cfg=cfg, day=day)


def _confidence(r: pd.Series, *, cfg: dict[str, Any]) -> float:
    """How tight the squeeze, how persistent the tape, how active the quotes.

    Ordinal, not a probability. The squeeze leg is inverted -- a width in the
    bottom percentile of its own distribution is the strongest form of the
    condition, so a smaller number scores higher.
    """
    squeeze_max = config.f(cfg, "s4.squeeze_pct_max")
    tight = (squeeze_max - float(r["bb_pct"])) / squeeze_max if squeeze_max > 0 else 0.0
    mem = (float(r["h_dfa"]) - config.f(cfg, "s4.hurst_min")) / 0.25
    active = (float(r["ticks_pct"]) - config.f(cfg, "s4.liquidity_pct_min")) / 0.50
    return float(np.clip(np.mean(np.clip([tight, mem, active], 0.0, 1.0)), 0.0, 1.0))
