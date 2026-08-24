#!/usr/bin/env python3
"""
Independent aggressor-side validation for GC, via Databento's TBBO schema.

WHAT THIS CLOSES
    Everything in DELTA_CVD_FINDINGS.md section 1 is INTERNAL consistency --
    the data agreeing with itself and with published schema semantics. The
    tick-rule check (~83%) is the strongest of those, and it is still a
    heuristic run on the same trade prints.

    TBBO carries, for every trade, the best bid and offer IMMEDIATELY BEFORE
    that trade. That lets each trade be classified by the QUOTE RULE --
    at/through the offer = buyer aggressed, at/through the bid = seller
    aggressed -- computed from the book state, with no reference to the
    `side` field at all.

        tick rule (already done)        ~83% accurate
        quote rule with real bid/ask    ~99% accurate  <-- this script
        TradingView CVD @ 5-min intrabar  degenerate; cannot detect
                                          absorption by construction

    The risk being tested is NOT "is Databento's `side` field wrong". It is
    "did SIDE_MAP invert B/A". The quote rule tests that interpretation
    directly and independently.

    HONEST LIMIT: the quote rule and the `side` tag both originate in the
    same MDP 3.0 feed, so this is not a second exchange confirming the first.
    It is a second, far more accurate derivation -- enough to catch an
    inverted mapping, a magnitude error, or a broken footprint, which is the
    failure set still open.

COST
    TBBO is one record per trade -- same row count as the trades schema, a
    few extra columns. Pulling a SINGLE raw_symbol (GCQ6) rather than the
    GC.FUT parent avoids paying for every other gold contract and every
    calendar spread.

    The default window is the ONE DISPUTED HOUR (12:00-13:00 UTC =
    08:00-09:00 ET), ~8k trades. Nearly all the information is there; do not
    buy the whole session until the hour clears.

USAGE
    # 1. Cost check first -- does NOT spend anything.
    python pull_tbbo_validate.py --estimate-only

    # 2. The disputed hour only.
    python pull_tbbo_validate.py --run

    # 3. Only once the hour passes: full session, for the footprint.
    python pull_tbbo_validate.py --run \
        --start 2026-07-15T22:00 --end 2026-07-16T21:00 --footprint

Requires:
    pip install databento pandas pyarrow python-dotenv
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import databento as db
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DATASET = "GLBX.MDP3"
SCHEMA = "tbbo"

# Must match pull_futures_trades.py exactly. This is the mapping under test.
SIDE_MAP = {
    "A": "sell_initiated",   # Ask side aggressor -> seller-initiated
    "B": "buy_initiated",    # Bid side aggressor -> buyer-initiated
    "N": "unknown",          # no aggressor side recorded
}

BUY, SELL = "buy_initiated", "sell_initiated"

# Databento encodes an undefined price as INT64_MAX, which surfaces through
# to_df(price_type="float") as ~9.22e9 rather than NaN. Any real gold quote is
# orders of magnitude below this, so a plain magnitude guard is enough.
UNDEF_GUARD = 1e9


def get_client() -> db.Historical:
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        sys.exit(
            "DATABENTO_API_KEY is not set.\n"
            "Copy .env.example to .env in this folder and paste your real key "
            "in there (DATABENTO_API_KEY=db-...), then re-run."
        )
    return db.Historical(key)


def estimate_cost(client: db.Historical, symbol: str, start: str, end: str) -> float:
    cost = client.metadata.get_cost(
        dataset=DATASET,
        symbols=[symbol],
        schema=SCHEMA,
        stype_in="raw_symbol",
        start=start,
        end=end,
    )
    print(f"\nCost estimate — {SCHEMA} / {symbol} / {start} -> {end}")
    print(f"  ESTIMATE: ${cost:.4f}   (against $125 sign-up credit)\n")
    return cost


def fetch_or_load(
    client: db.Historical, symbol: str, start: str, end: str, raw_dir: Path
) -> db.DBNStore:
    """Same discipline as pull_futures_trades.py: billing happens inside
    get_range(), so the raw DBN hits disk BEFORE any pandas code can fail on
    it. A processing bug then costs nothing to retry.

    Delete the cache file to force a genuine (billable) re-download."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{symbol}_{SCHEMA}_{start}_{end}".replace(":", "").replace("-", "")
    cache_path = raw_dir / f"{tag}.dbn.zst"

    if cache_path.exists():
        size_mb = cache_path.stat().st_size / 1_048_576
        print(f"CACHED: reusing {cache_path} ({size_mb:,.2f} MB) — no API call, no cost.")
        return db.DBNStore.from_file(cache_path)

    print(f"Downloading {SCHEMA} for {symbol} ({start} -> {end})...")
    store = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[symbol],
        schema=SCHEMA,
        stype_in="raw_symbol",
        start=start,
        end=end,
    )
    store.to_file(cache_path)
    size_mb = cache_path.stat().st_size / 1_048_576
    print(f"SAVED raw {SCHEMA} -> {cache_path} ({size_mb:,.2f} MB). Reprocessing is now free.")
    return store


