"""Trailing clock windows over bars, restarted at each session boundary.

Two functions, and every windowed feature in the repo is built on them. They
lived in `strategies.py` until 2026-09-06 and moved here to break an import
cycle: `features/expansion.py` imports them, `features/portable.py` imports
`expansion`, and `strategies.m3_session_event` needs `portable` -- so a
module-level import closed a loop through a half-initialised `strategies`.
Prathamesh worked around it with a function-body import and correctly called
the real fix a shared-spine change (`strategy-split.md` §2). This is that fix.

**One windowing convention, in one file, is the whole point.** `regime_filter.py`
states the rule this enforces: *"Re-solving session-grouped trailing windows in
a second file is how the two quietly disagree."* That already carried weight
with one author; with two lanes writing windows in parallel it is the thing
that stops the vol axis and the clock axis measuring different Londons.

Three traps live here rather than in each caller, which is why nobody should
re-derive them:

  * **Clock offsets, not row counts.** `minute_bars` drops empty minutes, so
    thirty rows is not thirty minutes.
  * **Grouped by session.** A window spanning the overnight break scores NY
    against Asia.
  * **`min_bars`, so a session's opening bars are NaN** rather than scored
    against one or two observations, where a standard deviation is either zero
    or meaningless and every z off it is enormous.
"""

from __future__ import annotations

import pandas as pd
from pandas.api.typing import RollingGroupby


def trailing(bars: pd.DataFrame, col: str, window: str, min_bars: int) -> RollingGroupby:
    """Trailing clock window over `col`, restarted at each session boundary."""
    return bars.groupby("session", sort=False)[col].rolling(window, min_periods=min_bars)


def align(s: pd.Series, bars: pd.DataFrame) -> pd.Series:
    """Drop the group level that groupby-rolling adds, restore bar order."""
    return s.droplevel(0).reindex(bars.index)
