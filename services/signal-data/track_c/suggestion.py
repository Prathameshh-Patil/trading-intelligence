"""What Track C emits: a `Suggestion`, or a `Refusal` that names its reason.

**`Refusal` is the normal return value.** Four strategies over ~370,000 bars
will refuse virtually all of them, and the first honest artefact this engine
can produce is an attrition table rather than an equity curve -- so a refusal
carries the condition that stopped it and that condition's position in its
strategy's ordered list, which is the only thing `funnel.py` needs to build
the table.

WHY THE INVARIANTS ARE CHECKED IN `__post_init__` AND NOT BY THE CALLER. A
`Suggestion` whose stop is on the wrong side of its entry is not a bad trade,
it is a bug that prices a loss as a win for the rest of the run. Four
strategies construct these; one place rejects the impossible ones.

WHAT `confidence` IS, STATED ONCE AND REPEATED IN EVERY REPORT. **It is an
ordinal score in [0, 1], not a probability.** It is a deterministic function of
how far the strategy's own conditions were cleared by -- no logistic, no
calibration, no fit. `classifier.py`'s isotonic `p_E` is the calibrated
quantity in this repo and Track C deliberately does not use it: a fitted model
is exactly what the "purely mathematical" constraint excludes. Nothing may
read `confidence` as "this trade wins 71% of the time".
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class Suggestion:
    strategy: str
    ts: pd.Timestamp
    side: int                  # +1 long, -1 short
    entry: float               # a LIMIT. §9: it expires, it never becomes a market order
    stop: float
    target: float
    lots: float
    expires_at: pd.Timestamp
    confidence: float          # ordinal, not a probability -- see the module docstring

    def __post_init__(self) -> None:
        if self.side not in (1, -1):
            raise ValueError(f"side must be +1 or -1, got {self.side}")
        if (self.entry - self.stop) * self.side <= 0:
            raise ValueError(
                f"{self.strategy}: stop {self.stop} is not behind entry {self.entry} for "
                f"side {self.side}; this prices a loss as a win for the rest of the run")
        if (self.target - self.entry) * self.side <= 0:
            raise ValueError(
                f"{self.strategy}: target {self.target} is not ahead of entry {self.entry} "
                f"for side {self.side}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence is an ordinal score in [0, 1], got {self.confidence}")
        if self.expires_at <= self.ts:
            raise ValueError(f"a limit that expires at or before it is placed never lives: "
                             f"{self.ts} -> {self.expires_at}")

    @property
    def d_usd(self) -> float:
        """Risk per ounce. §10 bounds it to [$2, $5] and `bracket.py` enforces both."""
        return abs(self.entry - self.stop)

    @property
    def r_usd(self) -> float:
        """Reward per ounce. §10's `clip(2.5D, $10, $15)`."""
        return abs(self.target - self.entry)


@dataclass(frozen=True, slots=True)
class Refusal:
    strategy: str
    ts: pd.Timestamp
    reason: str    # the condition that refused, from the strategy's CONDITIONS
    stage: int     # its index in CONDITIONS -- the attrition table's x-axis


def refuse(strategy: str, ts: pd.Timestamp, reason: str,
           conditions: tuple[str, ...]) -> Refusal:
    """A refusal, with its stage looked up rather than passed.

    `conditions.index` raises on a reason that is not in the strategy's own
    ordered list, which turns a mistyped refusal name into a test failure
    instead of a silently uncounted column in the attrition table.
    """
    return Refusal(strategy=strategy, ts=ts, reason=reason, stage=conditions.index(reason))
