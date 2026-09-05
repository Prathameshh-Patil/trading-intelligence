"""Layer 3: the 3-of-4 checker, over D1's eligible bars.

Week 1 D3, `plans/team/week-01.md` §3. Four conditions, each a
`(bars, *, thresholds) -> Series of +1 / -1 / 0` in the same shape as
`strategies.py`, and a combiner that turns them into one side series:

  * **A, absorption** -- aggressors filled, price did not follow. **Stubbed.**
  * **B, delta divergence** -- a new price extreme the flow did not confirm.
  * **C, CVD momentum shift** -- trailing CVD slope changes sign.
  * **D, range expansion** -- a bar far wider than ATR that closed on its end.

**Condition A is a stub that returns zeros, and that is a decision rather
than a difficulty.** `absorption_fade` was dropped from Week 1 in Part B: its
`|delta| / range` proxy was reasoned about against a 15-tick median bar, and
the 5-minute median is 38. D3 sanctions the stub in as many words -- *"stub
it `return False`, commit that, and move on. Day 4 will tell you whether it
mattered."* The consequence is reported, not relabelled: **with A silent,
3-of-4 is in practice 3-of-3, a stricter gate than the one designed.** Every
signal count downstream is a count under that gate.

**Agreement is part of the count.** Three conditions firing long while a
fourth fires short is a disagreement, not a 3-of-4 pass, so the combiner
requires the opposite side to be empty -- the same reading `footprint_stack`
takes of a bar stacked both ways. With A silent it is redundant today (three
of three cannot be outvoted) and it stops being redundant the moment A comes
back.

**B and D cannot agree, and that is structural rather than a tuning
problem.** B fires long at a new closing low for its window; D fires long
only on a bar that closed up on a big body, which at a new low it is not. On
the training half they co-fire on 26 bars and agree on direction on **zero**
of them. So the four conditions are not four interchangeable votes: any
combiner that needs both B and D is dead before it runs, and with A silent
the 3-of-4 gate needs exactly that. Measured 2026-09-04: **3-of-4 produces 0
signals on 3,516 training bars**, against ~0.7 expected if the three fired
independently. The design's arithmetic, not a bug in it.

**No threshold here has a default**, for the reason `strategies.py` and
`regime_filter.py` have none: the numbers belong to whoever carries the bias,
and a signature that raises `TypeError` is the only enforcement that cannot
be forgotten. `eligible` is a required argument for the same reason -- the
regime filter is not something a caller can leave off by accident.

Every feature is imported from `features/`, never re-derived. The three traps
`strategies.py` documents -- lookahead, dropped minutes, windows spanning the
overnight break -- are solved there once and inherited here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.expansion import atr, bar_range, body_ratio
from features.orderflow import cvd_slope
from instruments import GC
from strategies import _align, _sides, _window


def absorption_reversal(bars: pd.DataFrame) -> pd.Series:
    """Condition A. Zeros -- the rule was dropped from Week 1, see the module
    docstring. It stays as a named condition so the combiner keeps counting
    four slots and D4 can measure what the missing one cost."""
    return pd.Series(0, index=bars.index, dtype="int64")


def delta_divergence(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Condition B. A new closing low for the trailing window, made on less
    selling than the window's worst bar, with delta already turning up: long.
    Mirrored at a new high: short.

    Two legs, and both are needed. The price extreme alone is a breakout, and
    the flow leg alone is a delta reading with no location. It is the pair --
    *this* low cost less selling than the last one did -- that says the side
    pushing price is running out of size.

    Strictly above the window's minimum, not at it. A bar that is both the
    price low and the delta low is a trend making a new low with full
    conviction behind it, which is the case this condition exists to exclude.

    `cvd_divergence` in `strategies.py` asks a neighbouring question over
    CVD; this one is per-bar delta and is deliberately not the same rule.
    """
    close_lo = _align(_window(bars, "close", window, min_bars).min(), bars)
    close_hi = _align(_window(bars, "close", window, min_bars).max(), bars)
    delta_lo = _align(_window(bars, "delta", window, min_bars).min(), bars)
    delta_hi = _align(_window(bars, "delta", window, min_bars).max(), bars)
    step = bars.groupby("session", sort=False)["delta"].diff()
    return _sides(
        (bars["close"] <= close_lo) & (bars["delta"] > delta_lo) & (step > 0),
        (bars["close"] >= close_hi) & (bars["delta"] < delta_hi) & (step < 0),
        bars,
    )


def cvd_shift(bars: pd.DataFrame, *, window: str, min_bars: int) -> pd.Series:
    """Condition C. The trailing CVD slope crosses from non-positive to
    positive: long. From non-negative to negative: short.

    The crossing is the signal, not the sign. A slope that has been positive
    for six bars is momentum already in progress, and entering there is
    entering late -- which is why the bar after a flip is flat.

    D3 also describes a CVD EMA crossing zero. That is the same statement
    read off the level rather than the change: session CVD crossing zero says
    the session's net flow flipped, which a trailing slope flip already
    reports, at a window the caller chooses instead of one the anchor
    imposes. Two measures of one thing is two thresholds pretending to be
    one, so this implements the slope and not both.
    """
    slope = cvd_slope(bars, window=window, min_bars=min_bars)
    prev = slope.groupby(bars["session"].to_numpy(), sort=False).shift(1)
    return _sides((slope > 0) & (prev <= 0), (slope < 0) & (prev >= 0), bars)


def range_expansion(
    bars: pd.DataFrame, *, atr_window: str, atr_min_bars: int, mult: float, body_min: float
) -> pd.Series:
    """Condition D. A bar at least `mult` times ATR wide that spent at least
    `body_min` of that range on its body, in the direction it closed.

    Width without a body is a fight, not expansion: a 60-tick range that
    closes on its open travelled twice and kept nothing. ATR cannot tell the
    two apart, and on its own it would call the widest indecision bar of the
    month the strongest signal in it.

    ATR includes the bar being scored, which makes the test slightly harder
    to pass than a lagged ATR would -- the expansion is in its own
    denominator. That is the conservative direction, and it avoids a second
    windowing convention living next to the one `regime_filter` gates on.
    """
    wide = bar_range(bars, GC) >= mult * atr(bars, GC, window=atr_window, min_bars=atr_min_bars)
    strong = body_ratio(bars, GC) >= body_min
    direction = np.sign(bars["close"] - bars["open"])
    return _sides(wide & strong & (direction > 0), wide & strong & (direction < 0), bars)


def combine(
    conditions: list[pd.Series], *, min_conditions: int, eligible: pd.Series
) -> pd.Series:
    """At least `min_conditions` agreeing, nothing dissenting, on a bar the
    regime filter passed.

    `eligible` fails closed: a bar the filter could not score -- no trailing
    context, no regime label -- is not a bar that passed it.
    """
    if min_conditions > len(conditions):
        raise ValueError(f"{min_conditions} of {len(conditions)} conditions can never fire")
    votes = pd.concat(conditions, axis=1)
    n_long = (votes > 0).sum(axis=1)
    n_short = (votes < 0).sum(axis=1)
    side = _sides(
        (n_long >= min_conditions) & (n_short == 0),
        (n_short >= min_conditions) & (n_long == 0),
        votes,
    )
    return side.where(eligible.fillna(False).astype(bool), 0)
