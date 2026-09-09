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

from collections.abc import Sequence
from typing import Literal, NamedTuple

import numpy as np
import pandas as pd

from instruments import Instrument

HORIZONS = (5, 15, 30)  # minutes
MIN_SAMPLES = 30        # design §6.5: below this, report but do not act


def session_ends(bars: pd.DataFrame) -> pd.Series:
    """Last bar of each session, so a horizon can be told "ran out of session"
    apart from "ran out of bars" -- a gap in the tape is not a short leg."""
    return pd.Series(bars.index, index=bars.index).groupby(bars["session"], sort=False).last()


def evaluate(
    bars: pd.DataFrame,
    entries: pd.Series,
    inst: Instrument,
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    """One row per entry: realized move at each horizon, plus MFE/MAE, in ticks of `inst`.

    `entries` is aligned to `bars.index` and carries the side: +1 long, -1
    short, 0 no trade. Horizons never cross a session boundary -- a position
    held through the overnight break is a different trade than the one tested.

    A horizon whose session ends before it does is NaN, not a short leg. The
    difference is invisible and it matters: a trade entered ten minutes before
    the close would otherwise contribute its ten-minute move to the 30m column
    and be averaged in as though it had run the full half hour. On July 2026
    that is 2.2% of bars at 30m against 0.4% at 5m, so it biases the long
    horizon toward zero -- exactly where the horizon question is decided.
    """
    if not entries.index.isin(bars.index).all():
        raise ValueError("entries carry timestamps that are not bars")

    span = max(horizons)
    ends = session_ends(bars)
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
            mark = t + pd.Timedelta(minutes=h)
            leg = window.loc[:mark]
            if leg.empty or ends[bars.at[t, "session"]] < mark:
                row[f"move_{h}m"] = row[f"mfe_{h}m"] = row[f"mae_{h}m"] = np.nan
                continue
            row[f"move_{h}m"] = side * (leg["close"].iloc[-1] - entry) / inst.tick
            # MFE is the best it ever looked, MAE the worst. Both stay signed
            # in the trade's own favour direction, so MAE is negative only when
            # the trade actually went adverse -- a trade that never did has a
            # positive MAE, and flooring it at zero would hide exactly the
            # trades that need no stop.
            row[f"mfe_{h}m"] = side * ((leg["high"].max() if side > 0 else leg["low"].min()) - entry) / inst.tick
            row[f"mae_{h}m"] = side * ((leg["low"].min() if side > 0 else leg["high"].max()) - entry) / inst.tick
        rows.append(row)

    cols = ["t", "side", "entry", "bars_seen"]
    cols += [f"{k}_{h}m" for h in horizons for k in ("move", "mfe", "mae")]
    return pd.DataFrame(rows, columns=cols)


def summarize(
    trades: pd.DataFrame, inst: Instrument, horizon: int = HORIZONS[0]
) -> dict[str, float]:
    """Distribution of one horizon's outcome. Never a point estimate alone.

    `expectancy_usd` is NaN where the instrument has no `tick_value` -- USD per
    tick per contract is a futures fact and spot has no contract. NaN rather
    than the tick number repeated, which would read as dollars.
    """
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
        "expectancy_usd": float(m.mean() * inst.tick_value) if inst.tick_value is not None else np.nan,
        "mfe_median": float(trades[f"mfe_{horizon}m"].median()),
        "mae_median": float(trades[f"mae_{horizon}m"].median()),
    }


def report(
    trades: pd.DataFrame, inst: Instrument, horizons: tuple[int, ...] = HORIZONS
) -> pd.DataFrame:
    """The metric set across horizons, one row each, N always present."""
    return pd.DataFrame(
        [summarize(trades, inst, h) for h in horizons], index=[f"{h}m" for h in horizons]
    )


def first_touch(
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    inst: Instrument,
    *,
    target: float,
    stop: float,
    horizon: int,
    ties: Literal["stop", "target"] = "stop",
) -> pd.Series:
    """Which came first, +target ticks or -stop ticks: +1 target, -1 stop, 0 neither.

    **MFE and MAE cannot answer this and it is not obvious that they cannot.**
    A trade with `mfe=+50` and `mae=-25` either ran to its target or was
    stopped out on the way; both outcomes produce the same two numbers,
    because the order is the whole question and the order is not in them.
    Reading a hit rate off MFE alone counts every stopped-out trade as a win.

    **A same-bar tie resolves to the stop by default.** When one bar's high
    clears the target and its low clears the stop, the tape's order is not in
    the bar and `ties="stop"` reports the worse of the two, making `p_target` a
    LOWER bound. `ties="target"` is the same measurement at the other extreme,
    and it exists so the width of that band can be reported rather than
    assumed small -- the truth is inside it and bars cannot say where.

    The band is widest exactly where the stop is tight relative to the bar
    range: at ATR 40 a 20-tick stop is about half a typical bar, which
    `features/regime_filter.py` already flags as the fragility Week 1 D4 must
    settle at tick resolution. **A wide band there is not a defect of this
    function; it is the honest size of what bar data knows.**

    NaN when the session ends inside the horizon, matching `evaluate`: a leg
    the tape never offered is not a leg that went nowhere.
    """
    ex = excursions(bars, trades, inst, horizon=horizon)
    return first_touch_from(ex, target=target, stop=stop, ties=ties)


