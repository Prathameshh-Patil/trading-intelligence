#!/usr/bin/env python3
"""
Pull one month of GC (COMEX gold futures) and NQ (CME Nasdaq futures) trade
prints from Databento, collapse to the volume-dominant ("active") contract
per day, and write two clean Parquet files.

This is a data-acquisition script only: no delta/CVD, no aggregation, no
charts. That's tomorrow's task.

USAGE
    # 1. Cost check first — does NOT spend anything, just estimates.
    python pull_futures_trades.py --estimate-only

    # 2. Review the printed cost, then actually pull + write parquet.
    python pull_futures_trades.py --run

Requires:
    pip install databento pandas pyarrow
    export DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import databento as db
import pandas as pd

DATASET = "GLBX.MDP3"
SCHEMA_TRADES = "trades"
SCHEMA_DEF = "definition"

# root -> (parent symbol used for the pull, output filename)
INSTRUMENTS = {
    "GC": {"parent_symbol": "GC.FUT", "out_file": "gc_trades.parquet"},
    "NQ": {"parent_symbol": "NQ.FUT", "out_file": "nq_trades.parquet"},
}

SIDE_MAP = {
    "A": "sell_initiated",   # Ask side aggressor -> seller-initiated
    "B": "buy_initiated",    # Bid side aggressor -> buyer-initiated
    "N": "unknown",          # no aggressor side recorded
}


def previous_full_month(today: date) -> tuple[str, str, str]:
    """Return (label, start_iso, end_iso) for the most recently completed
    calendar month relative to `today`. end is exclusive."""
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month  # exclusive end = first of this month
    # first of previous month
    prev_month_last_day = first_of_this_month - timedelta(days=1)
    start = prev_month_last_day.replace(day=1)
    label = start.strftime("%Y-%m")
    return label, start.isoformat(), last_month_end.isoformat()


def get_client() -> db.Historical:
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        sys.exit(
            "DATABENTO_API_KEY is not set. Run:\n"
            "    export DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
            "then re-run this script."
        )
    return db.Historical(key)


def estimate_cost(client: db.Historical, start: str, end: str) -> float:
    total = 0.0
    print(f"\nCost estimate for {start} -> {end} (exclusive):")
    for root, cfg in INSTRUMENTS.items():
        trades_cost = client.metadata.get_cost(
            dataset=DATASET,
            symbols=[cfg["parent_symbol"]],
            schema=SCHEMA_TRADES,
            stype_in="parent",
            start=start,
            end=end,
        )
        def_cost = client.metadata.get_cost(
            dataset=DATASET,
            symbols=[cfg["parent_symbol"]],
            schema=SCHEMA_DEF,
            stype_in="parent",
            start=start,
            end=end,
        )
        subtotal = trades_cost + def_cost
        total += subtotal
        print(
            f"  {root:<3} ({cfg['parent_symbol']}): "
            f"trades=${trades_cost:.4f}  definitions=${def_cost:.4f}  "
            f"subtotal=${subtotal:.4f}"
        )
    print(f"  TOTAL ESTIMATE: ${total:.4f}  (against $125 free credit)\n")
    return total


def pull_one_instrument(
    client: db.Historical, root: str, parent_symbol: str, start: str, end: str
) -> pd.DataFrame:
    print(f"[{root}] pulling trades for {parent_symbol} ({start} -> {end})...")
    trades_store = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[parent_symbol],
        schema=SCHEMA_TRADES,
        stype_in="parent",
        start=start,
        end=end,
    )
    trades_df = trades_store.to_df()  # price_type=float, pretty_ts=True by default
    print(f"[{root}] raw trades rows: {len(trades_df):,}")

    print(f"[{root}] pulling instrument definitions to resolve contract symbols...")
    def_store = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[parent_symbol],
        schema=SCHEMA_DEF,
        stype_in="parent",
        start=start,
        end=end,
    )
    def_df = def_store.to_df()

    # Definitions publish (roughly) daily snapshots per instrument; we only
    # need one row per instrument_id. Keep futures only (exclude spreads).
    def_df = def_df[def_df["instrument_class"] == "F"]
    def_df = def_df.drop_duplicates(subset="instrument_id", keep="last")
    def_df = def_df[["instrument_id", "raw_symbol"]]

    merged = trades_df.merge(def_df, on="instrument_id", how="left")
    unresolved = merged["raw_symbol"].isna().sum()
    if unresolved:
        print(
            f"[{root}] WARNING: {unresolved:,} trade rows had no matching "
            f"definition (instrument_id not resolved to a raw_symbol). "
            f"These are dropped."
        )
        merged = merged.dropna(subset=["raw_symbol"])

    merged["aggressor_side"] = merged["side"].map(SIDE_MAP)
    unmapped_side = merged["aggressor_side"].isna().sum()
    if unmapped_side:
        print(
            f"[{root}] WARNING: {unmapped_side:,} rows had an unrecognized "
            f"side value outside A/B/N — check Databento schema docs."
        )

    out = merged.rename(columns={"raw_symbol": "symbol"})[
        ["ts_event", "price", "size", "aggressor_side", "symbol", "instrument_id"]
    ].rename(columns={"ts_event": "timestamp"})

    out = out.sort_values("timestamp").reset_index(drop=True)
    return out


def collapse_to_active_contract(df: pd.DataFrame, root: str) -> pd.DataFrame:
    """Per calendar day, keep only trades from whichever contract traded the
    most volume that day. This is a rough cut, not a hardened roll-splice —
    good enough to validate the strategy signal, not for production."""
    work = df.copy()
    work["trade_date"] = work["timestamp"].dt.date

    daily_volume = (
        work.groupby(["trade_date", "symbol"])["size"].sum().reset_index()
    )
    active = (
        daily_volume.loc[daily_volume.groupby("trade_date")["size"].idxmax()]
        [["trade_date", "symbol"]]
        .rename(columns={"symbol": "active_symbol"})
    )

    merged = work.merge(active, on="trade_date", how="left")
    active_df = merged[merged["symbol"] == merged["active_symbol"]].drop(
        columns=["active_symbol", "trade_date"]
    )

    distinct_contracts = sorted(active_df["symbol"].unique().tolist())
    dropped = len(work) - len(active_df)
    print(
        f"[{root}] active-contract cleanup: kept {len(active_df):,}/"
        f"{len(work):,} rows ({dropped:,} dropped as thin/rolled-off "
        f"contracts). Distinct active contracts in final data: "
        f"{distinct_contracts}"
    )
    return active_df.reset_index(drop=True)


def validate(df: pd.DataFrame, root: str) -> None:
    print(f"\n--- Validation: {root} ---")
    print(f"Row count: {len(df):,}")
    print(f"Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

    side_counts = df["aggressor_side"].value_counts(dropna=False)
    side_pct = (side_counts / len(df) * 100).round(2)
    print("Aggressor side split:")
    for k in side_counts.index:
        print(f"  {k:<14} {side_counts[k]:>10,}  ({side_pct[k]}%)")

    unknown_pct = side_pct.get("unknown", 0.0)
    if unknown_pct > 5.0:
        print(
            f"  WARNING: 'unknown' side is {unknown_pct}% of rows — higher "
            f"than expected, worth a closer look."
        )
    buy_pct = side_pct.get("buy_initiated", 0.0)
    sell_pct = side_pct.get("sell_initiated", 0.0)
    if buy_pct > 90 or sell_pct > 90:
        print(
            "  WARNING: aggressor split is heavily one-sided — check for a "
            "field-mapping bug before trusting this data."
        )

    # Gap check: sort, diff consecutive timestamps, flag anything > 2h.
    # reset_index(drop=True) first so positional index == label index, or
    # the "previous row" lookup below would be wrong (sort_values keeps the
    # original, now-shuffled index labels).
    ts_sorted = df["timestamp"].sort_values().reset_index(drop=True)
    gaps = ts_sorted.diff()
    big_gaps = gaps[gaps > pd.Timedelta(hours=2)].dropna()
    print(f"Gaps > 2h between consecutive trades: {len(big_gaps)}")
    if len(big_gaps):
        print("  Largest gaps (review manually — some daily-halt gaps are expected):")
        top = big_gaps.sort_values(ascending=False).head(10)
        for idx, gap in top.items():
            prior_ts = ts_sorted.iloc[idx - 1]
            curr_ts = ts_sorted.iloc[idx]
            print(f"    {prior_ts} -> {curr_ts}  (gap: {gap})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--month",
        default=None,
        help="Month to pull as YYYY-MM. Defaults to the most recently "
        "completed calendar month.",
    )
    parser.add_argument(
        "--out-dir", default="./data", help="Directory to write parquet files into."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually pull data and write parquet files. Without this "
        "flag, only the cost estimate is printed.",
    )
    args = parser.parse_args()

    if args.month:
        year, month = map(int, args.month.split("-"))
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        label = args.month
        start, end = start_date.isoformat(), end_date.isoformat()
    else:
        label, start, end = previous_full_month(date.today())

    print(f"Target month: {label}  ({start} -> {end}, exclusive)")

    client = get_client()
    total_cost = estimate_cost(client, start, end)

    if not args.run:
        print(
            "Estimate-only run (default). Re-run with --run once you're "
            "happy with the cost above."
        )
        return

    if total_cost > 30.0:
        sys.exit(
            f"Refusing to auto-proceed: estimated cost ${total_cost:.2f} is "
            f"above the $30 safety threshold hardcoded in this script. "
            f"Review manually and raise the threshold if this is expected."
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for root, cfg in INSTRUMENTS.items():
        raw_df = pull_one_instrument(client, root, cfg["parent_symbol"], start, end)
        active_df = collapse_to_active_contract(raw_df, root)
        validate(active_df, root)

        out_path = out_dir / cfg["out_file"]
        active_df.to_parquet(out_path, index=False)
        print(f"[{root}] wrote {len(active_df):,} rows -> {out_path}\n")

    print("Done. Remember: no delta/CVD/aggregation yet — that's tomorrow.")


if __name__ == "__main__":
    main()
