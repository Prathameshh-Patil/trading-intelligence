"""
Export the S1 tick fixture to JSON for `apps/desktop/src/lib/engine/mock.ts`.

WHAT THIS IS
    plans/team/week-01.md's Friday-28-Aug prep list (Prathamesh, item 3): W1D2's
    mock.ts replays the fixture session at 10x and emits DeltaBar/Outlier. TS
    cannot read parquet without a native binding, and pulling one in for a
    fixture read is not worth a lockfile change. This does the one conversion
    ahead of time so Day 2 starts on the replay logic, not on data plumbing.

WHAT THIS DOES NOT DO
    It does not compute DeltaBar or Outlier -- that shape decision (which bar
    size to replay at, how to synthesize outliers, how 'N' trades are surfaced
    given S2's Side type has no third state) belongs to W1D2 and to whoever
    writes mock.ts. This exports raw ticks; mock.ts decides how to bar them.

USAGE
    python export_fixture_json.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

DEFAULT_SRC = "data/fixtures/gc_ticks_1session.parquet"
# public/, not src/lib -- 4.7MB of ticks belongs in a fetch()'d static asset,
# not bundled into the JS chunk by an import.
DEFAULT_OUT = "../../apps/desktop/public/fixtures/gc_ticks_1session.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    src = Path(args.parquet)
    if not src.exists():
        sys.exit(f"Source not found: {src}\nRun from services/signal-data/.")

    df = pd.read_parquet(src)
    print(f"source: {src}  ({len(df):,} rows)")

    # Raw ticks, epoch ms -- JS-native, no timezone library needed to consume it.
    # aggressor_side stays 'B' | 'A' | 'N' (the raw contract encoding, same as
    # the parquet), not squeezed into S2's Side ('bid' | 'ask') here -- that
    # squeeze is mock.ts's decision, and this file should not make it silently.
    out_rows = [
        {
            "t": int(ts.value // 1_000_000),
            "price": float(price),
            "size": int(size),
            "side": side,
        }
        for ts, price, size, side in zip(
            df["timestamp"], df["price"], df["size"], df["aggressor_side"]
        )
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(
            {
                "symbol": str(df["symbol"].iloc[0]),
                "session": "2026-07-16",
                "rowCount": len(out_rows),
                "ticks": out_rows,
            },
            f,
        )

    size_kb = out.stat().st_size / 1024
    print(f"wrote {out}  ({size_kb:,.0f} KB, {len(out_rows):,} ticks)")


if __name__ == "__main__":
    main()