class Excursions(NamedTuple):
    """One row per leg, one column per bar after entry, in ticks.

    Signed in the trade's own favour, so `up` is how good it ever got and `dn`
    how bad, and both are read the same way for a long and a short.
    """

    up: np.ndarray     # favourable; -inf past the end of a short window
    dn: np.ndarray     # adverse; +inf past it, so neither barrier is ever hit there
    valid: np.ndarray  # False where the tape never offered the leg
    legs: pd.Index     # the legs' own index, so an answer aligns with the frame it came from


def excursions(
    bars: pd.DataFrame, trades: pd.DataFrame, inst: Instrument, *, horizon: int
) -> Excursions:
    """The window every bracket at one horizon is judged over, built once.

    **The window depends on `(t, side, horizon)` and not on where the barriers
    are**, so a sweep that re-slices it per bracket does the same work 48 times
    -- 24 target/stop pairs, twice for the tie band. `m1_sweep` computes this
    once per cell and horizon and answers the whole grid off it.

    Positional slicing is safe here for the reason the session filter it
    replaces is redundant: sessions are contiguous, so if `session` runs past
    `mark` then every bar between the two belongs to it, and if it does not the
    leg is NaN anyway. Gaps in the tape are handled by length, not by mask -- a
    leg with fewer bars than the horizon allows is padded with infinities that
    no barrier can reach.
    """
    idx = bars.index
    t = pd.DatetimeIndex(trades["t"])
    mark = t + pd.Timedelta(minutes=horizon)
    pos = idx.searchsorted(t)
    span = idx.searchsorted(mark, side="right") - pos - 1  # bars strictly after entry
    ends = session_ends(bars)
    valid = (span > 0) & (ends.reindex(bars["session"].to_numpy()[pos]).to_numpy() >= mark)

    width = max(int(span.max()), 1) if len(span) else 1
    take = pos[:, None] + 1 + np.arange(width)
    inside = np.arange(width) < span[:, None]
    take = np.where(inside, take, 0)  # clamp: masked out a line below

    side = trades["side"].to_numpy()[:, None]
    entry = trades["entry"].to_numpy()[:, None]
    high, low = bars["high"].to_numpy()[take], bars["low"].to_numpy()[take]
    fav, adv = np.where(side > 0, high, low), np.where(side > 0, low, high)
    return Excursions(
        up=np.where(inside, side * (fav - entry) / inst.tick, -np.inf),
        dn=np.where(inside, side * (adv - entry) / inst.tick, np.inf),
        valid=valid,
        legs=trades.index,
    )


def first_touch_from(
    ex: Excursions, *, target: float, stop: float,
    ties: Literal["stop", "target"] = "stop",
) -> pd.Series:
    """`first_touch`'s answer for one bracket, off a window already built.

    Same three-valued encoding and the same tie rule -- this is where they are
    defined, and `first_touch` is the single-bracket spelling of it. There is
    one convention in this file and it lives here.
    """
    hit_t = _first_true(ex.up >= target)
    hit_s = _first_true(ex.dn <= -stop)
    got_t, got_s = hit_t >= 0, hit_s >= 0

    out = np.zeros(len(ex.valid))
    out[got_t & ~got_s] = 1
    out[got_s & ~got_t] = -1
    both = got_t & got_s
    out[both] = np.where(hit_t[both] < hit_s[both], 1,
                         np.where(hit_t[both] > hit_s[both], -1,
                                  -1 if ties == "stop" else 1))
    out[~ex.valid] = np.nan
    return pd.Series(out, index=ex.legs, dtype="float64")


def _first_true(hit: np.ndarray) -> np.ndarray:
    """Column of each row's first True, or -1 where the row has none."""
    return np.where(hit.any(axis=1), hit.argmax(axis=1), -1)


def reach_table(
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    inst: Instrument,
    pairs: Sequence[tuple[float, float]],
    horizon: int = HORIZONS[0],
) -> pd.DataFrame:
    """One row per (target, stop) in ticks: how often the target came first, with N.

    This is the whole of the pip forecast the product promises, in the only
    form the data supports -- a base rate conditional on a bucket the caller
    chose, not a prediction of how far this particular trade travels. Bucket
    by grouping `trades` before calling; nothing here picks the buckets, and
    nothing here picks a pass line either. Design:
    docs/superpowers/specs/2026-09-05-live-signal-pipeline-design.md §6.3.
    """
    rows = []
    for target, stop in pairs:
        touch = first_touch(
            bars, trades, inst, target=target, stop=stop, horizon=horizon
        ).dropna()
        best = first_touch(
            bars, trades, inst, target=target, stop=stop, horizon=horizon, ties="target"
        ).dropna()
        n = len(touch)
        rows.append(
            {
                "target": target,
                "stop": stop,
                "n": n,
                "thin": n < MIN_SAMPLES,
                "p_target": float((touch == 1).mean()) if n else np.nan,
                # The same number with same-bar ties read the other way. Report
                # the pair, never the midpoint: bars do not know where in the
                # band the truth is, and averaging invents a precision.
                "p_target_max": float((best == 1).mean()) if n else np.nan,
                "p_stop": float((touch == -1).mean()) if n else np.nan,
                "p_neither": float((touch == 0).mean()) if n else np.nan,
            }
        )
    return pd.DataFrame(rows)


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
