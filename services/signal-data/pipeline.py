"""Runs both lanes and produces one S13 frame. The seam's only consumer-side proof.

WHY THIS EXISTS. `frame.require` describes a frame; until something builds one
that satisfies it and something else reads one, the seam is a declaration
rather than a contract. The first assembly found a three-way disagreement
about `r_hat_60` -- see `contracts.md`'s S13 amendment -- which frozen column
names had not prevented, because nothing had yet tried to satisfy both sides.

WHAT IS NaN HERE, AND WHY THAT IS CORRECT RATHER THAN INCOMPLETE.

  p_build, p_expand         §7's HMM. E4 has not run and its prediction is
                            unwritten; a column is never dropped to signal a
                            dead feature, so it carries NaN.
  swept_level, reclaim_dt_s,
  wick_w                    §9 needs TICKS, and E0 has not delivered any. The
                            detector exists and is tested; it has nothing to
                            read yet.
  spread_bp                 GC has no usable spread -- one tick, degenerate.
                            Spot will fill it.

**A NaN here means "not measured", never "zero".** `fsm.exclusions` reads these
by name and a zero would pass a `>` gate that a NaN correctly fails.

WHY HURST IS STRIDED. A rolling Hurst recomputes seven log-log regressions per
bar. Measured 2026-09-18 on 6,024 bars: every-bar is ~8s, stride-12 is ~0.7s
and gives the same series forward-filled at 5-minute resolution against a
15-minute feature. Measured, not guessed -- and the stride is an argument so a
caller who wants every bar can pay for it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features import frame, hurst, structure, volatility

# §2's horizon: twelve 5-minute bars make an hour.
BARS_PER_HOUR = 12

# §6 asks for a 15-minute Hurst. On 5-minute bars that is three bars, which is
# not three scales -- so the window is stated in BARS and sized to hold the
# scale ladder, and the "15m" in the column name is the spec's label for the
# feature rather than a claim about this window. See `daily_updates/2026-09-18`
# §12: coarse bars cannot support §6 as written, and E0's granularity choice is
# what actually resolves it.
HURST_WINDOW = 512
HURST_STRIDE = 12

# `r_ratio`'s trailing median. Twenty sessions of 5-minute bars.
RATIO_WINDOW = 288 * 20


def _rolling_hurst(logprice: pd.Series, *, window: int, stride: int) -> pd.DataFrame:
    """DFA and variance-time over a trailing window, computed every `stride` bars."""
    idx = range(window, len(logprice), stride)
    rows = [
        (logprice.index[i],
         hurst.hurst_dfa(logprice.to_numpy()[i - window:i]),
         hurst.hurst_vt(logprice.to_numpy()[i - window:i]))
        for i in idx
    ]
    out = pd.DataFrame(rows, columns=["ts", "h_dfa_15m", "h_vt_15m"]).set_index("ts")
    return out.reindex(logprice.index).ffill()


def build(bars: pd.DataFrame, *, events: pd.DatetimeIndex,
          hurst_stride: int = HURST_STRIDE) -> pd.DataFrame:
    """Assemble the S13 frame from bars. Returns a frame `frame.require` accepts.

    `bars` is S9's shared core -- `open, high, low, close, session` on a UTC
    index -- plus `spread_bp` where the instrument has one.
    """
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError(f"bars need a DatetimeIndex, got {type(bars.index).__name__}")
    ts = bars.index
    out = pd.DataFrame(index=ts)
    out["ts"] = ts
    out["mid"] = bars["close"]
    out["spread_bp"] = bars.get("spread_bp", np.nan)

    for n in (12, 48, 288):
        out[f"sigma_yz_{n}"] = volatility.yang_zhang(bars, n=n)

    # One GARCH fit over the whole frame, then its conditional variance path.
    # Refitting per bar would be the honest thing in a walk-forward and is
    # `tuning.folds`' job; here the fit is a feature, not a result.
    r = np.diff(np.log(bars["close"].to_numpy()))
    fit = volatility.garch_fit(r)
    s2 = volatility._garch_variance(r, fit.omega, fit.alpha, fit.beta)
    out["sigma_garch"] = pd.Series(np.sqrt(s2), index=ts[1:]).reindex(ts)

    sigma_60 = [
        volatility.combine_sigma(
            sigma_yz=volatility.yz_sigma_h(yz, m=BARS_PER_HOUR),
            sigma_garch=volatility.garch_sigma_h(sigma2_t=g**2, params=fit, m=BARS_PER_HOUR))
        if np.isfinite(yz) and np.isfinite(g) else np.nan
        for yz, g in zip(out["sigma_yz_12"], out["sigma_garch"], strict=True)
    ]
    out["r_hat_60_usd"] = [
        volatility.r_hat_60(price=p, sigma_60=s) if np.isfinite(s) else np.nan
        for p, s in zip(bars["close"], sigma_60, strict=True)
    ]
    out["r_ratio"] = volatility.r_ratio(out["r_hat_60_usd"], window=RATIO_WINDOW)

    h = _rolling_hurst(np.log(bars["close"]), window=HURST_WINDOW, stride=hurst_stride)
    out["h_dfa_15m"] = h["h_dfa_15m"]
    out["h_vt_15m"] = h["h_vt_15m"]
    out["h_agree"] = [
        hurst.hurst_agree(a, b) for a, b in zip(h["h_dfa_15m"], h["h_vt_15m"], strict=True)
    ]

    out["session"] = bars["session"]
    out["phase"] = structure.in_window(ts)
    out["news_lockout"] = structure.news_lockout(ts, events)

    # §7 and §9: see the module docstring. Not measured, never zero.
    for col in ("p_build", "p_expand", "swept_level", "reclaim_dt_s", "wick_w"):
        out[col] = np.nan

    out = out[list(frame.FEATURES)]
    frame.require(out)
    return out
