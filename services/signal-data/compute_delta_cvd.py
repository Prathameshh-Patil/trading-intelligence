#!/usr/bin/env python3
"""
Turn raw GC (COMEX gold futures) trade prints into delta, CVD and a
price-level footprint, and render the plots used to validate them against a
reference footprint chart.

Input is the parquet written by `pull_futures_trades.py`:
    timestamp (UTC), price, size, aggressor_side, symbol, instrument_id

AGGRESSOR-SIDE CONVENTION (confirmed against Databento's schema docs)
    Databento's `trades` schema carries a `side` field defined as "the side
    that initiates the trade" -- i.e. the aggressor, not the resting side:

        B (Bid) -> the AGGRESSOR WAS A BUYER. They lifted the offer.  delta = +size
        A (Ask) -> the AGGRESSOR WAS A SELLER. They hit the bid.      delta = -size
        N        -> no side disseminated (auction, implied, off-book). delta = 0

    `pull_futures_trades.py` has already mapped these to the strings
    buy_initiated / sell_initiated / unknown.

    The trap worth naming: "Ask" does NOT mean "printed at the ask". It means
    the resting order that got taken was a sell order -- which makes the trade
    seller-initiated. Reading it the natural-language way inverts the sign and
    produces a mirror-image CVD that looks completely plausible.

USAGE
    python compute_delta_cvd.py --parquet data/gc_trades.parquet \
        --session 2026-07-16 --out-dir analysis
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: write PNGs, never try to open a window

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from s1 import load_ticks, minute_bars, session_cvd

# The load / delta / bar layer lives in s1.py, against the S1 tick contract, so
# this script and the backtest harness cannot disagree about what a session or a
# bar is. It used to be duplicated here against the pull script's own encoding,
# which read the S1 fixture as zero delta on every row without complaining.
DISPLAY_TZ = "America/New_York"

# Palette roles (see the data-viz reference palette). Diverging blue<->red for
# signed delta -- warm/cool poles that read as opposites, neutral gray at zero.
C_BUY = "#2a78d6"      # positive delta / buy aggressor
C_SELL = "#e34948"     # negative delta / sell aggressor
C_PRICE = "#0b0b0b"    # primary ink -- price is not a "series", it's context
C_CVD = "#2a78d6"
C_SURFACE = "#fcfcfb"
C_GRID = "#e1e0d9"
C_AXIS = "#c3c2b7"
C_MUTED = "#898781"
C_SECONDARY = "#52514e"


# --------------------------------------------------------------------------
# Core signal
# --------------------------------------------------------------------------
def footprint(df: pd.DataFrame) -> pd.DataFrame:
    """Delta aggregated by PRICE LEVEL rather than by time -- net buy/sell
    volume at each traded price. This is the view that catches a sign error
    that a CVD line can hide: absorption and imbalance are anchored to
    specific prices, so they either agree with the reference chart at those
    prices or they don't."""
    buy = df["delta"].clip(lower=0)
    sell = (-df["delta"]).clip(lower=0)
    fp = (
        df.assign(buy_vol=buy, sell_vol=sell)
        .groupby("price", as_index=False)
        .agg(
            buy_vol=("buy_vol", "sum"),
            sell_vol=("sell_vol", "sum"),
            total_vol=("size", "sum"),
            trades=("size", "size"),
        )
    )
    fp["delta"] = fp["buy_vol"] - fp["sell_vol"]
    fp["dominant"] = np.where(fp["delta"] > 0, "buy", np.where(fp["delta"] < 0, "sell", "flat"))
    return fp.sort_values("price", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Plots
# --------------------------------------------------------------------------
def _style_axis(ax) -> None:
    ax.set_facecolor(C_SURFACE)
    ax.grid(True, color=C_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C_AXIS)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=C_MUTED, labelsize=9, length=0)


