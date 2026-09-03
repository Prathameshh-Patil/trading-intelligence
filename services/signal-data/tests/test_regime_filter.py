"""The four D1 gates, on bars built by hand so the answer is known.

One test per gate, plus the two failure modes a filter has that a signal does
not: passing a bar on a MISSING value, and letting a window or an EMA reach
across the overnight break. The ATR gate's own tests live in
`test_features.py`, with the function, which moved to `features/expansion.py`
on D2. A filter that fails open is worse than no filter,
because everything downstream is then measured on a sample nobody chose.

What this file does NOT test is whether the filter's pass rate is any good.
That is a number to be measured on the month, not asserted here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from conftest import NEXT, SESSION, bars_at

from features import regime_filter as rf


def with_regime(bars: pd.DataFrame, labels: list[float]) -> pd.DataFrame:
    return bars.assign(regime=pd.Series(labels, index=bars.index, dtype="float64"))


# --------------------------------------------------------------------------
# Gate 1 -- regime survival
# --------------------------------------------------------------------------
def test_survival_counts_only_bars_with_a_forward_bar_in_the_same_session() -> None:
    # Regime 0 holds for all four bars of session one. Measured one bar ahead
    # there are three comparisons, all of them holds -- not four with the last
    # scored against a session that had not started.
    bars = with_regime(
        bars_at(list(range(8)), [100.0] * 8, session=[SESSION] * 4 + [NEXT] * 4),
        [0, 0, 0, 0, 1, 1, 1, 1],
    )
    surv = rf.regime_survival(bars, horizon_bars=1)
    assert surv.loc[0] == 1.0, "the session boundary is not a regime change"
    assert surv.loc[1] == 1.0


def test_survival_falls_when_a_regime_actually_changes() -> None:
    # Regime 0 occupies bars 0-3; bar 3 flips to 1. One of the four 0-bars has
    # no forward bar, so it is 2 holds out of 3 comparisons.
    bars = with_regime(bars_at(list(range(5)), [100.0] * 5), [0, 0, 0, 1, 1])
    surv = rf.regime_survival(bars, horizon_bars=1)
    assert surv.loc[0] == 2 / 3


def test_an_unlabelled_bar_never_passes() -> None:
    # regimes_2026-09-02 leaves 253 of 6,276 bars unlabelled -- the opening
    # bars with no trailing window yet. NaN must fail, not slip through.
    bars = with_regime(bars_at(list(range(6)), [100.0] * 6), [np.nan] * 6)
    gate = bars["regime"].map(pd.Series({0.0: 1.0})) >= 0.9
    assert not gate.any()


def test_kappa_does_not_reward_a_regime_for_being_common() -> None:
    # The correction of 2026-09-04, in miniature: a common regime interleaved
    # with two rare ones that never transition into each other -- the real
    # structure of regimes_2026-09-02. Raw survival ranks the common regime
    # above rare regime 0 purely on prevalence. Kappa reverses that.
    #
    # A two-regime example cannot show this: for a two-state chain kappa is
    # symmetric by identity, so it takes three.
    labels = ([2.0] * 8 + [0.0] * 6 + [2.0] * 8 + [1.0] * 6) * 2
    bars = with_regime(bars_at(list(range(len(labels))), [100.0] * len(labels)), labels)
    surv = rf.regime_survival(bars, horizon_bars=1)
    kap = rf.regime_kappa(bars, horizon_bars=1)
    assert surv.loc[2.0] > surv.loc[0.0], "raw survival favours the common regime"
    assert kap.loc[0.0] > kap.loc[2.0], "kappa reverses it once base rate is removed"


def test_kappa_is_nan_when_there_is_no_base_rate_to_beat() -> None:
    # One regime over the whole frame: share is 1.0, there is nothing to beat,
    # and 1 - share is zero. NaN, not inf -- and NaN fails closed at the gate.
    bars = with_regime(bars_at(list(range(6)), [100.0] * 6), [0.0] * 6)
    assert rf.regime_kappa(bars, horizon_bars=1).isna().all()


# --------------------------------------------------------------------------
# Gate 3 -- EMA trend alignment
# --------------------------------------------------------------------------
def test_a_bounce_above_a_still_falling_ema_is_not_alignment() -> None:
    # Twelve bars down, then a sharp rally that lifts price back over the EMA
    # while the EMA is still below where it was `span` bars ago. That is a
    # bounce inside a downtrend, and it is the case the gate exists to reject.
    # It is also the case a one-bar slope CANNOT reject -- see the docstring.
    closes = [130.0 - 2 * i for i in range(12)] + [108.0, 112.0, 116.0, 120.0]
    aligned = rf.trend_aligned(bars_at(list(range(len(closes))), closes), span=5)
    assert aligned.iloc[5:13].all(), "a clean downtrend aligns short"
    assert not aligned.iloc[13], "price back above a still-lower average is not a trend"
    assert not aligned.iloc[14]
    assert aligned.iloc[15], "once the average turns up, it aligns again"


def test_a_rising_market_is_aligned() -> None:
    bars = bars_at(list(range(8)), [100.0 + 2 * i for i in range(8)])
    assert rf.trend_aligned(bars, span=3).iloc[3:].all()


def test_a_flat_ema_is_not_a_trend() -> None:
    bars = bars_at(list(range(6)), [100.0] * 6)
    assert not rf.trend_aligned(bars, span=3).any()


def test_the_ema_restarts_at_the_session_boundary() -> None:
    # Session one falls hard; session two opens and rises. If the EMA carried
    # across, session two's first bars sit far under a stale average and read
    # as aligned SHORT while price is climbing.
    bars = bars_at(
        list(range(8)),
        [130.0, 125.0, 120.0, 115.0, 100.0, 102.0, 104.0, 106.0],
        session=[SESSION] * 4 + [NEXT] * 4,
    )
    aligned = rf.trend_aligned(bars, span=3)
    msg = "a new session cannot align until it has span bars of its own"
    assert not aligned.iloc[4:7].any(), msg
    assert aligned.iloc[7], (
        "session two is rising and aligns once it has its own history"
    )


# --------------------------------------------------------------------------
# Gate 4 -- session edges
# --------------------------------------------------------------------------
def test_the_first_and_last_minutes_of_each_session_are_dropped() -> None:
    bars = bars_at(list(range(20)), [100.0] * 20, session=[SESSION] * 10 + [NEXT] * 10)
    keep = rf.session_interior(bars, edge_minutes=5)
    assert not keep.iloc[:5].any(), "session one's open is dropped"
    assert not keep.iloc[5:10].any(), "session one's close is dropped"
    assert not keep.iloc[10:15].any(), "session two's open is dropped"


def test_the_interior_of_a_long_session_survives() -> None:
    bars = bars_at(list(range(30)), [100.0] * 30)
    keep = rf.session_interior(bars, edge_minutes=5)
    assert keep.iloc[5:25].all()
    assert not keep.iloc[:5].any()
    assert not keep.iloc[25:].any()


# --------------------------------------------------------------------------
# The combiner
# --------------------------------------------------------------------------
def test_every_gate_can_veto_alone() -> None:
    n = 30
    bars = with_regime(
        bars_at(
            list(range(n)),
            [100.0 + i for i in range(n)],
            ranges=[2.0] * n,
            deltas=[50] * n,
        ),
        [0.0] * n,
    )
    kw = {
        "kappa": pd.Series({0.0: 0.85}),
        "kappa_min": 0.75,
        "persistence_window": "10min",
        "persistence_min_bars": 3,
        "persistence_min": 0.4,
        "atr_window": "10min",
        "atr_min_bars": 5,
        "atr_min": 10.0,
        "ema_span": 3,
        "edge_minutes": 5,
    }
    base = rf.passes(bars, **kw)  # type: ignore[arg-type]
    assert base.iloc[10:25].all(), "a rising, wide, mid-session, surviving bar passes"

    assert not rf.passes(bars, **{**kw, "kappa_min": 0.99}).any()  # type: ignore[arg-type]
    assert not rf.passes(bars, **{**kw, "atr_min": 999.0}).any()  # type: ignore[arg-type]
    assert not rf.passes(bars, **{**kw, "edge_minutes": 60}).any()  # type: ignore[arg-type]
    assert not rf.passes(bars, **{**kw, "persistence_min": 1.01}).any()  # type: ignore[arg-type]

    # Flow that cancels bar for bar is vetoed by the persistence gate alone:
    # the price trend, the range and the regime are all still fine.
    churn = with_regime(
        bars_at(
            list(range(n)),
            [100.0 + i for i in range(n)],
            ranges=[2.0] * n,
            deltas=[50, -50] * (n // 2),
        ),
        [0.0] * n,
    )
    assert not rf.passes(churn, **kw).any()  # type: ignore[arg-type]

    # A dead flat market has range to trade and a surviving regime, and is
    # vetoed by the trend gate alone -- a zero slope is not a direction.
    flat = with_regime(
        bars_at(list(range(n)), [100.0] * n, ranges=[2.0] * n, deltas=[50] * n),
        [0.0] * n,
    )
    assert not rf.passes(flat, **kw).any()  # type: ignore[arg-type]

    # A clean downtrend is NOT vetoed: the gate aligns short and passes it.
    falling = with_regime(
        bars_at(
            list(range(n)),
            [100.0 - i for i in range(n)],
            ranges=[2.0] * n,
            deltas=[-50] * n,
        ),
        [0.0] * n,
    )
    assert rf.passes(falling, **kw).iloc[10:25].all()  # type: ignore[arg-type]


def test_a_regime_missing_from_the_kappa_table_fails_closed() -> None:
    n = 30
    bars = with_regime(
        bars_at(
            list(range(n)),
            [100.0 + i for i in range(n)],
            ranges=[2.0] * n,
            deltas=[50] * n,
        ),
        [7.0] * n,
    )
    keep = rf.passes(
        bars,
        kappa=pd.Series({0.0: 0.85}),
        kappa_min=0.75,
        persistence_window="10min",
        persistence_min_bars=3,
        persistence_min=0.4,
        atr_window="10min",
        atr_min_bars=5,
        atr_min=10.0,
        ema_span=3,
        edge_minutes=5,
    )
    assert not keep.any(), "an unknown regime is dropped, not passed on a missing value"
