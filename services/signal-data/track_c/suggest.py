"""Track C's public entry: bars in, one outcome per strategy out.

**`row` is what the event loop calls and `at` is what a person calls.** Both
return the same thing -- four outcomes, one per strategy, in S1..S4 order --
because "any setups now?" and "what did this bar do in 2024?" are the same
question asked at different times, and an engine whose live path and backtest
path are two functions is an engine with two answers.

A `Refusal` is the normal element. All four refusing is the normal return
value, and it is not an error: it is the answer, and it names the condition.

WHAT THIS DOES NOT DO. It does not place, size against an open position, or
respect the daily caps -- those are `engine.py`'s, because they depend on state
a single bar does not carry. `day` is passed in for exactly that reason: the
caller owns the counters, and `fsm.Day()` (a fresh, empty day) is the honest
default for a standalone question.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

import fsm
from instruments import Instrument
from track_c import context, strategies
from track_c.suggestion import Refusal, Suggestion


def row(ctx: pd.DataFrame, i: int, *, cfg: dict[str, Any],
        day: fsm.Day) -> tuple[Suggestion | Refusal, ...]:
    """The four strategies against bar `i` of an already-built context."""
    return tuple(m.evaluate(ctx, i, cfg=cfg, day=day) for m in strategies.ALL)


def at(bars: pd.DataFrame, inst: Instrument, cfg: dict[str, Any], *,
       events: pd.DatetimeIndex, day: fsm.Day | None = None,
       when: pd.Timestamp | None = None) -> tuple[Suggestion | Refusal, ...]:
    """Build the context over `bars` and answer for one bar -- the last by default.

    **`bars` must END at the moment being asked about.** Nothing in `context`
    can see past its own frame, so a frame that runs past `when` would let a
    rolling window include the future even though every column is causal within
    the frame. Passing `when` slices first rather than trusting the caller.

    The warm-up is not a special case: with too little history the context
    columns are NaN and every strategy refuses at `inputs`, which is the
    correct answer and appears in the funnel as such.
    """
    if when is not None:
        bars = bars.loc[:when]
    if bars.empty:
        raise ValueError("no bars to evaluate; a suggestion needs a history, and an empty "
                         "frame is a data failure rather than a refusal")
    ctx = context.build(bars, inst, cfg, events=events)
    return row(ctx, len(ctx) - 1, cfg=cfg, day=day or fsm.Day())
