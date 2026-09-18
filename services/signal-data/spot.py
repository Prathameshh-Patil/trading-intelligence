"""Route 2's spot lane: Dukascopy hours in, the bar frame portable features expect out.

`dukascopy.py` decodes one hour and deliberately stops there. This is the rest
of the path -- a resumable bulk pull, and bars built from the mid.

WHY THIS IS NOT `s1.minute_bars`. That function aggregates `price` and `size`
into `open/high/low/close/volume/delta/trades` and then a session-reset `cvd`.
**Spot has none of those.** There is no tape, no aggregate size and no
aggressor, which is the whole reason `Instrument.has_flow` exists. Feeding a
bid/ask stream through a flow aggregator means inventing `volume` from tick
counts and `delta` from nothing, and `instruments.require_flow` exists
precisely to stop that being done quietly.

WHY NOT `regimes.resample_bars` EITHER. Same reason, plus a harder one:
`regimes.py` is a **parked Track A module** and `ARCHITECTURE.md` §2 says no
Track B work may modify one. Both it and `s1.minute_bars` also hardcode
`SESSION_SHIFT` rather than taking `inst.session_shift` -- step 1 injected
`TICK` through the repo but not the session boundary, so the portability seam
is one field short of complete. Recorded here rather than fixed here: fixing it
means editing a parked module.

THE TWO DUPLICATED NAMES ARE GONE, 2026-09-11. `features/portable.mid` and
`features/portable.spread_bp` were committed signatures raising
`NotImplementedError`, and this module computed both inline because it needed
them before step 6 ran -- **two definitions of the same quantity, which is how
two files quietly disagree**, the same failure `bd675f5` records for
first-touch. Prathamesh filled them (issue #6) and `minute_bars` now calls
them: one line at each site, exactly as `strategy-split.md` §9 said it would
be. **The swap was verified to move no number** -- `minute_bars` returns a
frame equal to the inline version's, column for column.

WHAT A SPOT BAR CARRIES, AND WHAT IT DOES NOT.

    open high low close   from the MID, not the bid and not the ask
    ticks                 quote updates in the bar -- NOT volume
    spread_bp             mean top-of-book spread, the one thing GC cannot see
    session               from `inst.session_shift`

`ticks` is named `ticks` and never `volume`. A quote-update count and a traded
size are different quantities, and `AllTick`'s `GOLD.md` is this repo's own
record of what happens when a feed's activity count is read as volume. Nothing
downstream may aggregate it as size.

**`spread_bp` is a broker pricing decision, not a market outcome** --
`ARCHITECTURE.md` §7 says so and it is repeated here because this is where the
number is produced. Two brokers disagree about the same instant. It is a
legitimate input to "does spread structure predict anything"; it is not a
threshold that transfers to another venue.

    PYTHONPATH=. uv run python spot.py --months 2026-05 2026-06 2026-07

**Expect to run that more than once.** It is resumable by design and the feed
is throttled by IP: a pass takes what it can get and the next one fills the
gaps. Days already on disk cost nothing to skip.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pandas as pd

import spot_s3
from features import portable
from instruments import Instrument


def pull(symbol: str, months: list[str], out: Path, *,
         fetch: Callable[[str, date], pd.DataFrame] = spot_s3.fetch_day) -> None:
    """Every day of every month, one parquet per UTC day. Resumable.

    A day already on disk is skipped, so an interrupted pull costs what is
    missing rather than the run -- `reach.build`'s rule.

    THE HOUR CACHE IS GONE, AND SO ARE PAUSE, RETRIES AND TIMEOUT. All four
    existed for one reason: the HTTP datafeed served fewer than 24 requests a
    day, so a day could not be fetched in one pass and a partial day had to be
    kept between runs. E0 replaced that transport with one S3 object per day
    (`analysis/E0_TRANSPORT.md`), so a day now arrives whole or not at all and
    ~50 lines of resume machinery answer a question nobody is asking. Deleted
    rather than left in place -- git remembers the HTTP path.

    **The day-completeness invariant survives the simplification and is now
    structural rather than enforced.** One object is one whole day, so there is
    no longer a code path that can write a day with holes. A day with holes
    looks exactly like a quiet day once it is on disk, and `atr_bp` and
    `rv_slope` would read the hole as calm rather than as absent.

    An empty frame is a real answer -- every Saturday, and any day the venue
    was shut -- and is written as an empty parquet rather than skipped, so a
    later pass does not re-request it forever.
    """
    out.mkdir(parents=True, exist_ok=True)
    for month in months:
        start = pd.Timestamp(f"{month}-01", tz="UTC")
        for ts in pd.date_range(start, start + pd.offsets.MonthEnd(0), freq="D", tz="UTC"):
            f = out / f"{ts:%Y-%m-%d}.parquet"
            if f.exists():
                continue
            t0 = time.perf_counter()
            ticks = fetch(symbol, ts.date())
            ticks.to_parquet(f)
            print(f"{ts:%Y-%m-%d}  {len(ticks):>7,} ticks  {time.perf_counter() - t0:5.1f}s",
                  flush=True)


def load_ticks(cache: Path, months: list[str]) -> pd.DataFrame:
    """Every cached day for these months, in time order."""
    days = sorted(f for m in months for f in cache.glob(f"{m}-*.parquet"))
    if not days:
        raise SystemExit(f"no cached days for {months} under {cache}")
    ticks = pd.concat([pd.read_parquet(f) for f in days], ignore_index=True)
    return ticks.sort_values("timestamp").reset_index(drop=True)


def minute_bars(ticks: pd.DataFrame, inst: Instrument) -> pd.DataFrame:
    """1-minute OHLC of the MID, plus the spread. Empty minutes dropped.

    Mid rather than bid or ask because a bracket measured on the bid and filled
    on the ask is a measurement of the spread wearing a strategy's name. The
    spread is carried in its own column instead, where it can be charged
    explicitly.

    Minutes with no quotes are dropped, so bar N+5 is NOT five minutes after
    bar N -- `s1.minute_bars`'s rule, and `backtest.py` slices on the index for
    exactly this reason.
    """
    # `features/portable`'s, not a second copy. Both were computed inline here
    # because step 6's signatures were still empty when this file needed them;
    # `strategy-split.md` §9 and issue #6 both recorded that as one line at each
    # site once they were filled, and this is that line.
    df = pd.DataFrame({
        "timestamp": ticks["timestamp"],
        "mid": portable.mid(ticks),
        "spread_bp": portable.spread_bp(ticks),
    })
    bars = (
        df.set_index("timestamp")
        .resample("1min")
        .agg(open=("mid", "first"), high=("mid", "max"), low=("mid", "min"),
             close=("mid", "last"), ticks=("mid", "size"), spread_bp=("spread_bp", "mean"))
    )
    bars = bars[bars["ticks"] > 0].copy()
    bars["session"] = pd.DatetimeIndex(bars.index + inst.session_shift).date
    return bars


def resample(bars_1min: pd.DataFrame, bar_size: str, inst: Instrument) -> pd.DataFrame:
    """`regimes.resample_bars` for a frame with no flow. Same index convention."""
    if bar_size in ("1min", "1T"):
        return bars_1min.copy()
    agg = bars_1min.resample(bar_size).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), ticks=("ticks", "sum"), spread_bp=("spread_bp", "mean"))
    agg = agg[agg["ticks"] > 0].copy()
    agg["session"] = pd.DatetimeIndex(agg.index + inst.session_shift).date
    return agg


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--months", nargs="+", required=True, help="YYYY-MM")
    p.add_argument("--out", type=Path, default=Path("data/spot/XAUUSD"))
    a = p.parse_args()
    pull(a.symbol, a.months, a.out)


if __name__ == "__main__":
    main()
