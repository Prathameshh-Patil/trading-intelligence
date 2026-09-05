"""The S1 tick contract, read once so nothing downstream re-derives it.

Contract: plans/team/contracts.md S1. Traps it carries, all three inherited by
every consumer:

  * `aggressor_side` has a third value `'N'` (2.34% of the fixture) where no
    aggressor was disseminated. It contributes 0 to delta. `map({"B": 1,
    "A": -1})` yields silent NaN, so SIDES is exhaustive and an unknown code
    raises rather than defaulting.
  * `size` is uint32 upstream, where `-size` wraps to ~4.29e9. Cast before
    negating.
  * The fixture holds 421 duplicate rows that are real multi-fills. Nothing
    here deduplicates; `drop_duplicates()` moves session delta by 8%.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from instruments import GC

# Both encodings map here. The exchange codes are what the S1 parquet carries;
# the long names are what pull_futures_trades.py writes. Keeping one table means
# a frame from either producer reads the same way, and an unrecognised code is
# an error rather than a zero.
SIDES = {"B": 1, "A": -1, "N": 0, "buy_initiated": 1, "sell_initiated": -1, "unknown": 0}

DTYPES = {
    "timestamp": "datetime64[ns, UTC]",
    "price": "float64",
    "size": "int64",
    "aggressor_side": "category",
}

# This is the S1 GC loader, so the instrument is pinned rather than injected:
# a Databento `trades` parquet for GC is not a frame any other instrument
# produces. What used to live here as TICK now lives in instruments.py, and
# nothing imports it -- see that module's docstring for why. The session shift
# stays reachable under its old name because regimes.py reads it, but it is
# GC's, defined once, in the seam.
SESSION_SHIFT = GC.session_shift


def load_ticks(path: Path) -> pd.DataFrame:
    """Read an S1 parquet, verify the contract, and add `delta` and `session`."""
    df = pd.read_parquet(path)
    missing = sorted(set(DTYPES) - set(df.columns))
    if missing:
        raise ValueError(f"{path}: not an S1 frame, missing {missing}")
    return add_delta(df.sort_values("timestamp").reset_index(drop=True))


def add_delta(df: pd.DataFrame) -> pd.DataFrame:
    """Signed volume per trade, plus the session each trade belongs to.

    Unattributed trades contribute 0. Folding them into either side is how a
    footprint acquires a directional bias that is not in the market.
    """
    codes = set(df["aggressor_side"].unique())
    unknown = sorted(str(c) for c in codes - set(SIDES))
    if unknown:
        raise ValueError(f"unknown aggressor_side values: {unknown}")

    sign = df["aggressor_side"].astype("object").map(SIDES).astype("int64")
    df["delta"] = sign * df["size"].astype("int64")
    df["session"] = (df["timestamp"] + SESSION_SHIFT).dt.date
    return df


def minute_bars(df: pd.DataFrame) -> pd.DataFrame:
    """1-minute OHLC with delta and session-reset CVD, indexed by bar open.

    Minutes with no trades are dropped, so bar N+5 is NOT five minutes after
    bar N. Anything measuring a horizon must slice on the index, never on row
    offsets -- see backtest.py.
    """
    bars = (
        df.set_index("timestamp")
        .resample("1min")
        .agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("size", "sum"),
            delta=("delta", "sum"),
            trades=("price", "size"),
        )
    )
    bars = bars[bars["trades"] > 0].copy()
    bars["session"] = pd.DatetimeIndex(bars.index + SESSION_SHIFT).date
    # CVD is only meaningful against a starting point; carrying it across the
    # overnight break makes the level rather than the shape do the talking.
    bars["cvd"] = bars.groupby("session", sort=False)["delta"].cumsum()
    return bars


def session_cvd(df: pd.DataFrame) -> pd.Series:
    """Trade-by-trade CVD, reset each session. See minute_bars on why it resets."""
    return df.groupby("session", sort=False)["delta"].cumsum()