def classify_quote_rule(df: pd.DataFrame) -> pd.DataFrame:
    """Label each trade by the quote rule, using ONLY bid_px_00/ask_px_00.

    Precedence (np.select takes the first match):
        price >= ask   -> buyer lifted the offer
        price <= bid   -> seller hit the bid
        inside spread  -> whichever side of the midpoint it fell on
        exactly at mid -> indeterminate, left as NA and excluded from the
                          agreement statistic rather than guessed at
    """
    bid, ask, price = df["bid_px_00"], df["ask_px_00"], df["price"]

    have_quote = (
        bid.notna() & ask.notna()
        & (bid > 0) & (ask > 0)
        & (bid < UNDEF_GUARD) & (ask < UNDEF_GUARD)
        & (ask > bid)          # excludes locked/crossed books; counted below
    )
    mid = (bid + ask) / 2.0

    df = df.copy()
    df["quote_label"] = np.select(
        [
            have_quote & (price >= ask),
            have_quote & (price <= bid),
            have_quote & (price > mid),
            have_quote & (price < mid),
        ],
        [BUY, SELL, BUY, SELL],
        default=None,
    )
    df["have_quote"] = have_quote

    n = len(df)
    no_quote = int((~have_quote).sum())
    at_mid = int((have_quote & df["quote_label"].isna()).sum())
    print("\n--- Quote-rule classification ---")
    print(f"  trades                      {n:>10,}")
    print(f"  usable two-sided quote      {int(have_quote.sum()):>10,}  "
          f"({have_quote.mean() * 100:.2f}%)")
    print(f"  no/locked/crossed quote     {no_quote:>10,}  (excluded)")
    print(f"  exactly at midpoint         {at_mid:>10,}  (indeterminate, excluded)")
    return df


def compare(df: pd.DataFrame, expected_delta: float | None) -> pd.DataFrame:
    """The actual test: does the quote rule agree with SIDE_MAP?

    Returns the frame enriched with `side_label` and `_size` so the hourly
    breakdown can reuse them.
    """
    size = df["size"].astype("int64")   # uint32 negation wraps to ~4.29e9

    df = df.assign(
        side_label=df["side"].map(SIDE_MAP),
        _size=size,
    )

    both = df[df["side_label"].isin([BUY, SELL]) & df["quote_label"].isin([BUY, SELL])]
    if both.empty:
        sys.exit("No comparable rows — cannot evaluate. Check the window and symbol.")

    agree = float((both["side_label"] == both["quote_label"]).mean())

    print("\n--- Agreement: `side` field vs quote rule ---")
    print(f"  comparable trades           {len(both):>10,}")
    print(f"  agreement                   {agree * 100:>9.2f}%")

    # Pass numpy arrays, not Series: crosstab aligns on the index, and a
    # duplicate-label index (which TBBO has naturally) makes it raise.
    xtab = pd.crosstab(
        both["side_label"].to_numpy(),
        both["quote_label"].to_numpy(),
        rownames=["side_label"],
        colnames=["quote_label"],
    )
    print("\n  confusion (rows = SIDE_MAP, cols = quote rule):")
    for line in xtab.to_string().splitlines():
        print(f"    {line}")

    # --- Delta both ways ------------------------------------------------
    # Both deltas MUST be summed over the same rows. The quote rule excludes
    # trades with no usable quote or sitting exactly at the midpoint; if the
    # `side` delta were taken over the full population while the quote delta
    # skipped those, the two would differ for reasons that have nothing to do
    # with classification and the sign test below would fire spuriously.
    def signed(frame: pd.DataFrame, col: str) -> int:
        lab = frame[col]
        return int(np.where(lab == BUY, frame["_size"],
                   np.where(lab == SELL, -frame["_size"], 0)).sum())

    delta_side_cmp = signed(both, "side_label")
    delta_quote_cmp = signed(both, "quote_label")
    delta_side_all = signed(df, "side_label")

    excluded_vol = int(df["_size"].sum() - both["_size"].sum())

    print("\n--- Window delta ---")
    print("  On the comparable subset (same rows, the only fair comparison):")
    print(f"    from `side` field (SIDE_MAP)   {delta_side_cmp:>+10,}")
    print(f"    from quote rule (independent)  {delta_quote_cmp:>+10,}")
    print("\n  For context, over ALL rows — this is what compute_delta_cvd.py produces:")
    print(f"    from `side` field, full window {delta_side_all:>+10,}")
    print(f"    volume excluded by quote rule  {excluded_vol:>10,} contracts")
    if expected_delta is not None:
        print(f"    your reported figure           {expected_delta:>+10,.0f}")

    # --- Verdict --------------------------------------------------------
    print("\n--- Verdict ---")
    if agree >= 0.95:
        print(
            f"  CONFIRMED. {agree * 100:.2f}% agreement. SIDE_MAP is not inverted,\n"
            f"  and this is independent of the schema docs and of the tick rule."
        )
        if delta_side_cmp * delta_quote_cmp < 0:
            print(
                f"  BUT the two deltas DISAGREE IN SIGN ({delta_side_cmp:+,} vs "
                f"{delta_quote_cmp:+,}).\n"
                f"  High per-trade agreement with opposite aggregate sign means the\n"
                f"  disagreements are concentrated in the large prints. Do NOT\n"
                f"  proceed. Re-run weighting agreement by size, and inspect the\n"
                f"  largest disagreeing trades individually."
            )
        else:
            print(
                f"  Both methods give delta of the same sign ({delta_side_cmp:+,} vs "
                f"{delta_quote_cmp:+,})."
            )
            if delta_quote_cmp == 0 or delta_side_cmp == 0:
                print(
                    "  One side is flat, so this window carries no directional\n"
                    "  evidence either way. Widen the window before concluding."
                )
            else:
                print(
                    "  Net aggressor flow over this window is independently\n"
                    "  corroborated, sign and rough magnitude both.\n\n"
                    "  This does NOT by itself close gate item (a). A whole-session\n"
                    "  total is consistent with many different intra-session paths.\n"
                    "  The shape check lives in the hourly table below -- read the\n"
                    "  specific window you are arguing about, not the total."
                )
    elif agree <= 0.05:
        print(
            f"  *** INVERTED. {agree * 100:.2f}% agreement. ***\n"
            f"  SIDE_MAP has B/A backwards. Every delta, CVD and footprint\n"
            f"  produced so far is sign-flipped. Fix SIDE_MAP, re-run\n"
            f"  compute_delta_cvd.py, and re-check everything downstream."
        )
    else:
        print(
            f"  AMBIGUOUS. {agree * 100:.2f}% agreement is neither a confirmation\n"
            f"  (>=95%) nor a clean inversion (<=5%). Something structural is off\n"
            f"  -- stale quotes, a symbol mismatch, or a timestamp alignment bug\n"
            f"  between trade and book. Investigate before trusting either number."
        )

    return df


