"""D2's Layer 3 features, on bars where the answer is arithmetic.

The ATR tests moved here with the function, from `test_regime_filter.py`.

What gets tested hardest is VWAP, because it is the only genuinely new
quantity in D2 and it has the two failure modes a session-anchored cumulative
has: carrying across the overnight break, and weighting by nothing when
volume is uniform, which makes it silently equal to a plain mean and hides a
missing weight.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd
import pytest
from conftest import NEXT, SESSION, bars_at

from features import expansion as ex
from features import orderflow as of
from instruments import GC

TICK = GC.tick


# --------------------------------------------------------------------------
# ATR -- moved from regime_filter on D2, same behaviour
# --------------------------------------------------------------------------
def test_atr_is_in_ticks_not_price() -> None:
    bars = bars_at(list(range(10)), [100.0] * 10, ranges=[2.0] * 10)
    assert ex.atr(bars, GC, window="5min", min_bars=3).dropna().round(6).eq(20.0).all()


def test_atr_has_no_value_until_the_window_is_full() -> None:
    bars = bars_at(list(range(10)), [100.0] * 10, ranges=[2.0] * 10)
    a = ex.atr(bars, GC, window="5min", min_bars=5)
    assert a.iloc[:4].isna().all()
    assert a.iloc[4:].notna().all()


def test_atr_does_not_measure_the_gap_across_a_session_break() -> None:
    bars = bars_at(
        list(range(8)),
        [100.0] * 4 + [150.0] * 4,
        ranges=[2.0] * 8,
        session=[SESSION] * 4 + [NEXT] * 4,
    )
    assert ex.atr(bars, GC, window="5min", min_bars=1).iloc[4] == 20.0


def test_regime_filter_uses_the_same_atr() -> None:
    # The point of the move: one true-range calculation, not two that drift.
    from features import regime_filter as rf

    assert rf.atr is ex.atr


# --------------------------------------------------------------------------
# Bar range and body ratio
# --------------------------------------------------------------------------
def test_bar_range_is_ticks() -> None:
    bars = bars_at([0, 1, 2], [100.0] * 3, ranges=[0.5, 2.0, 6.0])
    assert list(ex.bar_range(bars, GC).round(6)) == [5.0, 20.0, 60.0]


def test_body_ratio_spans_zero_to_one() -> None:
    # A bar that opens at its low and closes at its high is a full body; one
    # that opens and closes at the same price is a doji whatever it ranged.
    bars = bars_at([0, 1], [100.0, 100.0], ranges=[2.0, 2.0])
    full = bars.copy()
    full.loc[full.index[0], "open"] = 99.0
    full.loc[full.index[0], "close"] = 101.0
    r = ex.body_ratio(full, GC)
    assert r.iloc[0] == 1.0, "open at the low, close at the high"
    assert r.iloc[1] == 0.0, "open equals close is a doji"


def test_a_zero_range_bar_is_zero_not_infinite() -> None:
    # Gold prints these: one price, never traded away. 0/0 must not be inf.
    bars = bars_at([0], [100.0], ranges=[0.0])
    assert ex.body_ratio(bars, GC).iloc[0] == 0.0
    assert np.isfinite(ex.body_ratio(bars, GC)).all()


# --------------------------------------------------------------------------
# VWAP
# --------------------------------------------------------------------------
def test_vwap_is_volume_weighted_and_not_a_plain_mean() -> None:
    # Two bars: one lot at 100, ninety-nine at 200. The mean is 150; VWAP is
    # 199. Uniform volume would make these equal and hide a missing weight.
    bars = bars_at([0, 1], [100.0, 200.0])
    bars["volume"] = [1, 99]
    v = of.vwap(bars)
    assert v.iloc[0] == 100.0
    assert round(v.iloc[1], 6) == 199.0
    assert v.iloc[1] != bars["close"].mean()


def test_vwap_uses_typical_price_not_close() -> None:
    # One bar ranging 2.0 around a close of 100: typical is (101+99+100)/3.
    bars = bars_at([0], [100.0], ranges=[2.0])
    assert round(of.vwap(bars).iloc[0], 6) == round((101.0 + 99.0 + 100.0) / 3, 6)


def test_vwap_reanchors_at_the_session_boundary() -> None:
    # Session one trades at 100, session two at 200. Session two's first bar
    # must read 200, not a blend of the two sessions.
    bars = bars_at(
        list(range(6)), [100.0] * 3 + [200.0] * 3, session=[SESSION] * 3 + [NEXT] * 3
    )
    v = of.vwap(bars)
    assert v.iloc[2] == 100.0
    assert v.iloc[3] == 200.0, (
        "an overnight-anchored VWAP describes a session that has ended"
    )


def test_vwap_distance_is_signed_ticks() -> None:
    bars = bars_at([0, 1], [100.0, 100.5])
    d = of.vwap_distance(bars, GC)
    assert d.iloc[0] == 0.0, "the first bar of a session sits on its own VWAP"
    assert d.iloc[1] > 0, "a close above the session average is positive"
    assert round(d.iloc[1], 6) == round(
        (bars["close"].iloc[1] - of.vwap(bars).iloc[1]) / TICK, 6
    )


def test_a_zero_volume_bar_is_nan_not_a_division_by_zero() -> None:
    bars = bars_at([0, 1], [100.0, 100.0])
    bars["volume"] = [0, 0]
    assert of.vwap(bars).isna().all(), (
        "a bar with no trades is a data fault, reported not smoothed"
    )


# --------------------------------------------------------------------------
# CVD persistence -- the D1 fourth gate's feature, canonical here
# --------------------------------------------------------------------------
def test_persistence_is_one_when_all_flow_goes_one_way() -> None:
    bars = bars_at(list(range(6)), [100.0] * 6, deltas=[10, 20, 30, 40, 50, 60])
    assert of.cvd_persistence(bars, window="5min", min_bars=3).dropna().eq(1.0).all()


def test_persistence_is_zero_when_flow_cancels_exactly() -> None:
    bars = bars_at(list(range(4)), [100.0] * 4, deltas=[50, -50, 50, -50])
    p = of.cvd_persistence(bars, window="2min", min_bars=2)
    assert p.iloc[1] == 0.0, "one up and one down is perfectly balanced"


def test_no_flow_at_all_is_nan_not_zero() -> None:
    # Zero would read as "perfectly balanced", which is a different statement
    # from "nothing traded". The gate must fail closed on it, and NaN does.
    bars = bars_at(list(range(4)), [100.0] * 4, deltas=[0, 0, 0, 0])
    assert of.cvd_persistence(bars, window="2min", min_bars=2).isna().all()


def test_regimes_uses_this_exact_definition() -> None:
    # The clustering computed the labels with this function; the D1 gate now
    # filters on it. Two copies would let the labels and the gate drift.
    import regimes

    assert regimes._cvd_persistence is of._persistence


# --------------------------------------------------------------------------
# The re-exports D2 asks for -- imported, not re-derived
# --------------------------------------------------------------------------
def test_orderflow_reexports_the_tested_originals() -> None:
    import strategies as st

    assert of.delta_z is st.delta_z
    assert of.cvd_slope is st.cvd_slope
    assert of.absorption is st.absorption


def test_absorption_is_still_contracts_per_tick() -> None:
    # Guarding the re-export, not re-testing strategies.py: 400 contracts of
    # one-sided flow across a 20-tick bar is 20 contracts per tick.
    bars = bars_at([0], [100.0], deltas=[400], ranges=[2.0])
    assert of.absorption(bars, GC).iloc[0] == 20.0


# --------------------------------------------------------------------------
# Yang-Zhang -- mathematical.md §2. Task 6 of the 18-20 Sep block.
#
# What gets tested hardest is drift-independence, because it is the entire
# reason §2 specifies Yang-Zhang over close-to-close: gold rose 55.2% across
# the archive (M3B_DRIFT.md's correction), and an estimator that reads that
# trend as volatility would report the bull market as risk.


def ohlc(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """Bars from explicit (open, high, low, close). `bars_at` cannot serve
    here: it sets open == close, which zeroes Yang-Zhang's open-to-close leg
    and would let a missing `k` term pass every test."""
    idx = pd.date_range("2025-06-02T13:30:00Z", periods=len(rows), freq="5min")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def test_k_matches_the_published_constant() -> None:
    # k = 0.34 / (1.34 + (n+1)/(n-1)). Yang & Zhang (2000).
    assert ex._yz_k(12) == np.float64(0.34 / (1.34 + 13 / 11))
    assert abs(ex._yz_k(12) - 0.134823) < 1e-6


def test_k_approaches_the_large_n_limit() -> None:
    # (n+1)/(n-1) -> 1, so k -> 0.34/2.34. A k that drifts outside
    # [0.078, 0.146] for any n >= 2 means the formula was mistyped.
    assert abs(ex._yz_k(10_000) - 0.34 / 2.34) < 1e-4
    assert all(0.078 <= ex._yz_k(n) <= 0.146 for n in (2, 12, 48, 288))


def test_a_series_of_identical_flat_bars_has_zero_volatility() -> None:
    bars = ohlc([(3000.0, 3000.0, 3000.0, 3000.0)] * 30)
    assert ex.yang_zhang(bars, n=12).dropna().eq(0.0).all()


def test_it_is_drift_independent() -> None:
    # The whole claim. Identical bar SHAPES, one series flat and one ramping
    # hard: Yang-Zhang must return the same sigma, because the ramp lives in
    # the close-to-close return it deliberately does not use.
    shape = [(0.0, 2.0, -2.0, 1.0)] * 40  # o, h, l, c as offsets from a base
    flat = ohlc([(3000 + o, 3000 + h, 3000 + lo, 3000 + c) for o, h, lo, c in shape])
    ramp = ohlc([(3000 + o + 5 * i, 3000 + h + 5 * i, 3000 + lo + 5 * i, 3000 + c + 5 * i)
                 for i, (o, h, lo, c) in enumerate(shape)])
    a = ex.yang_zhang(flat, n=12).dropna()
    b = ex.yang_zhang(ramp, n=12).dropna()
    # Not exactly equal: the log transform makes the same dollar range a
    # slightly smaller LOG range at a higher price. Same order, though --
    # a close-to-close estimator would be several times larger on the ramp.
    assert (b / a).max() < 1.05


def test_a_close_to_close_estimator_would_fail_that_test() -> None:
    # The control for the test above. If this ever stops holding, the ramp
    # fixture is too weak to distinguish the two estimators and the
    # drift-independence test above is passing vacuously.
    shape = [(0.0, 2.0, -2.0, 1.0)] * 40
    ramp = ohlc([(3000 + o + 5 * i, 3000 + h + 5 * i, 3000 + lo + 5 * i, 3000 + c + 5 * i)
                 for i, (o, h, lo, c) in enumerate(shape)])
    flat = ohlc([(3000 + o, 3000 + h, 3000 + lo, 3000 + c) for o, h, lo, c in shape])
    def c2c(b: pd.DataFrame) -> pd.Series:
        return np.log(b["close"]).diff().rolling(12).std()

    assert c2c(ramp).dropna().mean() > 5 * c2c(flat).dropna().mean()


def test_a_window_shorter_than_n_is_nan_not_a_partial_estimate() -> None:
    # A partial-window estimate is a smaller number that looks like calm, and
    # `r_ratio` divides by it.
    #
    # FIRST VALID IS INDEX n, NOT n-1, and the extra bar is not an off-by-one.
    # The overnight term is ln(O_t / C_{t-1}), so n overnight returns need
    # n+1 bars. An implementation that produced a number at index 11 would be
    # computing the window from 11 overnight returns and one NaN.
    out = ex.yang_zhang(ohlc([(3000.0, 3001.0, 2999.0, 3000.5)] * 30), n=12)
    assert out.iloc[:12].isna().all()
    assert out.iloc[12:].notna().all()


def test_wider_bars_give_a_larger_sigma() -> None:
    narrow = ohlc([(3000.0, 3000.5, 2999.5, 3000.2)] * 30)
    wide = ohlc([(3000.0, 3005.0, 2995.0, 3002.0)] * 30)
    assert ex.yang_zhang(wide, n=12).dropna().mean() > \
        ex.yang_zhang(narrow, n=12).dropna().mean()


def test_sigma_is_never_negative() -> None:
    # The Rogers-Satchell term is a sum of products that can go negative on a
    # single bar. Summed into a variance it must not drive the total below
    # zero and produce a NaN from the square root.
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(200):
        o, c = 3000 + rng.normal(0, 2), 3000 + rng.normal(0, 2)
        rows.append((o, max(o, c) + abs(rng.normal(0, 1)), min(o, c) - abs(rng.normal(0, 1)), c))
    out = ex.yang_zhang(ohlc(rows), n=12).dropna()
    assert (out >= 0).all()
    assert out.notna().all()


# --------------------------------------------------------------------------
# Hurst -- mathematical.md §6. Task 9 of the 18-20 Sep block.
#
# §6 says "Do not trade from one noisy Hurst estimate" and asks for at least
# two methods. That sentence becomes `hurst_agree` or it becomes nothing, so
# what gets tested hardest is that the two estimators agree on series whose
# answer is known -- and that they take the SAME INPUT. DFA integrates its
# input and variance-time differences its input, so feeding one prices and
# the other returns yields 0.5 and 1.5 for the same series and neither
# function can tell.


@cache
def walk(n: int, phi: float = 0.0, seed: int = 0) -> np.ndarray:
    """Log prices whose increments are AR(1) with coefficient `phi`.

    Cached: eight tests ask for the same 20,000-step series and the AR(1)
    recursion is a Python loop. Callers must not mutate the result.

    phi = 0 is a random walk and H = 0.5. phi > 0 makes increments persistent
    and lifts H; phi < 0 makes them mean-reverting and lowers it. This is
    SHORT-range dependence, not true long memory -- enough to check an
    estimator responds in the right direction, not enough to pin a value.
    """
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n)
    r = np.empty(n)
    r[0] = e[0]
    for i in range(1, n):
        r[i] = phi * r[i - 1] + e[i]
    return np.log(3000.0) + np.cumsum(r) * 1e-4


def test_both_estimators_return_half_for_a_random_walk() -> None:
    x = walk(20_000)
    assert ex.hurst_dfa(x) == pytest.approx(0.5, abs=0.05)
    assert ex.hurst_vt(x) == pytest.approx(0.5, abs=0.05)


def test_both_exceed_half_when_increments_are_persistent() -> None:
    x = walk(20_000, phi=0.6)
    assert ex.hurst_dfa(x) > 0.55
    assert ex.hurst_vt(x) > 0.55


def test_both_fall_below_half_when_increments_mean_revert() -> None:
    # MEASURED AT SHORT SCALES, and the restriction is the finding rather
    # than a way to make the test pass. AR(1) anti-persistence is SHORT-range:
    # by s = 128 the correlation has decayed and the series is a random walk
    # again, so a regression pooling scales 4..256 is dominated by the long
    # end and returns 0.48 -- correct, and blind to what the fixture contains.
    #
    # 2026-09-18, phi = -0.6, same series:
    #     scales 4..32     dfa 0.288   vt 0.444
    #     scales 4..256    dfa 0.373   vt 0.476
    #
    # This is why §6 asks for several scales and separate readings at 5m and
    # 15m rather than one pooled number: H is scale-dependent, and pooling
    # hides exactly the regime the strategy is trying to detect.
    x = walk(20_000, phi=-0.6)
    short = (4, 8, 16, 32)
    assert ex.hurst_dfa(x, short) < 0.45
    assert ex.hurst_vt(x, short) < 0.45


def test_dfa_refuses_scales_below_four() -> None:
    # A least-squares line through 2 or 3 points fits almost exactly, so F(s)
    # collapses toward zero and the log-log slope explodes. Measured before
    # the guard: including s = 2 returned H = 14.0 on an anti-persistent
    # series. The guard drops them, so the answer stays sane rather than
    # becoming spectacular.
    x = walk(20_000, phi=-0.6)
    assert ex.hurst_dfa(x, (2, 4, 8, 16)) == pytest.approx(
        ex.hurst_dfa(x, (4, 8, 16)), abs=1e-12)


def test_too_few_usable_scales_is_nan_not_a_two_point_regression() -> None:
    # A slope through two points is exact and meaningless. Both estimators
    # need three scales before they will answer.
    x = walk(300)
    assert np.isnan(ex.hurst_dfa(x, (4, 128)))
    assert np.isnan(ex.hurst_vt(x, (4, 128)))


def test_the_two_estimators_agree_on_a_random_walk() -> None:
    # The claim §6 rests on. If they disagree on the easiest possible series,
    # `h_agree` will be False everywhere and the gate never opens.
    x = walk(20_000)
    assert ex.hurst_agree(ex.hurst_dfa(x), ex.hurst_vt(x))


def test_they_are_required_to_agree_before_either_is_used() -> None:
    # §6: "Do not trade from one noisy Hurst estimate."
    assert not ex.hurst_agree(0.52, 0.61)
    assert ex.hurst_agree(0.57, 0.59)


def test_agreement_is_symmetric() -> None:
    assert ex.hurst_agree(0.52, 0.61) == ex.hurst_agree(0.61, 0.52)


def test_both_take_log_prices_and_passing_returns_is_a_detectable_error() -> None:
    # The input convention, pinned. Handing a level-taking estimator its own
    # differences shifts H by about 1, which is the whole usable range -- so
    # the mistake is silent unless something asserts it is not.
    x = walk(20_000)
    r = np.diff(x)
    assert abs(ex.hurst_dfa(x) - ex.hurst_dfa(r)) > 0.3
    assert abs(ex.hurst_vt(x) - ex.hurst_vt(r)) > 0.3


def test_too_few_points_returns_nan_rather_than_a_confident_wrong_number() -> None:
    assert np.isnan(ex.hurst_dfa(np.arange(10.0)))
    assert np.isnan(ex.hurst_vt(np.arange(10.0)))


def test_a_constant_series_is_nan_not_zero() -> None:
    # No variance at any scale. A regression on log(0) must not return a
    # number, and 0.0 would read as "maximally anti-persistent".
    flat = np.full(5_000, np.log(3000.0))
    assert np.isnan(ex.hurst_dfa(flat))
    assert np.isnan(ex.hurst_vt(flat))


def test_both_hurst_estimators_use_the_same_scale_set() -> None:
    # H is scale-dependent, so two estimators regressed over DIFFERENT scales
    # are not two readings of one quantity -- and `hurst_agree` compares them.
    # Before the fix DFA dropped s=2 and VT did not: on a pure random walk
    # with a shared (2,4,8,16,32) that gave dfa 0.563 / vt 0.510 / agree
    # False, closing the gate on the one series whose answer is known.
    # Found by review 2026-09-18.
    x = walk(20_000)
    mixed, floored = (2, 4, 8, 16, 32), (4, 8, 16, 32)
    assert ex.hurst_dfa(x, mixed) == ex.hurst_dfa(x, floored)
    assert ex.hurst_vt(x, mixed) == ex.hurst_vt(x, floored)


def test_dfa_is_biased_high_on_a_short_scale_ladder_and_agreement_fails_there() -> None:
    # A SECOND REASON §6's 15-MINUTE HURST CANNOT COME FROM COARSE BARS.
    # Sharing a scale set (the fix above) is necessary and not sufficient: on
    # a pure random walk restricted to scales (4,8,16,32), DFA reads 0.563
    # against variance-time's 0.513 and a true 0.5 -- DFA's well-known
    # finite-size bias at small windows. The gap is 0.050 against AGREE_TOL
    # of 0.05, so `hurst_agree` returns False on the one series whose answer
    # is known, and `h_agree` would be systematically False for any feature
    # computed over a short ladder.
    #
    # Pinned rather than tuned around: widening AGREE_TOL to make this pass
    # would hide the bias instead of measuring it.
    x = walk(20_000)
    short = (4, 8, 16, 32)
    d, v = ex.hurst_dfa(x, short), ex.hurst_vt(x, short)
    assert d - v > 0.04, "DFA's short-ladder bias, measured 2026-09-18"
    assert not ex.hurst_agree(d, v)
    # Over the default ladder, which reaches 256, they do agree.
    assert ex.hurst_agree(ex.hurst_dfa(x), ex.hurst_vt(x))


def test_yang_zhang_refuses_a_one_bar_window_rather_than_dividing_by_zero() -> None:
    # (n+1)/(n-1) divides by zero at n=1. Found by review 2026-09-18.
    with pytest.raises(ValueError, match="at least 2"):
        ex._yz_k(1)


# --------------------------------------------------------------------------
# GARCH(1,1) with Student-t innovations -- §2's second leg. Task 7.
#
# The only honest test of an estimator is recovering parameters from a series
# simulated with known ones. Everything else checks that it does not crash.
#
# §2 specifies Student-t rather than Gaussian innovations "because GC returns
# have fat tails". That is a testable claim about the estimator too: fitting a
# t to a fat-tailed series must return a small nu, and fitting it to Gaussian
# data must return a large one.


@cache
def garch_series(n: int = 8_000, omega: float = 2e-6, alpha: float = 0.08,
                 beta: float = 0.90, nu: float = 6.0, seed: int = 0) -> np.ndarray:
    """Returns simulated from a known GARCH(1,1)-t. Cached; do not mutate."""
    rng = np.random.default_rng(seed)
    z = rng.standard_t(nu, size=n) / np.sqrt(nu / (nu - 2))   # unit variance
    r = np.empty(n)
    s2 = omega / (1 - alpha - beta)
    for i in range(n):
        r[i] = np.sqrt(s2) * z[i]
        s2 = omega + alpha * r[i] ** 2 + beta * s2
    return r


def test_it_recovers_known_parameters_from_a_simulated_series() -> None:
    fit = ex.garch_fit(garch_series())
    # Persistence is what the forecast actually depends on, and it is far
    # better identified than alpha and beta separately -- they trade off.
    assert fit.alpha + fit.beta == pytest.approx(0.98, abs=0.03)
    assert fit.alpha == pytest.approx(0.08, abs=0.05)
    assert fit.nu == pytest.approx(6.0, abs=3.0)


def test_fat_tails_give_a_small_nu_and_gaussian_data_a_large_one() -> None:
    # §2's reason for specifying Student-t, turned into a check on the fit.
    fat = ex.garch_fit(garch_series(nu=4.0, seed=1))
    rng = np.random.default_rng(2)
    thin = ex.garch_fit(rng.standard_normal(8_000) * 0.01)
    assert fat.nu < thin.nu


def test_a_non_stationary_fit_is_refused_not_returned() -> None:
    # alpha + beta >= 1 means the variance forecast diverges. Returning it
    # quietly puts an infinite r_hat_60 into the trade filter.
    with pytest.raises(ValueError, match="stationar"):
        ex.garch_forecast(sigma2_t=1e-4, params=ex.GarchFit(1e-6, 0.2, 0.85, 6.0), m=12)


def test_the_m_step_forecast_reverts_toward_the_unconditional_variance() -> None:
    # sigma2_bar + (alpha+beta)^m (sigma2_t - sigma2_bar). As m grows the
    # forecast must approach the unconditional level, not stay at the current.
    p = ex.GarchFit(omega=2e-6, alpha=0.08, beta=0.90, nu=6.0)
    bar = p.omega / (1 - p.alpha - p.beta)
    hot = 10 * bar
    near = ex.garch_forecast(sigma2_t=hot, params=p, m=1)
    far = ex.garch_forecast(sigma2_t=hot, params=p, m=500)
    assert hot > near > far > bar
    assert far == pytest.approx(bar, rel=0.05)


def test_a_zero_step_forecast_is_the_current_variance() -> None:
    p = ex.GarchFit(omega=2e-6, alpha=0.08, beta=0.90, nu=6.0)
    assert ex.garch_forecast(sigma2_t=5e-5, params=p, m=0) == pytest.approx(5e-5)


def test_the_fit_is_stationary_by_construction() -> None:
    fit = ex.garch_fit(garch_series())
    assert fit.alpha + fit.beta < 1.0
    assert fit.omega > 0
    assert fit.nu > 2.0


def test_a_series_too_short_to_identify_four_parameters_is_refused() -> None:
    with pytest.raises(ValueError, match="at least"):
        ex.garch_fit(np.array([0.001, -0.002, 0.0005]))


def test_the_recursion_matches_a_plain_python_loop() -> None:
    # The variance path is computed with a filter rather than a per-bar loop.
    # If the two ever disagree the filter is wrong, and the likelihood it
    # feeds would be wrong in a way that still converges to something.
    r = garch_series(n=500)
    omega, alpha, beta = 2e-6, 0.08, 0.90
    got = ex._garch_variance(r, omega, alpha, beta)
    want = np.empty(len(r))
    want[0] = float(np.var(r))
    for i in range(1, len(r)):
        want[i] = omega + alpha * r[i - 1] ** 2 + beta * want[i - 1]
    assert np.allclose(got, want)
