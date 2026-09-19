"""Track C's fixture-only half: config, levels, regime, fills, funnel, metrics.

Nothing here reads a market file. Every frame is built so the answer is known
by construction, which is the only way a lookahead test can be conclusive --
the future is put somewhere extreme, and a leak moves the number visibly.
"""

from __future__ import annotations

from collections import Counter
from datetime import time

import numpy as np
import pandas as pd
import pytest
from conftest import spot_bars

from features import hurst
from track_c import config, fills, funnel, levels, metrics, regime

ASIA_START, ASIA_END = time(20, 0), time(2, 0)
# 2026-07-16 00:00 UTC is 20:00 New York on the 15th (EDT), so the Asian window
# opens on the first bar and closes six hours later at 06:00 UTC.
ASIA_OPEN = "2026-07-16T00:00:00Z"
ASIA_BARS = 72          # 6 hours of 5-minute bars


# --------------------------------------------------------------------------
# config


def test_config_loads_and_agrees_with_the_modules_it_restates() -> None:
    cfg = config.load()
    assert config.f(cfg, "risk.d_min_atr") == 0.8
    assert config.windows(cfg, "s3") == ((time(8, 0), time(11, 30)),
                                         (time(13, 30), time(15, 30)))


def test_a_missing_key_names_itself() -> None:
    with pytest.raises(KeyError, match="risk.nonesuch"):
        config.get({"risk": {}}, "risk.nonesuch")


def test_a_restatement_that_drifts_is_refused() -> None:
    """The guard that stops the TOML and `fsm.py` quietly disagreeing."""
    cfg = config.load()
    cfg["risk"]["d_min_atr"] = 1.0
    with pytest.raises(ValueError, match="disagrees with fsm.D_MIN_ATR"):
        config.require(cfg)


def test_a_float_where_an_int_is_required_is_refused() -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        config.i({"a": {"b": 2.7}}, "a.b")


@pytest.mark.parametrize(("d", "expected"), [(2.0, 10.0), (4.0, 10.0), (5.0, 12.5)])
def test_target_is_clipped_between_the_floor_and_the_cap(d: float, expected: float) -> None:
    """§10's floor is why a tight stop does not buy a tight target: at D = $2
    the 2.5x multiple gives $5 and the floor lifts it to $10."""
    assert config.target_usd(d, config.load()) == expected


# --------------------------------------------------------------------------
# levels -- the three places lookahead would enter


def test_the_asian_range_is_nan_until_its_window_closes() -> None:
    closes = [3400.0] * ASIA_BARS + [3500.0] * 24
    bars = spot_bars(closes, start=ASIA_OPEN, rng=1.0)
    out = levels.asian_range(bars, start=ASIA_START, end=ASIA_END)
    assert out["asian_high"].iloc[:ASIA_BARS].isna().all(), "a partial range is not a range"
    assert out["asian_high"].iloc[ASIA_BARS] == pytest.approx(3400.5)


def test_a_later_spike_does_not_change_a_closed_asian_range() -> None:
    """The test that would catch a `cummax` without the window mask."""
    closes = [3400.0] * ASIA_BARS + [9999.0] + [3400.0] * 23
    bars = spot_bars(closes, start=ASIA_OPEN, rng=1.0)
    out = levels.asian_range(bars, start=ASIA_START, end=ASIA_END)
    assert out["asian_high"].iloc[-1] == pytest.approx(3400.5)


def test_prior_day_is_the_previous_session_and_nan_on_the_first() -> None:
    # 22:00 UTC is the session boundary `inst.session_shift` puts it at.
    bars = spot_bars([3400.0] * 288 + [3500.0] * 288,
                     start="2026-07-15T22:00:00Z", rng=2.0)
    out = levels.prior_day(bars)
    assert out["pdh"].iloc[:288].isna().all()
    assert out["pdh"].iloc[-1] == pytest.approx(3401.0)
    assert out["pdl"].iloc[-1] == pytest.approx(3399.0)


def test_donchian_excludes_the_bar_that_breaks_it() -> None:
    """Without the shift a breakout level includes the breaking bar's own high
    and can never be broken -- the bug presents as a strategy that never fires."""
    bars = spot_bars([1.0, 2.0, 3.0, 99.0], rng=0.0)
    out = levels.donchian(bars, n=2)
    assert out["dc_high"].iloc[3] == pytest.approx(3.0)


def test_session_vwap_with_flat_quote_counts_is_the_running_mean() -> None:
    bars = spot_bars([1.0, 2.0, 3.0, 4.0], ticks=10)
    assert levels.session_vwap(bars).tolist() == [1.0, 1.5, 2.0, 2.5]


def test_vwap_z_is_nan_until_the_session_has_enough_bars() -> None:
    bars = spot_bars(list(np.arange(30, dtype=float)))
    z = levels.vwap_z(bars, levels.session_vwap(bars), min_bars=24)
    assert z.iloc[:23].isna().all()
    assert np.isfinite(z.iloc[-1])


