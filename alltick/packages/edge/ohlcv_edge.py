"""Is there anything in AllTick's gold candles that OHLCV-only features can find?

The vendor question is downstream of this one. AllTick gives no order flow (GOLD.md
§1-§4), so anything built on it must come out of open/high/low/close/volume. If
nothing survives here on years of free bars, there is no tier worth pricing.

Two parts, cheapest first:

  1. THE RANDOM-WALK CHECK, which is horizon.py's method pointed at a different
     instrument. If dispersion grows as sqrt(h) and the overlap correlation between
     adjacent bars' legs lands on (h-b)/h, the series has no unconditional structure
     at these horizons and every rule below is trying to beat a coin.

  2. A FEATURE SWEEP AGAINST A PERMUTATION NULL. Four OHLCV rules over a grid of
     thresholds, each measured through backtest.evaluate so the leg semantics are
     the kill gate's own. The null permutes forward moves within session, which
     destroys any feature-to-outcome link while preserving the feature
     distribution, the trade count and the side mix. Because the whole grid is
     searched on the real data, the null is the BEST-OF-GRID on shuffled data --
     otherwise the sweep would find something by construction.

NO THRESHOLD HERE IS COMMITTED. The grid exists to map the space, not to pick a
point in it, and the pass/fail line is Varad's under thresholds_selector.md §6.1.
This file reports; it does not decide.

    services/signal-data/.venv/bin/python packages/edge/ohlcv_edge.py \
        --bars data/klines/GOLD_5m.jsonl --interval-minutes 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services" / "signal-data"))

# Imported after the path insert above; s1.TICK is 0.10, so every move below
# reads in GC-tick equivalents and is directly comparable to horizon.py.
import backtest
from s1 import TICK

HORIZONS = backtest.HORIZONS
SESSION_GAP = pd.Timedelta(minutes=45)  # gold's daily break is 60m; weekends are longer


def load_bars(path: Path) -> pd.DataFrame:
    """AllTick candles -> the frame backtest.evaluate expects.

    Sessions are cut on gaps rather than on a clock offset. s1.py's +2h shift
    assumes the summer Globex window; this data spans years, so the break moves
    with DST and only the gap itself is reliable.
    """
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    df = pd.DataFrame(rows).drop_duplicates(subset="timestamp")
    df["t"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="s", utc=True)
    for src, dst in (("open_price", "open"), ("high_price", "high"),
                     ("low_price", "low"), ("close_price", "close")):
        df[dst] = df[src].astype("float64")
    df["volume"] = df["volume"].astype("float64")
    bars = df.set_index("t").sort_index()[["open", "high", "low", "close", "volume"]]
    gap = bars.index.to_series().diff() > SESSION_GAP
    bars["session"] = gap.cumsum().to_numpy()
    return bars


def forward_moves(bars: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    """Move in ticks from each bar's close, session-bounded, clock-based.

    Vectorised twin of backtest.evaluate's move columns; verified against it in
    check_against_backtest below rather than assumed equivalent.
    """
    out = {}
    idx = bars.index
    ends = bars.groupby("session", sort=False).apply(lambda g: g.index[-1], include_groups=False)
    session_end = pd.DatetimeIndex(bars["session"].map(ends))
    for h in horizons:
        mark = idx + pd.Timedelta(minutes=h)
        # Last close at or before the mark; NaN where the session ends first.
        pos = np.searchsorted(idx.to_numpy(), mark.to_numpy(), side="right") - 1
        move = (bars["close"].to_numpy()[pos] - bars["close"].to_numpy()) / TICK
        same_session = bars["session"].to_numpy()[pos] == bars["session"].to_numpy()
        out[f"move_{h}m"] = np.where(same_session & (session_end >= mark), move, np.nan)
    return pd.DataFrame(out, index=idx)


def check_against_backtest(bars: pd.DataFrame, fwd: pd.DataFrame, n: int = 300) -> None:
    """The fast path is only usable if it agrees with the real harness."""
    sample = bars.index[::max(len(bars) // n, 1)]
    entries = pd.Series(0, index=bars.index, dtype="int64")
    entries.loc[sample] = 1
    trades = backtest.evaluate(bars, entries).set_index("t")
    for h in HORIZONS:
        a = trades[f"move_{h}m"]
        b = fwd.loc[a.index, f"move_{h}m"]
        both = a.notna() & b.notna()
        gap = (a[both] - b[both]).abs().max()
        agree = (a.isna() == b.isna()).mean()
        print(f"  {h:2}m  n={both.sum():4}  max|diff|={gap:.6f}  nan-agreement={agree:.3f}")
        if gap > 1e-9 or agree < 1.0:
            print("  ^ vectorised path disagrees with backtest.evaluate; trust the harness")


def random_walk_table(bars: pd.DataFrame, fwd: pd.DataFrame, bar_minutes: int) -> pd.DataFrame:
    """horizon.py's diagnostic: does dispersion grow as sqrt(h), and does the
    overlap correlation between adjacent bars' legs land on a random walk's (h-b)/h?"""
    base = HORIZONS[0]
    sigma_base = fwd[f"move_{base}m"].std()
    rows = []
    for h in HORIZONS:
        col = fwd[f"move_{h}m"].dropna()
        expected_rho = max(h - bar_minutes, 0) / h
        rows.append({
            "sigma_ticks": col.std(),
            "sigma_over_sqrt_h": col.std() / (sigma_base * np.sqrt(h / base)),
            "median_abs_move": col.abs().median(),
            "overlap_rho": fwd[f"move_{h}m"].autocorr(lag=1),
            "rw_predicted_rho": expected_rho,
            "n": len(col),
        })
    return pd.DataFrame(rows, index=[f"{h}m" for h in HORIZONS])


def features(bars: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """OHLCV only. Nothing here can see an aggressor, a book, or a real volume."""
    c, o, h, low = (bars[k] for k in ("close", "open", "high", "low"))
    tr = pd.concat([h - low, (h - c.shift()).abs(), (low - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window).mean()
    ema = c.ewm(span=window, adjust=False).mean()
    vol = bars["volume"]
    return pd.DataFrame({
        "mom": (c - c.shift(window // 4)) / atr,
        "ema_dist": (c - ema) / atr,
        "break_hi": (c - h.rolling(window).max().shift()) / atr,
        "break_lo": (c - low.rolling(window).min().shift()) / atr,
        "vol_z": (vol - vol.rolling(window).mean()) / vol.rolling(window).std(),
        "body": (c - o) / tr.replace(0, np.nan),
    }, index=bars.index)


GRID = np.arange(0.5, 3.01, 0.5)


def rules(f: pd.DataFrame) -> dict[str, pd.Series]:
    """Each rule -> a side series per threshold. Entry-only, both directions."""
    out = {}
    for k in GRID:
        out[f"momentum k={k}"] = np.sign(f["mom"]).where(f["mom"].abs() > k, 0)
        out[f"reversion k={k}"] = -np.sign(f["ema_dist"]).where(f["ema_dist"].abs() > k, 0)
        out[f"breakout k={k}"] = pd.Series(
            np.where(f["break_hi"] > k, 1, np.where(f["break_lo"] < -k, -1, 0)), index=f.index)
        out[f"vol_thrust k={k}"] = np.sign(f["body"]).where(
            (f["vol_z"] > k) & f["body"].notna(), 0)
    return {name: s.fillna(0).astype("int64") for name, s in out.items()}


def sweep(sides: dict[str, pd.Series], moves: np.ndarray) -> pd.DataFrame:
    """Expectancy in ticks per rule. moves is one horizon's forward move array."""
    rows = []
    for name, s in sides.items():
        m = s.to_numpy()
        live = (m != 0) & ~np.isnan(moves)
        n = int(live.sum())
        rows.append({"rule": name, "n": n,
                     "expectancy_ticks": float((m[live] * moves[live]).mean()) if n else np.nan,
                     "hit_rate": float((m[live] * moves[live] > 0).mean()) if n else np.nan})
    return pd.DataFrame(rows).set_index("rule")


