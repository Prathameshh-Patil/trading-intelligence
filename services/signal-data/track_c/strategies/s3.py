"""S3 -- session-VWAP mean reversion, in a low-memory compressed-volatility tape.

THE IDEA, IN ONE LINE. In a session with no memory (H well below 0.5) and
volatility below its own daily baseline, a price two standard deviations from
the session's volume-weighted mean is more likely to come back to it than to
keep going.

WHY IT IS THE ONE STRATEGY WITH A HARD TIME STOP. S1, S2 and S4 all trade an
event -- a break, a failure, an expansion -- and an event that has not resolved
is still an event. S3 trades a *statistical* claim about a session, and a
reversion that has not happened within two hours is evidence the claim was
false, not that it is early. The time stop is therefore part of the strategy,
not a risk overlay, and it exits at the mid **minus** the spread and slippage
like any other market order (`fills.exit_price`) -- a free exit at the mid is
how a time-stopped strategy comes to look profitable.

WHY IT IS THE ONLY STRATEGY THAT DEPENDS ON THE VOLUME PROXY. Session VWAP is
weighted by `ticks`, which is a QUOTE-UPDATE COUNT and not traded size --
`levels.session_vwap` states the assumption and `spot.py` refuses to call the
column `volume`. So if the proxy is bad, S3's result is the one that is wrong,
and that is worth knowing in advance of the run rather than after it.

REGIME PARTITION. S3 requires H <= 0.45 and `vol_ratio <= 0.90`; S1 and S4 both
require H >= 0.50 and (S1) expansion. **The three cannot fire on the same bar**
-- which is the point of building four strategies rather than four variants of
one, and is asserted in `test_strategies.py` rather than left as a claim.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import fsm
from track_c import bracket, config, context
from track_c.suggestion import Refusal, Suggestion, refuse

NAME = "s3"

CONDITIONS: tuple[str, ...] = (
    "window", "news_lock", "inputs", "hurst_agree", "hurst_reverting",
    "vol_compression", "z_extreme", *bracket.TAIL,
)

INPUTS: tuple[str, ...] = ("close", "atr_usd", "vol_ratio", "h_dfa", "h_vt", "vwap_z",
                           "s3_dc_high", "s3_dc_low", "spread_usd")


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
    # `vwap_z` is NaN until `min_session_bars` into the session, so the
    # admissibility check is also what enforces "two hours of session first".
    if not context.finite(r, INPUTS):
        return no("inputs")
    if not bool(r["h_agree"]):
        return no("hurst_agree")
    if float(r["h_dfa"]) > config.f(cfg, "s3.hurst_max"):
        return no("hurst_reverting")
    if float(r["vol_ratio"]) > config.f(cfg, "s3.vol_ratio_max"):
        return no("vol_compression")

    z = float(r["vwap_z"])
    if abs(z) < config.f(cfg, "s3.z_min"):
        return no("z_extreme")

    # Fade the excursion: below the mean, buy. The stop sits behind the last
    # hour's extreme, which is the only structure a mean-reversion trade has.
    side = -1 if z > 0 else 1
    atr = float(r["atr_usd"])
    pad = config.f(cfg, "s3.stop_pad_atr") * atr
    structure = float(r["s3_dc_low"]) if side > 0 else float(r["s3_dc_high"])
    return bracket.build(
        strategy=NAME, conditions=CONDITIONS, ts=ts, side=side, close=float(r["close"]),
        atr=atr, stop=structure - side * pad,
        spread_usd=float(r["spread_usd"]), news=bool(r["news_lock"]),
        confidence=_confidence(r, z=z, cfg=cfg), cfg=cfg, day=day)


def _confidence(r: pd.Series, *, z: float, cfg: dict[str, Any]) -> float:
    """How extreme, how reverting, how compressed. Ordinal, not a probability."""
    stretch = (abs(z) - config.f(cfg, "s3.z_min")) / 2.0
    mem = (config.f(cfg, "s3.hurst_max") - float(r["h_dfa"])) / 0.25
    calm = (config.f(cfg, "s3.vol_ratio_max") - float(r["vol_ratio"])) / 0.40
    return float(np.clip(np.mean(np.clip([stretch, mem, calm], 0.0, 1.0)), 0.0, 1.0))


def time_stop_bars(cfg: dict[str, Any]) -> int:
    """§S3's hard time stop, read by the engine. The other three have none."""
    return config.i(cfg, "s3.time_stop_bars")
