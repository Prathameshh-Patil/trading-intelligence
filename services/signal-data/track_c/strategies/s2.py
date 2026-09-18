"""S2 -- prior-day extreme swept, then reclaimed. The stop-run reversal.

THE IDEA, IN ONE LINE. Yesterday's high and low are where resting stops sit;
price that trades through one and then closes back inside the range has found
no acceptance beyond it, and the failure is the trade.

**THIS IS S1'S MIRROR AND THAT IS DELIBERATE.** S1 buys a level that breaks and
holds; S2 buys a level that breaks and fails. They are gated onto opposite
sides of the same Hurst reading -- S1 needs H >= 0.50, S2 needs H <= 0.55 -- and
the overlap in [0.50, 0.55] is left rather than closed, because a clean
partition would be a claim that H is measured to a precision `features/hurst.py`
says it is not (`AGREE_TOL` is 0.05, which is the width of that overlap).

WHAT IS WEAKER HERE THAN IN §9, SAID PLAINLY. §9 defines the reclaim on TICKS:
price must come back inside within 30 seconds, and `structure.sweeps` implements
exactly that. On 5-minute bars the same statement cannot be made -- the whole
sweep and reclaim may live inside one bar, or take three -- so this reads
"swept within the last `reclaim_bars` bars, closed back inside now", which is a
**strictly weaker condition than §9's** and admits excursions §9 would call
acceptance rather than rejection. The report says so; the intra-bar audit
measures how often the two disagree. `structure.sweeps` is not called because
it needs a tick frame, and a tick frame is what this engine does not have.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import fsm
from features.structure import reclaim_delta
from track_c import bracket, config, context
from track_c.suggestion import Refusal, Suggestion, refuse

NAME = "s2"

CONDITIONS: tuple[str, ...] = (
    "window", "news_lock", "inputs", "hurst_agree", "hurst_not_trending",
    "sweep", "reclaim", *bracket.TAIL,
)

INPUTS: tuple[str, ...] = ("close", "atr_usd", "h_dfa", "h_vt", "pdh", "pdl", "spread_usd")


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
    if not bool(r["h_agree"]):
        return no("hurst_agree")
    if float(r["h_dfa"]) > config.f(cfg, "s2.hurst_max"):
        return no("hurst_not_trending")

    atr = float(r["atr_usd"])
    delta = reclaim_delta(atr)
    swept = _swept_level(ctx, i, r, delta=delta, n=config.i(cfg, "s2.reclaim_bars"))
    if swept is None:
        return no("sweep")
    side, level, extreme = swept
    close = float(r["close"])

    if (close - level) * side < delta:
        # §9's delta again: the reclaim must CLEAR the level, not touch it.
        return no("reclaim")

    return bracket.build(
        strategy=NAME, conditions=CONDITIONS, ts=ts, side=side, close=close, atr=atr,
        stop=extreme - side * config.f(cfg, "s2.stop_pad_atr") * atr,
        spread_usd=float(r["spread_usd"]), news=bool(r["news_lock"]),
        confidence=_confidence(r, level=level, extreme=extreme, side=side, atr=atr, cfg=cfg),
        cfg=cfg, day=day)


def _swept_level(ctx: pd.DataFrame, i: int, r: pd.Series, *, delta: float,
                 n: int) -> tuple[int, float, float] | None:
    """Which prior-day extreme was swept in the last `n` bars, and how far.

    The window ENDS at this bar and includes it: a sweep and its reclaim inside
    one 5-minute bar is the commonest shape of the event, and excluding the
    current bar would refuse exactly those.

    **Neither, or BOTH, returns `None`.** Both is a window that swept the high
    and the low -- the day is not rejecting a level, it is moving, and there is
    no reversal to take. It shares the `sweep` stage rather than getting its
    own, because a stage with three events in five years tells nobody anything.
    """
    win = ctx.iloc[max(0, i - n + 1): i + 1]
    low, high = float(win["low"].min()), float(win["high"].max())
    low_sweep = low < float(r["pdl"]) - delta
    high_sweep = high > float(r["pdh"]) + delta
    if low_sweep and not high_sweep:
        return 1, float(r["pdl"]), low
    if high_sweep and not low_sweep:
        return -1, float(r["pdh"]), high
    return None


def _confidence(r: pd.Series, *, level: float, extreme: float, side: int, atr: float,
                cfg: dict[str, Any]) -> float:
    """Depth of the sweep, height of the reclaim, and distance from H's ceiling.

    Ordinal, not a probability. A deep sweep that is fully reclaimed is the
    event §9 describes; a shallow one that barely clears the level is the same
    shape at a size the spread can explain, and it scores lower.
    """
    depth = abs(level - extreme) / atr if atr > 0 else 0.0
    reclaim = (float(r["close"]) - level) * side / atr if atr > 0 else 0.0
    mem = (config.f(cfg, "s2.hurst_max") - float(r["h_dfa"])) / 0.25
    return float(np.clip(np.mean(np.clip([depth, reclaim, mem], 0.0, 1.0)), 0.0, 1.0))
