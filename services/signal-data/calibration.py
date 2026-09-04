"""Stage F: what was shown, what happened, and whether the two agree.

Design: docs/superpowers/specs/2026-09-05-live-signal-pipeline-design.md §7.

**Built before the first signal exists, on purpose.** A calibration loop added
after the fact has no history, and the first weeks are when calibration is most
informative -- so this file is written while there is nothing to log.

The one question it answers: **when the model says 61%, does it happen 61% of
the time.** That is falsifiable weekly on live data without a backtest, it is
the only claim a subscriber can check themselves, and it separates the two
cases a hit rate cannot -- a model that is 55% accurate and says 55% is a
useful tool; one that is 70% accurate and says 90% is a liability.

Three properties, and all three are structural rather than promised:

  * **Append-only.** A signal record is never rewritten. An outcome is a
    SECOND record joined by id, so the forecast on disk stays byte-identical
    to the one the trader saw. Calibration measured against retrospectively
    adjusted forecasts measures nothing at all, and the adjustment would be
    invisible in the result.
  * **`settle` cannot invent history.** It raises on an id that was never
    emitted and on one already settled. Backfilling an outcome for a signal
    that was never shown is the single cheapest way to fake this number.
  * **A forecast without its context is refused at the boundary.** `p` alone
    is meaningless -- it is a probability OF something, under a feed state,
    off a bucket of some size, against thresholds that were in force at the
    time. SIGNAL_FIELDS is that list, and emit() fails loud rather than
    recording a row nobody can audit later.

`outcome` uses `backtest.first_touch`'s encoding -- +1 target first, -1 stop
first, 0 neither -- because the live outcome and the historical base rate it
is compared against have to be the same measurement, not two that resemble
each other.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from backtest import MIN_SAMPLES

# Every one of these is load-bearing for reading the row back in six months.
# `feed` because a stale feed invalidates the forecast above it; `n` because a
# probability off nine samples is not the same claim as one off nine hundred;
# `thresholds` because the pass line moves and a number is only auditable
# against the one that produced it.
SIGNAL_FIELDS = (
    "at", "side", "p", "target", "stop", "horizon", "bucket", "n", "thresholds", "feed",
)


def emit(path: Path, **signal: object) -> str:
    """Append one signal exactly as shown to the trader. Returns its id.

    The id is generated here rather than accepted, so a caller cannot reuse one
    and quietly overwrite a forecast in the join.
    """
    missing = [f for f in SIGNAL_FIELDS if f not in signal]
    if missing:
        raise ValueError(f"signal is missing {missing}; every field is needed to audit the row")

    sid = uuid4().hex[:12]
    _append(path, {"kind": "signal", "id": sid, **signal})
    return sid


def settle(path: Path, sid: str, outcome: int, at: str) -> None:
    """Append the realised outcome for `sid`. +1 target, -1 stop, 0 neither.

    **Reads the whole log, so a replay that settles N signals is O(N^2).**
    Measured: 3,373 emit+settle pairs in 26.5s. Live use settles a handful a
    day against a log of hundreds, where that is free -- and both guards below
    need the history, so the read is what buys them. Seeding the log from the
    full archive is the case that would hurt; batch it there rather than making
    this function cheaper and blinder.
    """
    # `type(...) is not int` rather than isinstance, because bool subclasses int
    # and `True in (-1, 0, 1)` is True. A bool here would serialise as `true`,
    # read back as a bool, and quietly mean "hit" -- a second definition of the
    # outcome living alongside first_touch's three-valued one.
    if type(outcome) is not int or outcome not in (-1, 0, 1):
        raise ValueError(f"outcome is first_touch's encoding (-1/0/1), got {outcome!r}")

    seen = _records(path)
    if not any(r["kind"] == "signal" and r["id"] == sid for r in seen):
        raise KeyError(f"{sid} was never emitted; an outcome cannot precede the signal it settles")
    if any(r["kind"] == "outcome" and r["id"] == sid for r in seen):
        raise ValueError(f"{sid} is already settled; outcomes are written once")

    _append(path, {"kind": "outcome", "id": sid, "at": at, "outcome": outcome})


def read(path: Path) -> pd.DataFrame:
    """One row per signal, `outcome` NaN while it is still open."""
    records = _records(path)
    signals = pd.DataFrame([r for r in records if r["kind"] == "signal"]).drop(columns="kind")
    outcomes = [r for r in records if r["kind"] == "outcome"]
    if signals.empty:
        return signals

    if not outcomes:
        signals["outcome"] = pd.NA
        return signals

    done = pd.DataFrame(outcomes)[["id", "at", "outcome"]].rename(columns={"at": "settled_at"})
    orphans = set(done["id"]) - set(signals["id"])
    if orphans:
        raise ValueError(f"outcomes for ids that were never emitted: {sorted(orphans)}")
    return signals.merge(done, on="id", how="left")


BINS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def reliability(log: pd.DataFrame, bins: tuple[float, ...] = BINS) -> pd.DataFrame:
    """Predicted probability against realised frequency, per bin, with N.

    The diagram, as a table. A calibrated model puts `realised` on top of
    `predicted` in every row that is not thin -- and `thin` is most of them for
    a long time, which is the honest reading rather than a defect of the model.
    """
    settled = log[log["outcome"].notna()] if "outcome" in log else log.iloc[:0]
    if settled.empty:
        return pd.DataFrame(columns=["n", "predicted", "realised", "thin"])

    binned = pd.cut(settled["p"], list(bins))
    hit = (settled["outcome"].astype(int) == 1).groupby(binned, observed=True)
    return pd.DataFrame(
        {
            "n": hit.size(),
            "predicted": settled["p"].groupby(binned, observed=True).mean(),
            "realised": hit.mean(),
            "thin": hit.size() < MIN_SAMPLES,
        }
    )


def _append(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]