def plot_session_cvd(
    trades: pd.DataFrame, bars: pd.DataFrame, session: str, symbol: str, out_path: Path
) -> None:
    """Three stacked panels on a shared time axis -- deliberately NOT a
    twin-axis chart. Price and CVD have unrelated units, and overlaying them
    on two y-scales lets you slide the scales until any two lines appear to
    agree. Shared x, separate y, is the honest version: divergences have to be
    read off the time axis rather than manufactured by scaling."""
    tz = DISPLAY_TZ
    t_trades = trades["timestamp"].dt.tz_convert(tz)
    t_bars = bars.index.tz_convert(tz)

    fig, axes = plt.subplots(
        3, 1, figsize=(13, 10), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 2.2, 1.4], "hspace": 0.12},
    )
    fig.patch.set_facecolor(C_SURFACE)

    # -- Panel 1: price -----------------------------------------------------
    ax = axes[0]
    _style_axis(ax)
    ax.plot(t_trades, trades["price"], color=C_PRICE, linewidth=1.0)
    ax.set_ylabel("Price  (USD/oz)", color=C_SECONDARY, fontsize=10)
    ax.set_title(
        f"{symbol} — {session} CME session · price, cumulative delta, 1-minute delta",
        color="#0b0b0b", fontsize=13, pad=14, loc="left", fontweight="bold",
    )

    # -- Panel 2: continuous CVD -------------------------------------------
    ax = axes[1]
    _style_axis(ax)
    ax.axhline(0, color=C_AXIS, linewidth=1.0)
    ax.plot(t_trades, trades["cvd"], color=C_CVD, linewidth=1.6)
    ax.set_ylabel("CVD  (contracts, cumulative)", color=C_SECONDARY, fontsize=10)

    final = trades["cvd"].iloc[-1]
    ax.annotate(
        f"close {final:+,.0f}",
        xy=(t_trades.iloc[-1], final),
        xytext=(-8, 10 if final >= 0 else -18),
        textcoords="offset points",
        ha="right", fontsize=10, color=C_SECONDARY, fontweight="bold",
    )

    # -- Panel 3: 1-minute delta (diverging) --------------------------------
    ax = axes[2]
    _style_axis(ax)
    ax.axhline(0, color=C_AXIS, linewidth=1.0)
    colors = np.where(bars["delta"] >= 0, C_BUY, C_SELL)
    ax.bar(t_bars, bars["delta"], width=1 / 1440, color=colors, linewidth=0)
    ax.set_ylabel("1-min delta", color=C_SECONDARY, fontsize=10)
    ax.set_xlabel(f"Time ({tz})", color=C_SECONDARY, fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=t_bars.tz))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))

    # Identity is not carried by color alone: name the two signs in text.
    ax.text(
        0.005, -0.42,
        "Blue = net buy-aggressor minute (positive delta)   ·   "
        "Red = net sell-aggressor minute (negative delta)   ·   "
        "B = buyer lifted the offer (+size), A = seller hit the bid (−size)",
        transform=ax.transAxes, fontsize=9, color=C_MUTED, va="top",
    )

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)


def bin_footprint(fp: pd.DataFrame, bin_size: float) -> pd.DataFrame:
    """Roll the per-tick footprint up into fixed price bins for plotting.

    Plotting every 0.1 tick over a ~100-point session is 1,000 hairlines, and
    picking the top-N levels by volume instead leaves non-contiguous gaps that
    read as "no trade here" when the truth is "traded, just not in the top N".
    A footprint is a contiguous ladder or it misleads. The per-tick detail is
    still written to CSV -- this is a display rollup only."""
    lo = np.floor(fp["price"].min() / bin_size) * bin_size
    hi = np.ceil(fp["price"].max() / bin_size) * bin_size
    edges = np.arange(lo, hi + bin_size, bin_size)
    centres = edges[:-1] + bin_size / 2

    idx = np.clip(np.digitize(fp["price"], edges) - 1, 0, len(centres) - 1)
    out = (
        fp.assign(_bin=centres[idx])
        .groupby("_bin", as_index=False)
        .agg(buy_vol=("buy_vol", "sum"), sell_vol=("sell_vol", "sum"),
             total_vol=("total_vol", "sum"))
        .rename(columns={"_bin": "price"})
    )
    out["delta"] = out["buy_vol"] - out["sell_vol"]
    # Reindex onto the full ladder so untraded bins stay visible as gaps of
    # zero rather than vanishing and compressing the axis.
    full = pd.DataFrame({"price": centres})
    return full.merge(out, on="price", how="left").fillna(0.0)


