"""The attrition table: which condition refused what, per strategy.

**THE FIRST HONEST ARTEFACT THIS ENGINE CAN PRODUCE IS THIS TABLE AND NOT AN
EQUITY CURVE.** `TRACK_C_ENGINE.md` §5 and E2's own reasoning: "of 370,000
bars, 369,994 were refused, and here is the stage that refused them" is a
statement about the archive, and it is true whether or not the six survivors
made money. A curve off six trades is a statement about six trades.

TWO FAILURE MODES IT IS BUILT TO EXPOSE, AND THEY LOOK NOTHING ALIKE:

  * **Death at stage 3.** One early condition refuses everything and the
    strategy is untestable rather than untested. The table names the condition.
  * **Survival that is too easy.** A late stage still holding thousands of bars
    means the conditions above it condition on nothing. **This is the outcome
    that looks good and is not**, which is why every stage is reported and not
    only the last.

WHY A COUNTER AND NOT A LIST OF REFUSALS. Four strategies over five years of
5-minute bars is ~1.5 million outcomes. Keeping them is hundreds of megabytes
to answer a question that is twenty integers wide.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from track_c.suggestion import Refusal, Suggestion

# Two reserved keys alongside the condition names. Double-underscored so a
# strategy condition can never collide with one -- `suggestion.refuse` would
# raise on such a name anyway, since it is not in any `CONDITIONS`.
EVALUATED = "__evaluated__"
SUGGESTED = "__suggested__"

type Counts = Counter[tuple[str, str]]


def new() -> Counts:
    return Counter()


def record(counts: Counts, outcome: Suggestion | Refusal) -> None:
    """One bar-strategy outcome. Called once per strategy per bar, always."""
    counts[(outcome.strategy, EVALUATED)] += 1
    key = SUGGESTED if isinstance(outcome, Suggestion) else outcome.reason
    counts[(outcome.strategy, key)] += 1


def table(counts: Counts, conditions: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    """One row per (strategy, stage): how many reached it, how many it refused.

    `reached` is the count that arrived at the stage, so the first stage's
    `reached` is every bar evaluated and the last row's `survivors` is the
    suggestion count. `pass_rate` is per stage, not cumulative -- a cumulative
    column would hide which single condition did the work.
    """
    rows = []
    for name, conds in conditions.items():
        reached = counts[(name, EVALUATED)]
        for stage, cond in enumerate(conds):
            refused = counts[(name, cond)]
            rows.append({
                "strategy": name,
                "stage": stage,
                "condition": cond,
                "reached": reached,
                "refused": refused,
                "survivors": reached - refused,
                "pass_rate": (reached - refused) / reached if reached else float("nan"),
            })
            reached -= refused
        rows.append({
            "strategy": name, "stage": len(conds), "condition": SUGGESTED,
            "reached": reached, "refused": 0, "survivors": reached,
            "pass_rate": 1.0 if reached else float("nan"),
        })
    return pd.DataFrame(rows)


def check(counts: Counts, conditions: dict[str, tuple[str, ...]]) -> None:
    """Every outcome landed in a stage, for every strategy.

    A mismatch means a code path returned without being counted, which is how
    an attrition table comes to describe a different run than the equity curve
    beside it. Cheap, and it runs at the end of every backtest.
    """
    for name, conds in conditions.items():
        total = counts[(name, EVALUATED)]
        counted = counts[(name, SUGGESTED)] + sum(counts[(name, c)] for c in conds)
        if total != counted:
            raise ValueError(f"{name}: {total} evaluated but {counted} accounted for; "
                             "an outcome was produced without being recorded")
