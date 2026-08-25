#!/usr/bin/env python3
"""
Cut the S1 tick fixture from the full month of GC trades.

WHAT THIS IS
    plans/team/contracts.md S1 specifies a frozen tick-record contract and a
    fixture -- data/fixtures/gc_ticks_1session.parquet -- that "every test in
    the project asserts against for the next twelve weeks". The .gitignore
    exception landed 25 Aug re-includes exactly this one path and nothing else
    under data/, so the month of billed binary stays out of git while this file
    goes in.

    contracts.md records the fixture as blocked: services/signal-data/data/
    does not exist on Varad's machine. This unblocks it.

THE CONTRACT SAYS
        timestamp        datetime64[ns, UTC]   exchange timestamp
        price            float64
        size             int64
        aggressor_side   category  'B' | 'A'
        symbol           string
        instrument_id    int64

    Two discrepancies were found against the real data and resolved
    deliberately rather than papered over:

    1. pull_futures_trades.py writes aggressor_side as buy_initiated /
       sell_initiated / unknown, NOT 'B'/'A'. This script reverses SIDE_MAP to
       emit the raw exchange encoding the contract asks for.

    2. 'B' | 'A' has no slot for N (no aggressor disseminated -- auction,
       implied, off-book), but the contract's own stated row count of 77,532
       INCLUDES those ~1,811 trades. Both cannot hold. Resolved by keeping all
       77,532 rows and emitting 'N' as a third category value.

       => contracts.md S1 needs a one-line amendment recording that 'N' is a
          real value on ~2.3% of trades and consumers must handle it. Dropping
          those rows instead would mean consumers never learn N exists until
          they hit live data. Per contracts.md, that amendment needs all three
          of you in standup -- this script does NOT make it for you.

SESSION
    2026-07-16 GCQ6, chosen in DELTA_CVD_FINDINGS.md for 0.90 directional
    efficiency and for sitting clear of both the 29 Jul GCQ6->GCZ6 roll and the
    30 Jul day Databento flagged degraded. CME trading day: 18:00 ET on 07-15
    -> 17:00 ET on 07-16. Converted through zoneinfo rather than a fixed +2h
    offset so this stays correct outside EDT.

USAGE
    python cut_s1_fixture.py                 # writes the fixture
    python cut_s1_fixture.py --dry-run       # validate only, write nothing

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

SESSION = date(2026, 7, 16)
SESSION_OPEN_ET = time(18, 0)     # on the PREVIOUS calendar day
SESSION_CLOSE_ET = time(17, 0)
EXPECTED_SYMBOL = "GCQ6"
EXPECTED_ROWS = 77_532            # contracts.md S1

# Reverse of SIDE_MAP in pull_futures_trades.py. The contract wants the raw
# exchange encoding, not the internal labels.
UNMAP_SIDE = {
    "buy_initiated": "B",
    "sell_initiated": "A",
    "unknown": "N",
}

CONTRACT_COLUMNS = [
    "timestamp",
    "price",
    "size",
    "aggressor_side",
    "symbol",
    "instrument_id",
]


def et_to_utc(d: date, t: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(d, t, tzinfo=ET)).tz_convert(UTC)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", default="data/gc_trades.parquet")
    ap.add_argument("--out", default="data/fixtures/gc_ticks_1session.parquet")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.parquet)
    if not src.exists():
        sys.exit(f"Source not found: {src}\nRun from services/signal-data/.")

    df = pd.read_parquet(src)
    print(f"source: {src}  ({len(df):,} rows)")

    ts = df["timestamp"]
    if ts.dt.tz is None:
        df["timestamp"] = ts.dt.tz_localize(UTC)

    start = et_to_utc(SESSION - timedelta(days=1), SESSION_OPEN_ET)
    end = et_to_utc(SESSION, SESSION_CLOSE_ET)
    print(f"session window: {start}  ->  {end}")

    cut = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    cut = cut.sort_values("timestamp").reset_index(drop=True)

    # --- Contract conformance ------------------------------------------
    symbols = sorted(cut["symbol"].unique().tolist())
    if symbols != [EXPECTED_SYMBOL]:
        sys.exit(
            f"Expected only {EXPECTED_SYMBOL} in this session, got {symbols}. "
            f"Refusing to write a fixture that mixes contracts."
        )

    unmapped = set(cut["aggressor_side"].unique()) - set(UNMAP_SIDE)
    if unmapped:
        sys.exit(f"Unrecognised aggressor_side values: {sorted(unmapped)}")

    cut["aggressor_side"] = (
        cut["aggressor_side"].map(UNMAP_SIDE).astype("category")
    )
    # The contract pins datetime64[ns, UTC]. pandas 3 / pyarrow will happily
    # round-trip this as [us] instead, which silently breaks any test that
    # asserts the dtype. Pin it explicitly, and write with coerce_timestamps
    # below so it survives the parquet round-trip.
    cut["timestamp"] = cut["timestamp"].astype("datetime64[ns, UTC]")
    cut["size"] = cut["size"].astype("int64")      # uint32 negation wraps
    cut["price"] = cut["price"].astype("float64")
    cut["instrument_id"] = cut["instrument_id"].astype("int64")
    cut["symbol"] = cut["symbol"].astype("string")

    cut = cut[CONTRACT_COLUMNS]

    # --- Report ---------------------------------------------------------
    print(f"\nrows: {len(cut):,}   (contract states {EXPECTED_ROWS:,})")
    if len(cut) != EXPECTED_ROWS:
        print(f"  WARNING: row count differs from contracts.md by "
              f"{len(cut) - EXPECTED_ROWS:+,}. Investigate before committing.")

    print(f"volume: {int(cut['size'].sum()):,} contracts")
    print(f"price:  {cut['price'].min():.1f} .. {cut['price'].max():.1f}")
    print("\naggressor_side split:")
    vc = cut["aggressor_side"].value_counts()
    for k in ["B", "A", "N"]:
        if k in vc:
            print(f"  {k}  {vc[k]:>8,}  ({vc[k] / len(cut) * 100:5.2f}%)")

    print("\ndtypes (must match contracts.md S1):")
    for c in CONTRACT_COLUMNS:
        print(f"  {c:<16} {cut[c].dtype}")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # version="2.6" is what makes nanosecond timestamps representable in the
    # file at all -- parquet 1.0 tops out at microseconds, so writing under it
    # silently downgrades the dtype the contract pins.
    cut.to_parquet(out, index=False, version="2.6")

    # Read it back and assert the contract holds on the FILE, not just in
    # memory -- a dtype that only survives until the write is not a contract.
    back = pd.read_parquet(out)
    problems = []
    if str(back["timestamp"].dtype) != "datetime64[ns, UTC]":
        problems.append(f"timestamp is {back['timestamp'].dtype}, want datetime64[ns, UTC]")
    if str(back["size"].dtype) != "int64":
        problems.append(f"size is {back['size'].dtype}, want int64")
    if str(back["price"].dtype) != "float64":
        problems.append(f"price is {back['price'].dtype}, want float64")
    if str(back["instrument_id"].dtype) != "int64":
        problems.append(f"instrument_id is {back['instrument_id'].dtype}, want int64")
    if len(back) != len(cut):
        problems.append(f"row count changed on round-trip: {len(cut):,} -> {len(back):,}")
    if problems:
        print("\nROUND-TRIP CONFORMANCE FAILURES:")
        for p in problems:
            print(f"  - {p}")
        sys.exit("Fixture does not satisfy contracts.md S1 after write. Not committing this.")
    print("\nround-trip check: dtypes and row count survive the parquet write.")

    size_kb = out.stat().st_size / 1024
    print(f"\nwrote {out}  ({size_kb:,.0f} KB)")
    print(
        "\nNEXT: this path is re-included by the .gitignore exception, so it "
        "needs no -f:\n"
        f"    git add {out}\n"
        "Verify nothing else came along:\n"
        "    git status --short\n"
    )


if __name__ == "__main__":
    main()
