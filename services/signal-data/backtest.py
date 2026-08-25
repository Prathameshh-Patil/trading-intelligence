"""One strategy over a bar frame -> the metric set the selector design pins.

Design: docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md §4.

Two things this file exists to keep honest:

  * Horizons are measured on the CLOCK, not on row offsets. Minute bars drop
    empty minutes, so `bars.iloc[i + 5]` is not five minutes after `bars.iloc[i]`.
  * Every number is reported with its N, and a distribution is reported as a
    distribution. These are fat-tailed; a mean on its own is a lie.

Fill assumption, stated once: an entry fills at the CLOSE of the bar that
signalled it. The signal must therefore be computable from that bar's completed
data -- a strategy reading its own bar's close is fine, reading the next bar's
anything is lookahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from s1 import TICK, TICK_VALUE

HORIZONS = (5, 15, 30)  # minutes
MIN_SAMPLES = 30        # design §6.5: below this, report but do not act


def evaluate(
    bars: pd.DataFrame, entries: pd.Series, horizons: tuple[int, ...] = HORIZONS
) -> pd.DataFrame:
    """One row per entry: realized move at each horizon, plus MFE/MAE, in ticks.

    `entries` is aligned to `bars.index` and carries the side: +1 long, -1
    short, 0 no trade. Horizons never cross a session boundary -- a position
    held through the overnight break is a different trade than the one tested.
    """
    if not entries.index.isin(bars.index).all():
        raise ValueError("entries carry timestamps that are not bars")

    span = max(horizons)
    rows = []
    fired = entries[entries != 0]
    for t, side in zip(pd.DatetimeIndex(fired.index), fired.to_numpy(), strict=True):
        entry = bars.at[t, "close"]
        window = bars.loc[t : t + pd.Timedelta(minutes=span)]
        window = window[window["session"] == bars.at[t, "session"]].iloc[1:]
        if window.empty:
            continue  # entered at the session's last bar; nothing to measure

        row = {"t": t, "side": int(side), "entry": entry, "bars_seen": len(window)}
        for h in horizons:
            leg = window.loc[: t + pd.Timedelta(minutes=h)]
            if leg.empty:  # session ended inside this horizon
                row[f"move_{h}m"] = row[f"mfe_{h}m"] = row[f"mae_{h}m"] = np.nan
                continue
            row[f"move_{h}m"] = side * (leg["close"].iloc[-1] - entry) / TICK
            # MFE is the best it ever looked, MAE the worst. Both stay signed
            # in the trade's own favour direction, so MAE is negative only when
            # the trade actually went adverse -- a trade that never did has a
            # positive MAE, and flooring it at zero would hide exactly the
            # trades that need no stop.
            row[f"mfe_{h}m"] = side * ((leg["high"].max() if side > 0 else leg["low"].min()) - entry) / TICK
            row[f"mae_{h}m"] = side * ((leg["low"].min() if side > 0 else leg["high"].max()) - entry) / TICK
        rows.append(row)

    cols = ["t", "side", "entry", "bars_seen"]
    cols += [f"{k}_{h}m" for h in horizons for k in ("move", "mfe", "mae")]
    return pd.DataFrame(rows, columns=cols)


def summarize(trades: pd.DataFrame, horizon: int = HORIZONS[0]) -> dict[str, float]:
    """Distribution of one horizon's outcome. Never a point estimate alone."""
    m = trades[f"move_{horizon}m"].dropna()
    if m.empty:
        return {"n": 0, "thin": True}
    p10, p25, p50, p75, p90 = m.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    return {
        "n": len(m),
        "thin": len(m) < MIN_SAMPLES,
        "hit_rate": float((m > 0).mean()),
        "median": float(p50),
        "iqr_lo": float(p25),
        "iqr_hi": float(p75),
        "p10": float(p10),
        "p90": float(p90),
        "expectancy_ticks": float(m.mean()),
        "expectancy_usd": float(m.mean() * TICK_VALUE),
        "mfe_median": float(trades[f"mfe_{horizon}m"].median()),
        "mae_median": float(trades[f"mae_{horizon}m"].median()),
    }


def report(trades: pd.DataFrame, horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    """The metric set across horizons, one row each, N always present."""
    return pd.DataFrame([summarize(trades, h) for h in horizons], index=[f"{h}m" for h in horizons])


def random_entries(bars: pd.DataFrame, like: pd.Series, seed: int) -> pd.Series:
    """The §6.3 stage-1 null: same count, same side mix, same holding period.

    Matching the side mix matters. A long-biased strategy measured against a
    coin flip in a rising market beats it on the drift alone, and that is not
    an edge.
    """
    sides = like[like != 0]
    rng = np.random.default_rng(seed)
    when = rng.choice(len(bars), size=len(sides), replace=False)
    return pd.Series(rng.permutation(sides.to_numpy()), index=bars.index[np.sort(when)])