def hourly_breakdown(df: pd.DataFrame) -> None:
    """Delta per hour, computed both ways over the comparable subset.

    This is the CVD-SHAPE check (gate item a) at hourly resolution, and it is
    the only thing that speaks to a specific window like 08:00-09:00 ET. A
    whole-session delta cannot: a session total of +1,842 is consistent with
    almost any intra-session path, including one where the disputed hour ran
    negative. Read the 12:00 UTC row, not the session total.
    """
    ts_col = "ts_event" if "ts_event" in df.columns else "ts_recv"
    if ts_col not in df.columns:
        print("\n(no timestamp column — skipping hourly breakdown)")
        return

    work = df[
        df["side_label"].isin([BUY, SELL]) & df["quote_label"].isin([BUY, SELL])
    ].copy()
    work["_size"] = work["size"].astype("int64")
    work["hour"] = work[ts_col].dt.floor("h")

    work["d_side"] = np.where(work["side_label"] == BUY, work["_size"], -work["_size"])
    work["d_quote"] = np.where(work["quote_label"] == BUY, work["_size"], -work["_size"])

    g = work.groupby("hour").agg(
        trades=("_size", "size"),
        volume=("_size", "sum"),
        delta_side=("d_side", "sum"),
        delta_quote=("d_quote", "sum"),
    ).reset_index()

    et = ZoneInfo("America/New_York")
    print("\n--- Delta by hour (comparable subset, both methods) ---")
    print(f"  {'UTC':<6}{'ET':<8}{'trades':>8}{'volume':>9}"
          f"{'side':>9}{'quote':>9}  agree?")
    disagreements = 0
    for _, r in g.iterrows():
        h_utc = r["hour"]
        h_et = h_utc.tz_convert(et)
        same = (r["delta_side"] > 0) == (r["delta_quote"] > 0)
        if not same:
            disagreements += 1
        flag = "" if same else "   <== SIGN DISAGREES"
        print(
            f"  {h_utc.strftime('%H:%M'):<6}{h_et.strftime('%H:%M'):<8}"
            f"{int(r['trades']):>8,}{int(r['volume']):>9,}"
            f"{int(r['delta_side']):>+9,}{int(r['delta_quote']):>+9,}{flag}"
        )

    print(f"\n  hours where the two methods disagree in sign: "
          f"{disagreements} of {len(g)}")