def plot_footprint(fp_binned: pd.DataFrame, session: str, symbol: str,
                   out_path: Path, bin_size: float) -> None:
    """Horizontal diverging bars on a contiguous price ladder. Price on the
    vertical axis, the way a footprint chart stacks it, so levels can be read
    straight across against the reference."""
    top = fp_binned.sort_values("price")
    height = bin_size * 0.82

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13, 11), sharey=True,
        gridspec_kw={"width_ratios": [1.6, 1.0], "wspace": 0.06},
    )
    fig.patch.set_facecolor(C_SURFACE)

    for ax in (ax1, ax2):
        _style_axis(ax)

    colors = np.where(top["delta"] >= 0, C_BUY, C_SELL)
    ax1.barh(top["price"], top["delta"], height=height, color=colors, linewidth=0)
    ax1.axvline(0, color=C_AXIS, linewidth=1.0)
    ax1.set_xlabel("Net delta at price  (buy − sell volume)", color=C_SECONDARY, fontsize=10)
    ax1.set_ylabel("Price  (USD/oz)", color=C_SECONDARY, fontsize=10)
    ax1.set_title(
        f"{symbol} — {session} footprint: net delta by price level",
        color="#0b0b0b", fontsize=13, pad=14, loc="left", fontweight="bold",
    )

    ax2.barh(top["price"], top["total_vol"], height=height, color=C_MUTED, linewidth=0)
    ax2.set_xlabel("Total volume at price", color=C_SECONDARY, fontsize=10)
    ax2.set_title(
        f"volume profile · ${bin_size:g} price bins", color=C_SECONDARY, fontsize=11,
        pad=14, loc="left",
    )

    ax1.text(
        0.0, -0.055,
        "Blue = buy-dominant level (compare to the reference chart's buy-side "
        "colour)   ·   Red = sell-dominant level",
        transform=ax1.transAxes, fontsize=9, color=C_MUTED, va="top",
    )

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)


