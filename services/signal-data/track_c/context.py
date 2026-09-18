"""One pass over the bars that produces every number the four strategies read.

WHY THE FEATURES ARE BUILT ONCE AND NOT PER BAR. The strategies are evaluated
bar by bar -- they are event-driven, which is the whole reason Track C is not
`backtest.py` -- but the quantities they read are rolling statistics, and a
rolling statistic recomputed inside a per-bar loop is the same arithmetic done
`window` times. So: vectorise the features, loop the decisions.

**The loop may only look at row `i` and rows before it.** That is not enforced
by the loop; it is enforced here, by every column being causal at construction
(`levels.py`'s docstring lists the three places lookahead would enter). A
strategy that indexes `ctx.iloc[i]` therefore cannot see the future even by
accident, which is the property that makes the event loop safe to write
plainly.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from features import structure
from instruments import Instrument
from track_c import config, levels, regime

REQUIRED_BARS: tuple[str, ...] = ("open", "high", "low", "close", "ticks", "spread_bp", "session")


def build(bars: pd.DataFrame, inst: Instrument, cfg: dict[str, Any],
          *, events: pd.DatetimeIndex) -> pd.DataFrame:
    """Every per-bar input, aligned to `bars.index`.

    `events` is the economic calendar, and it is required rather than
    defaulted: an empty index is a real answer ("nothing scheduled") and a
    missing one would silently disable §12's lockout, which is the one filter
    whose failure is invisible in the output.
    """
    missing = [c for c in REQUIRED_BARS if c not in bars.columns]
    if missing:
        raise ValueError(f"Track C needs {missing} on the bar frame; `spot.resample` "
                         "produces all of them and a frame without them is not spot bars")
    if not bars.index.is_monotonic_increasing:
        raise ValueError("bars must be in time order; out of order, every rolling window "
                         "is a window over a shuffled sample")

    idx = pd.DatetimeIndex(bars.index)
    ctx = pd.DataFrame(index=idx)
    ctx[["open", "high", "low", "close"]] = bars[["open", "high", "low", "close"]]
    ctx["atr_usd"] = regime.atr_usd(bars, inst, window=config.get(cfg, "regime.atr_window"),
                                    min_bars=config.i(cfg, "regime.atr_min_bars"))
    ctx["vol_ratio"] = regime.vol_ratio(bars, fast=config.i(cfg, "regime.yz_fast_bars"),
                                        slow=config.i(cfg, "regime.yz_slow_bars"))
    ctx[["h_dfa", "h_vt", "h_agree"]] = regime.hurst_pair(
        bars, window=config.i(cfg, "regime.hurst_window_bars"),
        step=config.i(cfg, "regime.hurst_step_bars"))

    ctx[["asian_high", "asian_low"]] = levels.asian_range(bars, **_asian_clock(cfg))
    ctx[["pdh", "pdl"]] = levels.prior_day(bars)
    ctx["vwap"] = levels.session_vwap(bars)
    ctx["vwap_z"] = levels.vwap_z(bars, ctx["vwap"],
                                  min_bars=config.i(cfg, "s3.min_session_bars"))
    ctx["bb_width"] = levels.bb_width(bars, n=config.i(cfg, "s4.bb_bars"),
                                      k=config.f(cfg, "s4.bb_k"))
    lookback = config.i(cfg, "regime.pct_lookback_bars")
    ctx["bb_pct"] = regime.pct_rank(ctx["bb_width"], lookback=lookback)
    ctx["ticks_pct"] = regime.pct_rank(bars["ticks"].astype(float), lookback=lookback)
    ctx[["s4_dc_high", "s4_dc_low"]] = levels.donchian(bars, n=config.i(cfg, "s4.bb_bars"))
    ctx[["s3_dc_high", "s3_dc_low"]] = levels.donchian(
        bars, n=config.i(cfg, "s3.stop_lookback_bars"))

    # §12. The internal 5-minute lock is the one the strategies trade against;
    # the hard 2-minute lock is a subset of it and is carried separately so a
    # report can say which of the two refused a bar.
    ctx["news_lock"] = structure.news_lockout(
        idx, events, minutes=config.i(cfg, "news.internal_lockout_min")).to_numpy()
    ctx["news_hard"] = structure.news_lockout(
        idx, events, minutes=config.i(cfg, "news.hard_lockout_min")).to_numpy()

    for s in config.STRATEGIES:
        ctx[f"in_{s}"] = structure.in_window(idx, config.windows(cfg, s)).to_numpy()

    ctx["spread_usd"] = bars["spread_bp"] / 1e4 * bars["close"]
    ctx["session"] = bars["session"]
    return ctx


def _asian_clock(cfg: dict[str, Any]) -> dict[str, Any]:
    """§`session`'s Asian window, as `levels.asian_range` wants it."""
    return {"start": config.clock(config.get(cfg, "session.asian_start")),
            "end": config.clock(config.get(cfg, "session.asian_end"))}


def finite(row: pd.Series, names: tuple[str, ...]) -> bool:
    """Are all of these inputs real numbers on this row?

    Layer 1 of `TRACK_C_ENGINE.md` §5: a non-finite input refuses the bar
    rather than propagating a NaN into a comparison, where it would silently
    evaluate False and be counted as a condition that failed on the market
    rather than on the warm-up. Every strategy's first real condition.
    """
    return bool(pd.notna(row[list(names)]).all())
