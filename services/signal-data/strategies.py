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

**Every tick-denominated function here takes an `Instrument`** -- see
`instruments.py` -- and the two that also read flow call `require_flow` first.
That guard is not redundant with the missing column it would otherwise trip
over: an MT5 spot feed carries a `volume` column holding a TICK COUNT, so a
frame from a flow-less instrument can satisfy every column check and still
have no aggregate volume in it. The KeyError is luck; the guard is the rule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.typing import RollingGroupby

from instruments import Instrument, require_flow


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


def absorption(bars: pd.DataFrame, inst: Instrument) -> pd.Series:
    """Contracts traded per tick of price movement.

    A bar that closed where it opened and never traded away is the purest
    absorption there is, so the range floors at one tick. Dividing by zero
    would turn the strongest case into `inf` and then into a dropped row.
    """
    require_flow(inst)
    span = ((bars["high"] - bars["low"]) / inst.tick).clip(lower=1.0)
    return bars["delta"].abs() / span


def bar_imbalance(ticks: pd.DataFrame, inst: Instrument, *, ratio: float) -> pd.DataFrame:
    """Per-bar diagonal footprint imbalance: buy volume at a price against sell
    volume one tick below it, which is the comparison footprint charts draw.

    Takes TICKS, not bars -- price levels within a bar do not survive OHLC.
    Prices become integer tick levels first, because 99.9 / 0.10 is not 999
    in binary floating point and a float key silently splits a level in two.

    A level with nothing resting opposite is skipped rather than counted as
    infinite imbalance: one lone print is not a stack.
    """
    require_flow(inst)
    cell = (
        ticks.assign(
            bar=ticks["timestamp"].dt.floor("1min"),
            lvl=(ticks["price"] / inst.tick).round().astype("int64"),
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


def absorption_fade(
    bars: pd.DataFrame, inst: Instrument, *, min_ratio: float, min_delta: float
) -> pd.Series:
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
    heavy = (absorption(bars, inst) >= min_ratio) & (bars["delta"].abs() >= min_delta)
    return pd.Series(np.where(heavy, -np.sign(bars["delta"]), 0), index=bars.index).astype("int64")


def footprint_stack(
    ticks: pd.DataFrame, bars: pd.DataFrame, inst: Instrument, *, ratio: float, min_stack: int
) -> pd.Series:
    """Continuation. At least `min_stack` price levels inside the bar where
    buy volume is `ratio` times the sell volume one tick below, and no level
    imbalanced the other way: long. Mirrored for short.

    Requiring the opposite count to be zero is deliberate. A bar stacked both
    ways is a two-sided fight, not a direction, and it is common.

    Counts levels, not runs. Consecutive stacking is the stricter reading and
    is not implemented -- it is a different rule with its own Part B block.
    """
    imb = bar_imbalance(ticks, inst, ratio=ratio).reindex(bars.index).fillna(0)
    return _sides(
        (imb["buy_imb"] >= min_stack) & (imb["sell_imb"] == 0),
        (imb["sell_imb"] >= min_stack) & (imb["buy_imb"] == 0),
        bars,
    )


# --------------------------------------------------------------------------
# Track B. SIGNATURES COMMITTED, BODIES NOT WRITTEN -- strategy-split.md §3
# point 4 and §4.
#
# These three exist as stubs on day one so two people can fill in disjoint
# bodies in this file without either appending to a moving target. Order,
# names and parameter lists change only at standup; `m4_*` is contested
# (ARCHITECTURE §7) and is deliberately absent rather than reserved.
#
# **All three are NON-DIRECTIONAL, and that changes what the return value
# means.** They return +1 where the rule fires and 0 where it does not, never
# -1, so `backtest.evaluate` consumes them unchanged -- but the `move_*`
# columns it produces are then a signed quantity for an unsigned claim, and
# the measurement reads |move|, `mfe` and the reach table off them. Reading a
# hit rate off `move > 0` here is answering a question none of the three asks.
# --------------------------------------------------------------------------
def m1_geometry(bars: pd.DataFrame, inst: Instrument, *, side: int) -> pd.Series:
    """M1, the geometry frontier: enter every bar, and let the sweep decide.

    ARCHITECTURE §4.4. The rule has no entry condition on purpose -- M1 asks
    what `(target, stop, horizon)` has positive EV per
    `(atr_bp x phase x side)`, which is a property of the tape rather than of
    a signal. **It runs first because M2's brackets are read off its surface
    rather than guessed**, and because its output is the corrected null every
    later lift in this track is quoted against.

    The grid is swept at the CALL SITE, through `backtest.reach_table` over
    the bucketed legs. It is not a parameter here, and it must be committed to
    Prathamesh in a commit before the sweep runs (split.md §7) -- a grid
    widened after the surface is visible is a fit with extra steps.
    """
    raise NotImplementedError("M1 -- step 2, and the geometry grid is pre-committed first")


def m2_vol_momentum(
    bars: pd.DataFrame, inst: Instrument, *, window: str, min_bars: int, slope_min: float
) -> pd.Series:
    """M2, vol momentum and compression: fire where realized vol is EXPANDING.

    ARCHITECTURE §4.4. Signed `rv_slope` over the trailing `window`, against
    the ATR-matched null -- `slope_min` is the cut that separates EXPANDING
    from STABLE, and its mirror below zero is CONTRACTING. The claim is about
    MAGNITUDE, `P(|move| >= T within H)`, which is why the return is +1/0.

    **This does not contradict `horizon.py`.** A price series that is a random
    walk in direction can have entirely predictable scale, and only the first
    of those was measured. That is the highest prior of the four candidates
    and it is also the one most likely to be already in the price of the
    bracket, so the null is the thing to get right here, not the feature.

    Runs on the training half only: it selects, so it costs out-of-sample data
    (ARCHITECTURE §6).
    """
    raise NotImplementedError("M2 -- step 4, and it waits on M1's corrected null")


def m3_session_event(
    bars: pd.DataFrame, inst: Instrument, *, phases: tuple[str, ...], event_window_minutes: int
) -> pd.Series:
    """M3, session and event conditioning: fire inside `phases`, or near an event.

    ARCHITECTURE §4.4. Prathamesh's, and the clock lane's whole vertical --
    `session_phase` and `event_proximity` come from `features/portable.py`.
    Needs no market data beyond the bars already on disk, which is what makes
    the entire clock lane testable before a spot vendor is chosen.

    **The result is only a finding if it survives the 2025-01..09 against
    2025-10..2026-07 split**, the way the 50+ ATR bucket held 0.2000 -> 0.1989
    while the headline moved 2.2x. A phase profile that does not survive it is
    a description of 2025.

    The six phase boundaries in UTC, the event window, and the split date are
    all pre-committed to Varad before this runs (split.md §7).

    `phases` is the arm being tested and it is deliberately a parameter rather
    than a constant: the claim "London-NY carries a lift" is one call and the
    claim "Asia does not" is another, against the same null, and neither gets
    to quietly become the other. Passing `()` runs the event arm alone.

    `event_window_minutes=0` runs the phase arm alone. **Zero is off, not
    "instant only"** -- a zero-width window matches a bar only on an exact
    nanosecond and would report the event arm as dead rather than as absent.

    The two arms are OR'd, per §4.4's "fire inside `phases`, or near an event".
    They are separable by the two switches above, and clock-lane.md pre-commits
    that all three cuts -- phase-only, event-only, and the union -- are
    reported together, so the union cannot be chosen after the fact as the one
    that looked best.

    The calendar is not a parameter and cannot be. The signature is frozen
    (split.md §3 point 4) and `calendars.load()` is the right answer anyway:
    the BLS and FOMC schedules are public fact, not a tunable, and a caller
    free to pass its own calendar is a caller free to drop the releases that
    went the wrong way.
    """
    # Imported inside the body on purpose. `features.expansion` imports
    # `_align` and `_window` from this module, so a module-level import of
    # `features.portable` -- which imports expansion -- closes a cycle through
    # a partially initialised `strategies`. Hoisting `_window` into its own
    # module would fix it properly and is a shared-spine change, which is
    # Varad's (split.md §2). This is the clock lane's cost of not touching it.
    from calendars import load as load_calendar
    from features.portable import PHASES, event_proximity, session_phase

    unknown = [p for p in phases if p not in PHASES]
    if unknown:
        raise ValueError(
            f"unknown phases {unknown}; known: {list(PHASES)}. A misspelled phase never "
            "fires, and a strategy that never fires reads as a phase with no edge."
        )
    if event_window_minutes < 0:
        raise ValueError(f"event_window_minutes must be >= 0, got {event_window_minutes}")
    if not phases and not event_window_minutes:
        raise ValueError("both arms are off; this fires on nothing and measures nothing")

    fires = session_phase(bars, inst).isin(phases).to_numpy()
    if event_window_minutes:
        near = event_proximity(bars, load_calendar(), window_minutes=event_window_minutes)
        fires = fires | near.to_numpy()
    return pd.Series(np.where(fires, 1, 0), index=bars.index).astype("int64")