def build_footprint(df: pd.DataFrame, out_path: Path) -> None:
    """Per-price-level net delta from quote-rule labels. This is gate item
    (b) -- the piece no free charting platform will give you."""
    work = df[df["quote_label"].isin([BUY, SELL])].copy()
    work["_size"] = work["size"].astype("int64")
    work["buy_vol"] = np.where(work["quote_label"] == BUY, work["_size"], 0)
    work["sell_vol"] = np.where(work["quote_label"] == SELL, work["_size"], 0)

    fp = work.groupby("price")[["buy_vol", "sell_vol"]].sum().reset_index()
    fp["delta"] = fp["buy_vol"] - fp["sell_vol"]
    fp["total_vol"] = fp["buy_vol"] + fp["sell_vol"]
    fp = fp.sort_values("price", ascending=False)

    fp.to_csv(out_path, index=False)
    print(f"\n--- Footprint (quote-rule) ---")
    print(f"  {len(fp):,} price levels -> {out_path}")
    print(f"  strongest buy level:  {fp.loc[fp['delta'].idxmax(), 'price']:.1f} "
          f"({int(fp['delta'].max()):+,})")
    print(f"  strongest sell level: {fp.loc[fp['delta'].idxmin(), 'price']:.1f} "
          f"({int(fp['delta'].min()):+,})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="GCQ6",
                        help="Exchange raw_symbol. GCQ6 = Aug 2026 gold.")
    parser.add_argument("--start", default="2026-07-16T12:00",
                        help="UTC. Default = 08:00 ET, start of the disputed hour.")
    parser.add_argument("--end", default="2026-07-16T13:00",
                        help="UTC. Default = 09:00 ET, end of the disputed hour.")
    parser.add_argument("--expected-delta", type=float, default=1083.0,
                        help="Your reported delta for this window, for comparison.")
    parser.add_argument("--out-dir", default="./analysis")
    parser.add_argument("--raw-dir", default="./data/raw")
    parser.add_argument("--footprint", action="store_true",
                        help="Also write a per-price footprint CSV. Use on a full session.")
    parser.add_argument("--estimate-only", action="store_true",
                        help="Print the cost estimate and exit. This is the default.")
    parser.add_argument("--run", action="store_true",
                        help="Actually pull. Without this, only the estimate prints.")
    parser.add_argument("--max-cost", type=float, default=5.0,
                        help="Refuse to pull above this estimated cost.")
    args = parser.parse_args()

    client = get_client()
    cost = estimate_cost(client, args.symbol, args.start, args.end)

    if not args.run:
        print("Estimate-only run (default). Re-run with --run once you're happy.")
        return

    if cost > args.max_cost:
        sys.exit(
            f"Refusing to proceed: ${cost:.4f} exceeds --max-cost ${args.max_cost:.2f}. "
            f"Narrow the window or raise the threshold deliberately."
        )

    store = fetch_or_load(client, args.symbol, args.start, args.end, Path(args.raw_dir))
    df = store.to_df()

    # to_df() indexes on ts_recv, and many trades share a timestamp to the
    # nanosecond -- sweeps through multiple price levels all print at once. A
    # DatetimeIndex with duplicate labels makes pd.crosstab blow up with
    # "cannot reindex on an axis with duplicate labels". Flatten to a clean
    # RangeIndex up front so every downstream op is index-safe, keeping the
    # timestamp as an ordinary column where it is still useful.
    if df.index.name and df.index.name not in df.columns:
        df = df.reset_index()
    else:
        df = df.reset_index(drop=True)

    print(f"\nRows: {len(df):,}")

    if df.empty:
        sys.exit("Empty result. Check the symbol is valid for this date range.")

    # A single raw_symbol pull should yield exactly one contract. If it does
    # not, the window straddles something unexpected and the comparison would
    # be mixing instruments.
    if "symbol" in df.columns:
        contracts = sorted(df["symbol"].unique().tolist())
        print(f"Contracts in result: {contracts}")
        if len(contracts) > 1:
            sys.exit(f"Expected one contract, got {contracts}. Aborting.")

    missing = {"price", "size", "side", "bid_px_00", "ask_px_00"} - set(df.columns)
    if missing:
        sys.exit(f"TBBO frame is missing expected columns: {sorted(missing)}")

    df = classify_quote_rule(df)
    df = compare(df, args.expected_delta)
    hourly_breakdown(df)

    if args.footprint:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        day = args.start.split("T")[0]
        build_footprint(df, out_dir / f"gc_footprint_quoterule_{day}.csv")


if __name__ == "__main__":
    main()
