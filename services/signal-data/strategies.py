"""The Stage 1 candidates, as entry-only functions over minute bars.

Design: docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md §2, §7.

Each strategy is `(bars, *, thresholds) -> Series of +1 / -1 / 0` aligned to
`bars.index`, which is what `backtest.evaluate` consumes. There is no exit
rule: §4's horizons are the exit, and MFE/MAE already say what a stop or a
target would have done without committing to one. Stage 1 is a kill gate and
only has to answer whether there is directional edge at all.

**The prose rule in each docstring is a literal reading of its family, not a
transcription of how anyone actually trades it.** It is a proposal, and
`thresholds_selector.md` Part B is where the trader confirms or rewrites it.

**No threshold here has a default.** Calling a strategy without its numbers
raises `TypeError`, so §6.1 -- nothing is backtested before Part B is
committed -- is enforced by the signature rather than by anyone remembering.

Three traps, all of which produce signal series that look entirely plausible:

  * Scoring a bar against statistics of the session it sits in is lookahead:
    a 09:30 bar judged against the day's own standard deviation has read the
    afternoon. Every window here is trailing.
  * `minute_bars` drops empty minutes, so thirty rows is not thirty minutes.
    Windows are clock-based offsets, matching `backtest.py`'s horizons.
  * A window that spans the overnight break scores NY against Asia. Windows
    are grouped by session and restart at the boundary.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.typing import RollingGroupby

from s1 import TICK


def _window(bars: pd.DataFrame, col: str, window: str, min_bars: int) -> RollingGroupby:
    """Trailing clock window over `col`, restarted at each session boundary.

    `min_bars` is what makes a session's opening bars NaN rather than scored
    against one or two observations, where a standard deviation is either zero
    or meaningless and every z off it is enormous.
    """
    return bars.groupby("session", sort=False)[col].rolling(window, min_periods=min_bars)


def _align(s: pd.Series, bars: pd.DataFrame) -> pd.Series:
    """Drop the group level that groupby-rolling adds, restore bar order."""
    return s.droplevel(0).reindex(bars.index)


def _sides(long: pd.Series, short: pd.Series, bars: pd.DataFrame) -> pd.Series:
    """Two boolean masks to one side series. NaN compares False, so a bar with
    no trailing context is flat rather than accidentally directional."""
    return pd.Series(np.where(long, 1, np.where(short, -1, 0)), index=bars.index).astype("int64")


# --------------------------------------------------------------------------
# State features -- trailing only, and §2's regimes.py reads these too
# --------------------------------------------------------------------------
def delta_z(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Bar delta against its own trailing distribution, in standard deviations.

    A window whose delta never varied has zero spread and no scale to speak
    of; that is NaN, not an infinite outlier.
    """
    r = _window(bars, "delta", window, min_bars)
    mu, sd = _align(r.mean(), bars), _align(r.std(), bars)
    return (bars["delta"] - mu) / sd.where(sd > 0)


