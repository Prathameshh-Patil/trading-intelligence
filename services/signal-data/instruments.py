"""The portability seam: what a tick is worth, and whether flow exists here.

Contract: `docs/strategy/ARCHITECTURE.md` §4.2, seam S8 in
`plans/team/strategy-split.md` §8. **This module is step 1 of the Track B build
order and everything else in that track waits on it.**

Before this file, `s1.py` held `TICK = 0.10` and every tick-denominated number
in the repo -- `backtest.py`, `strategies.py`, `horizon.py`,
`features/expansion.py`, `features/orderflow.py` -- reached for it by import.
That is not a constant, it is an assumption about which instrument is being
measured, and an import cannot be wrong out loud. Injecting it means a frame
from a second instrument either carries its own tick or fails to run.

**`has_flow: False` raises. It does not degrade, fall back, or substitute a
proxy.** Spot gold has no tape, no aggregate volume and no aggressor, so every
flow feature on it would be an estimate wearing a measurement's name -- and a
silent degradation produces a number that looks exactly like the real one.
`require_flow` is called by the functions that read `delta` or `volume`.

TWO PLACES THIS DELIBERATELY DIVERGES FROM S8 AS DRAFTED, both to be put to
the room before the seam is called frozen:

  * S8 says `session: SessionCalendar`. There is no calendar type in this repo
    and nothing yet needs one: the only session logic that exists is the
    +2h shift `s1.py` applies to roll a Globex date onto the day a trader
    files it under, and "24x5 with a named boundary" is the same shape. So the
    field is the shift itself. A calendar earns its own type when a second
    instrument needs more than an offset -- which is also when the DST hole
    `s1.SESSION_SHIFT` already documents has to be closed.
  * **XAUUSD is not defined here.** Route 2 has not picked a vendor and a spot
    tick is broker-dependent -- 0.01 or 0.10, which is the exact 10x error
    §4.6 exists to prevent. Writing a placeholder would put a guessed number
    where the seam's whole job is to make the number explicit.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Instrument:
    """Everything downstream needs to know about an instrument, and no more.

    Frozen because it is passed into feature functions that must not be able
    to retune the instrument under a running measurement.
    """

    name: str
    tick: float
    tick_value: float | None  # USD per tick per contract; None where there is no contract
    session_shift: pd.Timedelta
    anchors: tuple[str, ...]  # which anchors are defined here -- ARCHITECTURE §4.3
    has_flow: bool


GC = Instrument(
    name="GC",
    tick=0.10,
    tick_value=10.0,
    # Globex gold runs 18:00 -> 17:00 ET. Under EDT that is 22:00 -> 21:00 UTC,
    # so +2h rolls a session onto the calendar date a trader would file it
    # under. A month crossing DST needs a real exchange calendar instead.
    session_shift=pd.Timedelta(hours=2),
    anchors=("session_open", "prior_close", "session_high", "session_low", "opening_range", "twap"),
    has_flow=True,
)


def require_flow(inst: Instrument) -> None:
    """Refuse a flow feature on an instrument that has no flow. §10.3."""
    if not inst.has_flow:
        raise ValueError(
            f"{inst.name} has no order flow: no tape, no aggregate volume, no aggressor. "
            "There is no proxy for this and substituting one produces a number that "
            "looks exactly like the real one."
        )