def plot_month_cvd(bars: pd.DataFrame, out_path: Path, symbol_label: str) -> None:
    """Whole-month view, CVD reset per session. Context for the single
    validated session -- it shows whether that session's behaviour is typical
    or an outlier."""
    fig, axes = plt.subplots(
        2, 1, figsize=(13, 7), sharex=True,
        gridspec_kw={"height_ratios": [1.4, 1.0], "hspace": 0.12},
    )
    fig.patch.set_facecolor(C_SURFACE)

    ax = axes[0]
    _style_axis(ax)
    ax.plot(bars.index, bars["close"], color=C_PRICE, linewidth=1.0)
    ax.set_ylabel("Price  (USD/oz)", color=C_SECONDARY, fontsize=10)
    ax.set_title(
        f"{symbol_label} — July 2026, 1-minute bars · price and per-session CVD",
        color="#0b0b0b", fontsize=13, pad=14, loc="left", fontweight="bold",
    )

    ax = axes[1]
    _style_axis(ax)
    ax.axhline(0, color=C_AXIS, linewidth=1.0)
    for _, seg in bars.groupby("session", sort=True):
        ax.plot(seg.index, seg["cvd"], color=C_CVD, linewidth=1.1)
    ax.set_ylabel("CVD  (per session)", color=C_SECONDARY, fontsize=10)
    ax.set_xlabel("Date (UTC)", color=C_SECONDARY, fontsize=10)

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet", default="data/gc_trades.parquet")
    ap.add_argument("--session", default=None,
                    help="Validation session as YYYY-MM-DD (CME trading day). "
                         "Default: the most directionally clean session found.")
    ap.add_argument("--out-dir", default="analysis")
    ap.add_argument("--price-bin", type=float, default=1.0,
                    help="Price bin size for the footprint PLOT, in USD. The "
                         "CSV always keeps full 0.1-tick resolution.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_ticks(Path(args.parquet))
    print(f"loaded {len(df):,} trades  "
          f"{df['timestamp'].min()} -> {df['timestamp'].max()}")

    counts = df["aggressor_side"].value_counts()
    pct = (counts / len(df) * 100).round(2)
    print("\naggressor split:")
    for k in counts.index:
        print(f"  {k:<15}{counts[k]:>12,}   {pct[k]:>6}%")
    print(f"\nmonth net delta: {df['delta'].sum():+,}  "
          f"on {df['size'].sum():,} contracts "
          f"({df['delta'].sum() / df['size'].sum() * 100:+.2f}% imbalance)")

    df = df.assign(cvd=session_cvd(df))
    bars = minute_bars(df)
    bars.to_csv(out_dir / "gc_minute_bars_2026-07.csv")
    print(f"\nwrote {len(bars):,} 1-minute bars -> "
          f"{out_dir / 'gc_minute_bars_2026-07.csv'}")

    # ---- choose the validation session ----------------------------------
    if args.session:
        session = pd.Timestamp(args.session).date()
    else:
        stats = []
        for s, d in df.groupby("session"):
            if len(d) < 20_000:
                continue
            rng = d["price"].max() - d["price"].min()
            if not rng:
                continue
            stats.append((abs(d["price"].iloc[-1] - d["price"].iloc[0]) / rng, s))
        session = max(stats)[1]
        print(f"\nauto-selected cleanest trending session: {session}")

    sess = df[df["session"] == session].copy()
    if sess.empty:
        raise SystemExit(f"no trades for session {session}")
    sess["cvd"] = sess["delta"].cumsum()
    sym = sess["symbol"].mode().iloc[0]
    sbars = bars[bars["session"] == session]

    fp = footprint(sess)
    fp.to_csv(out_dir / f"gc_footprint_{session}.csv", index=False)
    fp_binned = bin_footprint(fp, args.price_bin)

    plot_session_cvd(sess, sbars, str(session), sym, out_dir / f"gc_cvd_{session}.png")
    plot_footprint(fp_binned, str(session), sym,
                   out_dir / f"gc_footprint_{session}.png", args.price_bin)
    plot_month_cvd(bars, out_dir / "gc_cvd_month_2026-07.png", "GC (front month)")

    # ---- session report --------------------------------------------------
    et = sess["timestamp"].dt.tz_convert(DISPLAY_TZ)
    print(f"\n===== validation session {session}  ({sym}) =====")
    print(f"trades            {len(sess):,}")
    print(f"volume            {sess['size'].sum():,} contracts")
    print(f"UTC window        {sess['timestamp'].min()}  ->  {sess['timestamp'].max()}")
    print(f"{DISPLAY_TZ:<18}{et.min()}  ->  {et.max()}")
    print(f"price             open {sess['price'].iloc[0]:.1f}  "
          f"high {sess['price'].max():.1f}  low {sess['price'].min():.1f}  "
          f"close {sess['price'].iloc[-1]:.1f}  "
          f"({sess['price'].iloc[-1] - sess['price'].iloc[0]:+.1f})")
    print(f"session CVD close {sess['cvd'].iloc[-1]:+,}")
    print(f"CVD high / low    {sess['cvd'].max():+,} / {sess['cvd'].min():+,}")

    print("\n-- hourly delta (read these against the reference chart) --")
    hourly = sess.set_index("timestamp").tz_convert(DISPLAY_TZ).resample("1h").agg(
        delta=("delta", "sum"), volume=("size", "sum"), close=("price", "last"))
    hourly = hourly[hourly["volume"] > 0]
    hourly["cvd"] = hourly["delta"].cumsum()
    print(hourly.to_string())

    print("\n-- 12 highest-volume price levels --")
    top = fp.reindex(fp["total_vol"].sort_values(ascending=False).index[:12])
    print(top[["price", "buy_vol", "sell_vol", "delta", "total_vol", "dominant"]]
          .to_string(index=False))

    print(f"\nplots -> {out_dir}/")


if __name__ == "__main__":
    main()