def cvd_slope(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Change in session CVD across the trailing window, in contracts.

    The chord, not a fitted line -- it answers "did flow go one way over this
    stretch", which is the question, and it costs nothing.
    """
    r = _window(bars, "cvd", window, min_bars)
    return _align(r.apply(lambda a: a[-1] - a[0], raw=True), bars)


def absorption(bars: pd.DataFrame) -> pd.Series:
    """Contracts traded per tick of price movement.

    A bar that closed where it opened and never traded away is the purest
    absorption there is, so the range floors at one tick. Dividing by zero
    would turn the strongest case into `inf` and then into a dropped row.
    """
    span = ((bars["high"] - bars["low"]) / TICK).clip(lower=1.0)
    return bars["delta"].abs() / span


def bar_imbalance(ticks: pd.DataFrame, *, ratio: float) -> pd.DataFrame:
    """Per-bar diagonal footprint imbalance: buy volume at a price against sell
    volume one tick below it, which is the comparison footprint charts draw.

    Takes TICKS, not bars -- price levels within a bar do not survive OHLC.
    Prices become integer tick levels first, because 99.9 / 0.10 is not 999
    in binary floating point and a float key silently splits a level in two.

    A level with nothing resting opposite is skipped rather than counted as
    infinite imbalance: one lone print is not a stack.
    """
    cell = (
        ticks.assign(
            bar=ticks["timestamp"].dt.floor("1min"),
            lvl=(ticks["price"] / TICK).round().astype("int64"),
            buy=ticks["delta"].clip(lower=0),
            sell=(-ticks["delta"]).clip(lower=0),
        )
        .groupby(["bar", "lvl"], as_index=False)[["buy", "sell"]]
        .sum()
    )
    keyed = cell.set_index(["bar", "lvl"])
    below = pd.MultiIndex.from_arrays([cell["bar"], cell["lvl"] - 1])
    above = pd.MultiIndex.from_arrays([cell["bar"], cell["lvl"] + 1])
    sell_below = keyed["sell"].reindex(below).to_numpy()
    buy_above = keyed["buy"].reindex(above).to_numpy()

    cell["buy_imb"] = (sell_below > 0) & (cell["buy"] >= ratio * sell_below)
    cell["sell_imb"] = (buy_above > 0) & (cell["sell"] >= ratio * buy_above)
    return cell.groupby("bar")[["buy_imb", "sell_imb"]].sum()


# --------------------------------------------------------------------------
# The candidates. Prose is a proposal; numbers are Part B's.
# --------------------------------------------------------------------------
def delta_outlier(bars: pd.DataFrame, *, window: str, min_bars: int, z: float) -> pd.Series:
    """Continuation. A bar whose delta is `z` standard deviations above its
    trailing `window` goes long at that bar's close; `z` below goes short.

    This is the family §4's ~15-20% method dependence hits hardest, because
    the threshold IS a delta magnitude. A5's +/-20% perturbation is not
    optional here.
    """
    s = delta_z(bars, window=window, min_bars=min_bars)
    return _sides(s >= z, s <= -z, bars)


def cvd_divergence(
    bars: pd.DataFrame, *, window: str, min_bars: int, min_slope: float
) -> pd.Series:
    """Mean reversion. Price closes at the high of its trailing `window` while
    CVD fell by at least `min_slope` contracts across that same window: short.
    A new low that buying did not confirm: long.

    The extreme and the flow are measured over the same window on purpose. A
    price extreme judged over one horizon and flow over another is two
    thresholds pretending to be one.
    """
    hi = _align(_window(bars, "close", window, min_bars).max(), bars)
    lo = _align(_window(bars, "close", window, min_bars).min(), bars)
    flow = cvd_slope(bars, window=window, min_bars=min_bars)
    return _sides((bars["close"] <= lo) & (flow >= min_slope), (bars["close"] >= hi) & (flow <= -min_slope), bars)


def absorption_fade(bars: pd.DataFrame, *, min_ratio: float, min_delta: float) -> pd.Series:
    """Fade. A bar trading at least `min_ratio` contracts per tick of range, on
    at least `min_delta` contracts of one-sided flow, means aggressors got
    filled and price did not follow: take the opposite side of the delta.

    **`min_delta` is not a refinement, it is what makes the rule mean what it
    says.** The ratio alone is scale-free -- five contracts into a one-tick
    range scores exactly what five hundred into a hundred-tick range does. On
    the one session available, the highest ratios in the book were 5- and
    6-contract bars in the Globex-open dead zone, which is illiquidity, not
    absorption. Without a size floor this rule selects for an empty market.

    **Fade is an assumption, and it is the one to check first.** The same bar
    reads as continuation if you believe the aggressor is early rather than
    trapped. Part B is where that gets decided, and if it is continuation this
    function is one sign change.
    """
    heavy = (absorption(bars) >= min_ratio) & (bars["delta"].abs() >= min_delta)
    return pd.Series(np.where(heavy, -np.sign(bars["delta"]), 0), index=bars.index).astype("int64")


def footprint_stack(
    ticks: pd.DataFrame, bars: pd.DataFrame, *, ratio: float, min_stack: int
) -> pd.Series:
    """Continuation. At least `min_stack` price levels inside the bar where
    buy volume is `ratio` times the sell volume one tick below, and no level
    imbalanced the other way: long. Mirrored for short.

    Requiring the opposite count to be zero is deliberate. A bar stacked both
    ways is a two-sided fight, not a direction, and it is common.

    Counts levels, not runs. Consecutive stacking is the stricter reading and
    is not implemented -- it is a different rule with its own Part B block.
    """
    imb = bar_imbalance(ticks, ratio=ratio).reindex(bars.index).fillna(0)
    return _sides(
        (imb["buy_imb"] >= min_stack) & (imb["sell_imb"] == 0),
        (imb["sell_imb"] >= min_stack) & (imb["buy_imb"] == 0),
        bars,
    )