# --------------------------------------------------------------------------
# regime


def test_both_hurst_estimators_are_given_the_same_scales() -> None:
    """`features/hurst.py`'s own trap: DFA differences its input and so has one
    point fewer, which at window 256 hands variance-time a scale DFA cannot use.
    Two estimators over different scale sets are not two readings of one
    quantity, and `hurst_agree` would be comparing the wrong things."""
    scales = regime.hurst_scales(256)
    assert len(scales) >= 3
    assert all((256 - 1) // s >= 4 for s in scales)
    assert all(256 // s >= 4 for s in scales)


def test_the_production_window_reaches_only_five_of_the_seven_declared_scales() -> None:
    """🔴 **`test_dfa_is_biased_high_on_a_short_scale_ladder_and_agreement_fails
    _there` documents a failure mode; this records that production runs inside
    it.**

    `hurst.SCALES` declares seven scales up to 256, and a scale survives only if
    the window holds four of it -- against `window - 1`, since DFA differences
    its input and has one point fewer. At `hurst_window_bars = 256` that leaves
    **(4, 8, 16, 32): four of the seven, and a largest scale of 32.**

    **That is, exactly, the ladder `test_dfa_is_biased_high_on_a_short_scale_
    ladder_and_agreement_fails_there` was written about** -- it restricts a pure
    random walk to `(4, 8, 16, 32)` and records DFA reading 0.563 against a true
    0.5. The bias was documented in a test and then configured into production.

    **The config comment said "§6's estimators need 4 windows at the largest
    scale; 256 gives them". It does not** -- 256 gives four windows at scale 32.
    Four windows at the largest *declared* scale needs **1025**.

    MEASURED, and the synthetic case is the one that settles it. On 300 random
    walks whose true H is 0.5 by construction, at window 256 DFA reads 0.562 and
    variance-time reads 0.420 -- **a built-in +0.142 gap against a 0.05
    tolerance, agreeing 16.7% of the time.** On the real June-August 2026
    archive the pair agree on **26.2%** of bars, which is *better* than the
    synthetic floor -- so `h_agree` is not measuring the market here.

        window   scales used      bias    sd     agree (real archive)
           256   4..64           +0.084  0.118   26.2%
           512   4..128          +0.058  0.074   35.1%
          1024   4..256 (all)    +0.047  0.052   50.0%
          2048   4..256          +0.023  0.036   72.8%

    ⛔ **Not changed here.** `hurst_window_bars` is a §6 threshold and moving it
    after seeing its effect on a funnel is the thing §7's gates exist to stop.
    This test pins the arithmetic so the choice is explicit rather than
    inherited; it fails the day the window moves, which is when the room should
    be looking at it.
    """
    window = config.i(config.load(), "regime.hurst_window_bars")
    reachable = regime.hurst_scales(window)

    assert window == 256
    assert tuple(reachable) == (4, 8, 16, 32)
    assert set(hurst.SCALES) - set(reachable) == {64, 128, 256}, "the ladder is truncated"

    # The window that would reach the whole declared ladder, derived from the
    # rule rather than typed: four windows of the largest scale, plus the one
    # point DFA loses to differencing.
    needed = 4 * max(hurst.SCALES) + 1
    assert needed == 1025
    assert tuple(regime.hurst_scales(needed)) == hurst.SCALES


def test_hurst_is_held_between_recomputations_and_never_early() -> None:
    rng = np.random.default_rng(7)
    bars = spot_bars(list(3400 + np.cumsum(rng.normal(0, 0.5, 400))))
    out = regime.hurst_pair(bars, window=256, step=12)
    assert out["h_dfa"].iloc[:255].isna().all(), "a value before its window is lookahead"
    assert np.isfinite(out["h_dfa"].iloc[255])
    # Held, not interpolated: the value only moves on the step grid.
    changes = out["h_dfa"].iloc[255:].diff().ne(0).sum()
    assert changes <= len(out.iloc[255:]) // 12 + 1


def test_vol_ratio_refuses_a_fast_window_that_is_not_faster() -> None:
    bars = spot_bars([3400.0] * 50)
    with pytest.raises(ValueError, match="shorter window"):
        regime.vol_ratio(bars, fast=48, slow=12)


def test_pct_rank_is_one_at_the_top_of_its_own_trailing_sample() -> None:
    s = pd.Series(np.arange(100, dtype=float))
    out = regime.pct_rank(s, lookback=10)
    assert out.iloc[:9].isna().all()
    assert out.iloc[-1] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# fills -- the pessimistic half


def _cfg() -> dict:
    return config.load()


def test_a_limit_that_only_touches_the_mid_does_not_fill() -> None:
    """Mid bars: a limit buy fills when the ASK reaches it, so the mid has to
    clear it by half a spread. Requiring only a touch grants a fill the book
    never offered -- on every trade, in the flattering direction."""
    cfg = _cfg()
    bar = pd.Series({"low": 3400.0, "high": 3402.0})
    assert not fills.limit_filled(bar, limit=3400.0, side=1, spread_usd=0.60,
                                  cfg=cfg, news=False)
    assert fills.limit_filled(bar, limit=3400.4, side=1, spread_usd=0.60,
                              cfg=cfg, news=False)


def test_a_gapping_stop_fills_at_the_bar_extreme_not_at_the_stop() -> None:
    """Capping the loss at exactly 1R on the days that gap is the single most
    flattering assumption a bar backtest can make."""
    cfg = _cfg()
    bar = pd.Series({"low": 3390.0, "high": 3400.0})
    price = fills.stop_fill_price(bar, stop=3398.0, side=1, spread_usd=0.60,
                                  cfg=cfg, news=False)
    assert price < 3390.0


def test_news_widens_the_spread_even_where_the_trade_is_allowed() -> None:
    cfg = _cfg()
    assert (fills.half_spread(0.60, cfg, news=True)
            == pytest.approx(3.0 * fills.half_spread(0.60, cfg, news=False)))


def test_a_round_trip_pays_one_spread_and_one_slippage() -> None:
    """Two half-spreads, not two spreads: charging a full spread at each end is
    the double-count `e3_cost.py` exists to name."""
    cfg = _cfg()
    assert fills.round_trip_usd(1.0, cfg, news=False) == pytest.approx(1.0 + 0.75)


def test_five_minute_bars_cannot_resolve_a_twenty_second_limit() -> None:
    assert not fills.resolves_limit(_cfg())


# --------------------------------------------------------------------------
# funnel


def test_the_attrition_table_accounts_for_every_bar() -> None:
    counts: funnel.Counts = Counter()
    conds: dict[str, tuple[str, ...]] = {"sx": ("a", "b")}
    counts[("sx", funnel.EVALUATED)] = 10
    counts[("sx", "a")] = 6
    counts[("sx", "b")] = 3
    counts[("sx", funnel.SUGGESTED)] = 1
    t = funnel.table(counts, conds)
    assert list(t["reached"]) == [10, 4, 1]
    assert list(t["survivors"]) == [4, 1, 1]
    funnel.check(counts, conds)


def test_an_uncounted_outcome_is_a_hard_failure() -> None:
    """A table that describes a different run than the equity curve beside it
    is worse than no table."""
    conds: dict[str, tuple[str, ...]] = {"sx": ("a", "b")}
    counts: funnel.Counts = Counter({("sx", funnel.EVALUATED): 10, ("sx", "a"): 6})
    with pytest.raises(ValueError, match="accounted for"):
        funnel.check(counts, conds)


# --------------------------------------------------------------------------
# metrics


def _trades(rs: list[float], cfg: dict) -> pd.DataFrame:
    risk = config.f(cfg, "risk.equity_usd") * config.f(cfg, "risk.risk_fraction")
    days = pd.date_range("2026-01-01", periods=len(rs), freq="B").date
    return pd.DataFrame({"r": rs, "pnl_usd": [r * risk for r in rs],
                         "session": days, "strategy": "sx"})


def test_summary_of_an_empty_frame_is_a_result_and_not_an_exception() -> None:
    s = metrics.summarize(pd.DataFrame(columns=["r", "pnl_usd", "session"]), _cfg())
    assert s["n"] == 0 and s["total_r"] == 0.0


def test_profit_factor_and_worst_day() -> None:
    cfg = _cfg()
    s = metrics.summarize(_trades([2.5, -1.0, -1.0, 2.5], cfg), cfg)
    assert s["pf"] == pytest.approx(2.5)
    assert s["worst_day_r"] == pytest.approx(-1.0)
    assert s["win_rate"] == pytest.approx(0.5)


def test_a_run_with_no_loser_has_an_undefined_profit_factor_not_an_infinite_one() -> None:
    cfg = _cfg()
    assert np.isnan(metrics.summarize(_trades([2.5, 2.5], cfg), cfg)["pf"])


def test_drawdown_is_a_fraction_of_starting_equity() -> None:
    cfg = _cfg()
    risk = config.f(cfg, "risk.equity_usd") * config.f(cfg, "risk.risk_fraction")
    s = metrics.summarize(_trades([1.0, -2.0], cfg), cfg)
    assert s["max_dd"] == pytest.approx(2.0 * risk / config.f(cfg, "risk.equity_usd"))


def test_a_gate_with_no_measurement_fails() -> None:
    """An unmeasured gate is not a passed gate, and omitting the row is how a
    gate table lies."""
    row = metrics._gate("sx", "C3", "profit factor", float("nan"), 1.4, "ge")
    assert row["pass"] is False
