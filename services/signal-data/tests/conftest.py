"""Frames built by hand, where the answer is known by construction.

Three test files wanted the same builder, which is where a copy stops being
duplication worth tolerating. Nothing here reads a real file -- the fixture
tests do that themselves, and deliberately, since asserting the S1 contract's
own numbers is the point of those.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

SESSION = pd.Timestamp("2026-07-16").date()
NEXT = pd.Timestamp("2026-07-17").date()
OPEN = pd.Timestamp("2026-07-15T22:00:00Z")

type Session = date | str


def bars_at(
    minutes: list[int],
    closes: list[float],
    deltas: list[int] | None = None,
    ranges: list[float] | None = None,
    session: Session | Sequence[Session] = SESSION,
) -> pd.DataFrame:
    """Bars at the given minute offsets, shaped like s1.minute_bars output.

    Gaps in `minutes` are the point -- a real frame drops minutes that had no
    trades. `ranges` is the high-low spread in PRICE, centred on the close.
    """
    idx = pd.DatetimeIndex([OPEN + pd.Timedelta(minutes=m) for m in minutes])
    c = pd.Series(closes, index=idx, dtype="float64")
    half = pd.Series(ranges if ranges is not None else [0.0] * len(idx), index=idx) / 2
    # date and str ARE the scalar cases; anything else is a per-bar sequence.
    sess: list[Session] = [session] * len(idx) if isinstance(session, date | str) else list(session)
    bars = pd.DataFrame(
        {
            "open": c,
            "high": c + half,
            "low": c - half,
            "close": c,
            "volume": 100,
            "delta": deltas if deltas is not None else [0] * len(idx),
            "trades": 10,
            "session": sess,
        },
        index=idx,
    )
    bars["cvd"] = bars.groupby("session", sort=False)["delta"].cumsum()
    return bars


def ticks_at(rows: list[tuple[int, float, int, str]], session: Session = SESSION) -> pd.DataFrame:
    """Tick frame shaped like s1.load_ticks output: (minute, price, size, side)."""
    df = pd.DataFrame(rows, columns=["minute", "price", "size", "aggressor_side"])
    df["timestamp"] = [OPEN + pd.Timedelta(minutes=int(m)) for m in df["minute"]]
    df["delta"] = df["size"] * df["aggressor_side"].map({"B": 1, "A": -1, "N": 0})
    df["session"] = session
    return df.drop(columns="minute")


def entries_at(bars: pd.DataFrame, positions: dict[int, int]) -> pd.Series:
    """Sides by row offset: +1 long, -1 short, everything else flat."""
    s = pd.Series(0, index=bars.index)
    for i, side in positions.items():
        s.iloc[i] = side
    return s


def noise(n: int) -> list[int]:
    """Small deltas with real spread -- a constant series has zero standard
    deviation and every z-score off it is infinite."""
    return [8, 10, 12, 9, 11][: n % 5] + [8, 10, 12, 9, 11] * (n // 5)
