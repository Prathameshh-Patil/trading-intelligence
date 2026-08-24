#!/usr/bin/env python3
"""
Resolve the 2026-07-16 closing-price discrepancy using data already on disk.
NO API CALLS, NO COST.

THE DISCREPANCY
    TradingView's daily bar for COMEX:GCQ2026 on 2026-07-16 closes at 3992.1.
    compute_delta_cvd.py reports 3979.9. That is 12.2 points apart on a bar
    whose open (4068.9), high (4071.9) and low (3973.4) all match TradingView
    to the dime.

    O/H/L matching while C does not is the signature of a different CLOSE
    RULE, not a different session window -- if the window were wrong, the
    high (which prints right at the 18:00 ET open, the most window-sensitive
    value there is) would have moved too.

THE HYPOTHESIS
    CME settles COMEX gold on the volume-weighted average price of trades in
    the 13:29:30-13:30:00 ET closing range, NOT on the last print before the
    17:00 ET session close. Vendors overwhelmingly report the daily bar's
    close as the official settlement. So:

        yours (3979.9)        = last trade at 17:00 ET   -- correct for
                                order-flow work, since it is where CVD ends
        TradingView (3992.1)  = settlement at 13:30 ET   -- correct for
                                margin, P&L, and published daily bars

    Both can be right. This script tests whether that actually explains the
    gap, using gc_trades.parquet.

    NOTE: confirm the exact closing-range window against CME's published
    methodology for GC before relying on the number. The mechanism is solid;
    the precise seconds are worth checking. Several candidate windows are
    evaluated below so a small definitional difference is visible rather
    than hidden.

USAGE
    python verify_settlement_close.py \
        --parquet data/gc_trades.parquet \
        --session 2026-07-16 \
        --reference 3992.1

Requires:
    pip install pandas pyarrow
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Session runs 18:00 ET -> 17:00 ET the next day; compute_delta_cvd.py rolls a
# UTC timestamp onto its session date by adding 2h. That +2h is EDT-specific.
# Here we convert through a real timezone instead, so this stays correct
# across the DST boundary.
SESSION_OPEN_ET = time(18, 0)
SESSION_CLOSE_ET = time(17, 0)

# Candidate settlement windows, as (label, start_et, end_et) on the session
# date. CME's documented closing range for GC is the first of these; the
# others are included so that a small definitional difference shows up as a
# near-miss rather than being invisible.
SETTLEMENT_WINDOWS = [
    ("13:29:30-13:30:00 ET  (CME closing range for GC)", time(13, 29, 30), time(13, 30, 0)),
    ("13:29:00-13:30:00 ET  (1-minute variant)", time(13, 29, 0), time(13, 30, 0)),
    ("13:28:00-13:30:00 ET  (2-minute variant)", time(13, 28, 0), time(13, 30, 0)),
    ("13:30:00-13:30:30 ET  (post-bell control)", time(13, 30, 0), time(13, 30, 30)),
]


def et_to_utc(d: date, t: time) -> pd.Timestamp:
    """Localise a naive (date, time) in America/New_York and return it as a
    tz-aware UTC pandas Timestamp. Going through zoneinfo rather than a fixed
    offset is what keeps this correct in EST as well as EDT."""
    return pd.Timestamp(datetime.combine(d, t, tzinfo=ET)).tz_convert(UTC)


def load_session(parquet: Path, session: date) -> pd.DataFrame:
    df = pd.read_parquet(parquet, columns=["timestamp", "price", "size", "symbol"])

    ts = df["timestamp"]
    if ts.dt.tz is None:
        # Parquet round-trips can drop tz. The pull writes UTC, so re-attach it
        # rather than letting a naive column be compared against aware bounds.
        df["timestamp"] = ts.dt.tz_localize(UTC)

    # CME trading day for `session` opens 18:00 ET on the PREVIOUS calendar day.
    start = et_to_utc(session - timedelta(days=1), SESSION_OPEN_ET)
    end = et_to_utc(session, SESSION_CLOSE_ET)

    out = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    if out.empty:
        sys.exit(
            f"No trades found between {start} and {end}.\n"
            f"Check --session and that {parquet} covers that date."
        )

    print(f"Session {session} (CME trading day)")
    print(f"  window       {start}  ->  {end}")
    print(f"  trades       {len(out):,}")
    print(f"  volume       {int(out['size'].astype('int64').sum()):,} contracts")
    print(f"  contracts    {sorted(out['symbol'].unique().tolist())}")
    return out


def vwap(df: pd.DataFrame) -> tuple[float, int, int]:
    """Volume-weighted average price, trade count, volume."""
    size = df["size"].astype("int64")
    volume = int(size.sum())
    if volume == 0:
        return float("nan"), 0, 0
    return float((df["price"] * size).sum() / volume), len(df), volume


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", default="data/gc_trades.parquet")
    parser.add_argument(
        "--session",
        default="2026-07-16",
        help="CME trading day as YYYY-MM-DD (the date the session CLOSES on).",
    )
    parser.add_argument(
        "--reference",
        type=float,
        default=3992.1,
        help="The external close to explain (TradingView's daily bar close).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.5,
        help="How close a candidate VWAP must land to count as a match, in "
        "points. Gold ticks at 0.1, so 0.5 is a few ticks of slack.",
    )
    args = parser.parse_args()

    session = date.fromisoformat(args.session)
    parquet = Path(args.parquet)
    if not parquet.exists():
        sys.exit(f"Parquet not found: {parquet}")

    df = load_session(parquet, session)

    # --- The two close definitions -------------------------------------
    last_row = df.loc[df["timestamp"].idxmax()]
    last_trade = float(last_row["price"])

    print("\n--- Close definitions ---")
    print(f"  last trade at session close   {last_trade:>10.1f}   "
          f"({last_row['timestamp']})")
    print(f"  external reference to explain {args.reference:>10.1f}")
    print(f"  gap                           {args.reference - last_trade:>+10.1f}")

    # --- Candidate settlement windows ----------------------------------
    print("\n--- Settlement-window VWAPs ---")
    best = None
    for label, t0, t1 in SETTLEMENT_WINDOWS:
        w0, w1 = et_to_utc(session, t0), et_to_utc(session, t1)
        window = df[(df["timestamp"] >= w0) & (df["timestamp"] < w1)]
        price, n, vol = vwap(window)

        if n == 0:
            print(f"  {label:<52}  no trades in window")
            continue

        diff = price - args.reference
        hit = abs(diff) <= args.tolerance
        marker = "  <== MATCH" if hit else ""
        print(
            f"  {label:<52}  vwap={price:>9.2f}  "
            f"diff={diff:>+7.2f}  n={n:>5,}  vol={vol:>7,}{marker}"
        )
        if best is None or abs(diff) < abs(best[1] - args.reference):
            best = (label, price, n, vol)

    # --- Verdict --------------------------------------------------------
    print("\n--- Verdict ---")
    if best is None:
        print("  INCONCLUSIVE: no trades in any candidate window.")
        return

    label, price, n, vol = best
    diff = price - args.reference

    if abs(diff) <= args.tolerance:
        print(
            f"  CONFIRMED. The settlement window {label.split('  ')[0]} gives "
            f"{price:.2f}, within {args.tolerance} of TradingView's "
            f"{args.reference:.1f}.\n"
            f"  Your 3979.9 is the last trade and is correct as defined; the\n"
            f"  12.2-point gap is settlement-vs-last-trade, not a data bug.\n\n"
            f"  ACTION: label which close each downstream consumer uses. Keep\n"
            f"  the last trade for order-flow work (it is where CVD ends) and\n"
            f"  the settlement for anything compared against published bars."
        )
    else:
        print(
            f"  NOT EXPLAINED. Closest candidate ({label.split('  ')[0]}) gives "
            f"{price:.2f}, still {diff:+.2f} from {args.reference:.1f}.\n"
            f"  The settlement hypothesis does NOT account for the gap. Do not\n"
            f"  wave this away -- check, in order:\n"
            f"    1. Is TradingView's bar the same contract? (GCQ2026, not GC1!\n"
            f"       which is back-adjusted and will not match raw prices.)\n"
            f"    2. Does your parquet actually contain the settlement window,\n"
            f"       or were those prints dropped as spreads/non-outright?\n"
            f"    3. CME's published closing-range methodology for GC -- the\n"
            f"       window above may simply be the wrong seconds."
        )


if __name__ == "__main__":
    main()
