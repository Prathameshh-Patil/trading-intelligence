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
  * **XAUUSD was not defined here until 2026-09-10, and the reason it now is
    should be read before the number is used.** Route 2 has not picked a
    vendor and a spot tick is broker-dependent -- 0.01 or 0.10, the exact 10x
    error §4.6 exists to prevent -- so a placeholder would have put a guessed
    number where the seam's whole job is to make the number explicit.

    **MEASURED 2026-09-10, and it narrows what the missing tick actually
    blocks.** Running `m1_sweep.month_counts` over one month twice, at tick
    0.10 and at tick 0.01, returns **byte-identical counts** -- `n`, `target`,
    `stop`, `target_max`, `stop_min` -- with `open_pnl` agreeing to 3e-14 and
    only `cost_atr` moving, by exactly the 10x. The tick cancels: the bracket
    is `tgt_a x atr_ticks` and `first_touch` compares it against
    `target x tick`, so the barrier is `tgt_a x ATR` in price whatever the
    tick is. **So a cross-instrument geometry comparison -- `p_target`,
    `p_stop`, `p_neither` -- is tick-free and does not wait on this decision.
    EV net of cost is not**, and on spot the cost is the measured spread
    rather than GC's 1.4 ticks, so it needs its own model rather than a
    borrowed constant. **So `XAUUSD` below carries the feed's own price
    quantum rather than a broker's tradeable tick** -- a measured property of
    the data in hand, not a guess about an account nobody has opened -- and
    every use of it in a cost or EV claim is still blocked on the room.
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


XAUUSD = Instrument(
    name="XAUUSD",
    # DUKASCOPY'S PRICE QUANTUM, NOT A TRADEABLE TICK. The feed encodes price
    # as integers in points of 1e-3 (`dukascopy.POINTS`), so 0.001 is the
    # finest distinction this data can express -- a fact about the file, which
    # is why it can be written down without the room. **A broker's tick is a
    # different number and this is not it.** Nothing in a geometry comparison
    # depends on it (see the measurement above); anything costed in ticks does,
    # and must not use this.
    tick=0.001,
    # No contract, so no USD per tick. `backtest.summarize` returns NaN for
    # `expectancy_usd` here rather than repeating the tick count as dollars.
    tick_value=None,
    # The same +2h as GC, deliberately: the comparison is only worth making if
    # both instruments cut their sessions on the same boundary. Spot runs
    # ~22:00 Sun to 21:00 Fri UTC, near enough to Globex that the shift lands
    # the same way, and a different shift here would show up as a phase
    # difference that is really a bookkeeping difference.
    session_shift=pd.Timedelta(hours=2),
    anchors=("session_open", "prior_close", "session_high", "session_low", "opening_range", "twap"),
    # No tape, no aggregate size, no aggressor. This is the field the whole
    # module exists for, and it is what makes every flow feature raise here.
    has_flow=False,
)


def require_flow(inst: Instrument) -> None:
    """Refuse a flow feature on an instrument that has no flow. §10.3."""
    if not inst.has_flow:
        raise ValueError(
            f"{inst.name} has no order flow: no tape, no aggregate volume, no aggressor. "
            "There is no proxy for this and substituting one produces a number that "
            "looks exactly like the real one."
        )