def permutation_null(sides: dict[str, pd.Series], moves: np.ndarray, sessions: np.ndarray,
                     seeds: int, min_n: int) -> np.ndarray:
    """Best-of-grid expectancy achievable when outcomes carry no information.

    Moves are shuffled WITHIN session, so the session's own volatility regime and
    every rule's trade count survive the shuffle; only the link between a feature
    and what followed it is destroyed.
    """
    rng = np.random.default_rng(20260905)
    order = np.argsort(sessions, kind="stable")
    bounds = np.flatnonzero(np.diff(sessions[order])) + 1
    groups = np.split(order, bounds)
    masks = [(s.to_numpy() != 0) for s in sides.values()]
    signs = [s.to_numpy() for s in sides.values()]
    best = np.empty(seeds)
    for i in range(seeds):
        shuffled = moves.copy()
        for g in groups:
            shuffled[g] = rng.permutation(moves[g])
        scores = []
        for mask, sign in zip(masks, signs, strict=True):
            live = mask & ~np.isnan(shuffled)
            if live.sum() >= min_n:
                scores.append((sign[live] * shuffled[live]).mean())
        best[i] = max(scores) if scores else np.nan
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", type=Path, default=Path("data/klines/GOLD_5m.jsonl"))
    ap.add_argument("--interval-minutes", type=int, default=5)
    ap.add_argument("--horizon", type=int, default=HORIZONS[0])
    ap.add_argument("--seeds", type=int, default=200)
    args = ap.parse_args()

    bars = load_bars(args.bars)
    fwd = forward_moves(bars)
    span = f"{bars.index[0]:%Y-%m-%d} -> {bars.index[-1]:%Y-%m-%d}"
    print(f"\n{len(bars):,} bars  {span}  {bars['session'].nunique()} sessions"
          f"  ({args.interval_minutes}-minute)\n")

    print("VECTORISED PATH vs backtest.evaluate")
    check_against_backtest(bars, fwd)

    print("\nPART 1 -- IS IT A RANDOM WALK AT THESE HORIZONS?")
    print(random_walk_table(bars, fwd, args.interval_minutes).to_string(
        float_format=lambda v: f"{v:8.3f}"))
    print("\n  sigma_over_sqrt_h at 1.000 and overlap_rho on rw_predicted_rho both mean"
          "\n  no unconditional structure -- the same result horizon.py measured on GC.")

    sides = rules(features(bars))
    moves = fwd[f"move_{args.horizon}m"].to_numpy()
    table = sweep(sides, moves).sort_values("expectancy_ticks", ascending=False)
    usable = table[table["n"] >= backtest.MIN_SAMPLES]

    print(f"\nPART 2 -- {len(sides)} OHLCV CONFIGS AT {args.horizon}m, best and worst by expectancy")
    print(pd.concat([usable.head(5), usable.tail(3)]).to_string(
        float_format=lambda v: f"{v:8.4f}"))
    if usable.empty:
        print(f"\nno config reached n >= {backtest.MIN_SAMPLES}; nothing to test")
        return

    null = permutation_null(sides, moves, bars["session"].to_numpy(), args.seeds,
                            backtest.MIN_SAMPLES)
    null = null[~np.isnan(null)]
    best = usable["expectancy_ticks"].iloc[0]
    p = float((null >= best).mean())
    print(f"\nPERMUTATION NULL -- best-of-grid on {len(null)} within-session shuffles")
    print(f"  best real config     {best:8.4f} ticks   ({usable.index[0]}, n={usable['n'].iloc[0]})")
    print(f"  null median / p95    {np.median(null):8.4f} / {np.quantile(null, 0.95):.4f} ticks")
    print(f"  shuffles beating it  {p:.3f}")
    print("\n  A best-of-grid that sits inside its own null is a grid search finding the"
          "\n  grid, not the market. Where the line falls is thresholds_selector.md's"
          "\n  call, not this file's.")


if __name__ == "__main__":
    main()
