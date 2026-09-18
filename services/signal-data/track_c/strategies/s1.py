"""S1 -- Asian-range breakout, gated on volatility expansion and persistence.

THE IDEA, IN ONE LINE. The Asian session prints a range while London and New
York are asleep; if the day is going to trend, the break of that range is where
it starts, and a break that happens while short-horizon volatility is already
running hot against its own daily baseline is the one worth taking.

WHAT MAKES IT STRUCTURALLY DIFFERENT FROM THE OTHER THREE, which matters more
than whether it works:

  * **Its level comes from the clock.** The Asian range is fixed by the time of
    day and is the same level all session. S4's level comes from volatility
    (a Bollinger squeeze) and moves; S2's comes from the previous session; S3
    has no level at all, only a mean.
  * **It buys strength.** S2 buys the failure of exactly this kind of break.
    The two cannot both fire on the same bar in the same direction, and when
    both fire at once on opposite sides that is a fact about the day worth
    seeing in the report rather than a bug.
  * **It needs H > 0.5 and expansion.** S3 needs the opposite of both. They
    partition the archive rather than competing over it.

THE CONDITION ORDER IS CHEAPEST-FIRST AND IT IS ALSO THE ATTRITION TABLE'S
X-AXIS. Clock before news before inputs before geometry: a bar refused at
`window` cost one comparison, and the ordering is what makes the funnel's
counts interpretable as "what the archive actually looks like" rather than as
an artefact of evaluation order.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import fsm
from features.structure import reclaim_delta
from track_c import bracket, config, context
from track_c.suggestion import Refusal, Suggestion, refuse

NAME = "s1"

CONDITIONS: tuple[str, ...] = (
    "window", "news_lock", "inputs", "range_width", "vol_expansion",
    "hurst_agree", "hurst_trending", "breakout", "not_extended", *bracket.TAIL,
)

INPUTS: tuple[str, ...] = ("close", "atr_usd", "vol_ratio", "h_dfa", "h_vt",
                           "asian_high", "asian_low", "spread_usd")


def evaluate(ctx: pd.DataFrame, i: int, *, cfg: dict[str, Any],
             day: fsm.Day) -> Suggestion | Refusal:
    """One bar in, a suggestion or the named condition that refused it."""
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

    atr = float(r["atr_usd"])
    width = float(r["asian_high"] - r["asian_low"])
    if not (config.f(cfg, "s1.range_min_atr") * atr <= width
            <= config.f(cfg, "s1.range_max_atr") * atr):
        return no("range_width")
    if float(r["vol_ratio"]) < config.f(cfg, "s1.vol_ratio_min"):
        return no("vol_expansion")
    if not bool(r["h_agree"]):
        # §6's own instruction: do not trade from one noisy Hurst estimate.
        return no("hurst_agree")
    h_min = config.f(cfg, "s1.hurst_min")
    if float(r["h_dfa"]) < h_min:
        return no("hurst_trending")

    broken = _broken_level(r, atr)
    if broken is None:
        return no("breakout")
    side, level = broken
    close = float(r["close"])

    extension = (close - level) * side
    max_ext = config.f(cfg, "s1.max_extension_atr") * atr
    if extension > max_ext:
        return no("not_extended")

    return bracket.build(
        strategy=NAME, conditions=CONDITIONS, ts=ts, side=side, close=close, atr=atr,
        stop=level - side * config.f(cfg, "s1.stop_pad_atr") * atr,
        spread_usd=float(r["spread_usd"]), news=bool(r["news_lock"]),
        confidence=_confidence(r, extension=extension, max_ext=max_ext, h_min=h_min, cfg=cfg),
        cfg=cfg, day=day)


def _broken_level(r: pd.Series, atr: float) -> tuple[int, float] | None:
    """Which side of the Asian range the close has cleared, if either.

    §9's delta is reused rather than re-spelled -- `max($0.02, 0.05 x ATR)`.
    A level cleared by less than that has not been cleared.
    """
    delta = reclaim_delta(atr)
    close = float(r["close"])
    if close > float(r["asian_high"]) + delta:
        return 1, float(r["asian_high"])
    if close < float(r["asian_low"]) - delta:
        return -1, float(r["asian_low"])
    return None


def _confidence(r: pd.Series, *, extension: float, max_ext: float, h_min: float,
                cfg: dict[str, Any]) -> float:
    """How far the three continuous conditions were cleared by, averaged.

    **Ordinal, not a probability** -- `suggestion.py` says why, and nothing may
    read it as a win rate. Each leg is the margin over its own threshold scaled
    by a fixed span, so the number is a deterministic function of the row and
    of `config`, with nothing fitted anywhere in it. The extension leg is
    inverted: a break that has barely cleared the level is the better entry.
    """
    vol = (float(r["vol_ratio"]) - config.f(cfg, "s1.vol_ratio_min")) / 0.50
    mem = (float(r["h_dfa"]) - h_min) / 0.25
    room = 1.0 - extension / max_ext if max_ext > 0 else 0.0
    return float(np.clip(np.mean(np.clip([vol, mem, room], 0.0, 1.0)), 0.0, 1.0))
