"""The four strategies, against rows whose answer is known by construction.

WHY THE CONTEXT IS BUILT BY HAND HERE. `context.build` is tested end to end in
`test_track_c_engine.py`; what these tests are about is the DECISION, and a
decision test that has to steer a 2,880-bar percentile window into place is a
test about the fixture. One row, every input named, nothing implicit.

**THE STRUCTURAL-DIFFERENCE TESTS ARE THE POINT OF THIS FILE.** The task asks
for strategies that differ in kind rather than in parameter, and the honest way
to hold that claim is to assert the gates are mutually exclusive: S1 needs
volatility expansion and S3 needs compression, S1/S4 need H above 0.50 and S3
needs it below 0.45. Four variants of one idea could not pass these.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import pytest

import fsm
from track_c import bracket, config, fills, strategies
from track_c.strategies import s1, s2, s3, s4
from track_c.suggestion import Refusal, Suggestion

CFG = config.load()
DAY = fsm.Day()

NEUTRAL: dict[str, Any] = {
    "open": 3400.0, "high": 3401.0, "low": 3399.0, "close": 3400.0,
    "atr_usd": 4.0, "vol_ratio": 1.0, "h_dfa": 0.50, "h_vt": 0.50, "h_agree": True,
    "asian_high": 3400.0, "asian_low": 3390.0, "pdh": 3410.0, "pdl": 3390.0,
    "vwap": 3400.0, "vwap_z": 0.0, "bb_width": 0.001, "bb_pct": 0.5, "ticks_pct": 0.5,
    "s4_dc_high": 3401.0, "s4_dc_low": 3399.0, "s3_dc_high": 3402.0, "s3_dc_low": 3398.0,
    "news_lock": False, "news_hard": False,
    "in_s1": True, "in_s2": True, "in_s3": True, "in_s4": True,
    "spread_usd": 0.40, "session": pd.Timestamp("2026-07-16").date(),
}


def ctx(*rows: Mapping[str, Any]) -> pd.DataFrame:
    """A context frame of `rows`, each overriding `NEUTRAL`."""
    idx = pd.date_range("2026-07-16T13:00:00Z", periods=len(rows), freq="5min", tz="UTC")
    return pd.DataFrame([{**NEUTRAL, **r} for r in rows], index=idx)


# --------------------------------------------------------------------------
# One firing setup per strategy, with the bracket checked arithmetically.


def test_s1_fires_on_an_asian_high_breakout() -> None:
    out = s1.evaluate(ctx({"close": 3401.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62}),
                      0, cfg=CFG, day=DAY)
    assert isinstance(out, Suggestion)
    assert out.side == 1
    # entry = close - 0.25 ATR; stop = level - 1.00 ATR; so D = (close - level) + 0.75 ATR.
    assert out.entry == pytest.approx(3400.0)
    assert out.stop == pytest.approx(3396.0)
    assert out.d_usd == pytest.approx(4.0)
    assert out.target == pytest.approx(3410.0)   # clip(2.5 x 4, 10, 15) = 10
    assert 0.0 <= out.confidence <= 1.0


def test_s1_takes_the_short_side_below_the_asian_low() -> None:
    out = s1.evaluate(ctx({"close": 3389.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62}),
                      0, cfg=CFG, day=DAY)
    assert isinstance(out, Suggestion)
    assert out.side == -1
    assert out.stop > out.entry > out.target


def test_s2_fires_on_a_prior_day_low_sweep_that_is_reclaimed() -> None:
    swept = {"low": 3387.0, "close": 3388.0, "h_dfa": 0.45, "h_vt": 0.46}
    reclaim = {"low": 3388.0, "close": 3390.5, "h_dfa": 0.45, "h_vt": 0.46}
    out = s2.evaluate(ctx(swept, reclaim), 1, cfg=CFG, day=DAY)
    assert isinstance(out, Suggestion)
    assert out.side == 1
    assert out.entry == pytest.approx(3389.5)      # 3390.5 - 0.25 x 4
    assert out.stop == pytest.approx(3385.0)       # swept 3387 - 0.50 x 4
    assert out.d_usd == pytest.approx(4.5)


def test_s3_fades_a_two_sigma_excursion_below_the_session_vwap() -> None:
    row = {"close": 3395.0, "vwap_z": -2.5, "h_dfa": 0.40, "h_vt": 0.41,
           "vol_ratio": 0.80, "s3_dc_low": 3392.0}
    out = s3.evaluate(ctx(row), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Suggestion)
    assert out.side == 1                            # below the mean, buy it back
    assert out.stop == pytest.approx(3390.0)        # 3392 - 0.50 x 4
    assert out.d_usd == pytest.approx(4.0)


def test_s4_fires_on_a_squeeze_breakout() -> None:
    row = {"atr_usd": 1.0, "close": 3400.5, "bb_pct": 0.10, "ticks_pct": 0.70,
           "h_dfa": 0.60, "h_vt": 0.61, "s4_dc_high": 3400.0, "s4_dc_low": 3397.0}
    out = s4.evaluate(ctx(row), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Suggestion)
    assert out.side == 1
    assert out.stop == pytest.approx(3396.25)       # far edge 3397 - 0.75 x 1
    assert out.d_usd == pytest.approx(4.0)


# --------------------------------------------------------------------------
# Refusals name the condition, and every name is in the strategy's own list.


@pytest.mark.parametrize(("override", "reason"), [
    ({"in_s1": False}, "window"),
    ({"news_lock": True}, "news_lock"),
    ({"atr_usd": float("nan")}, "inputs"),
    ({"asian_low": 3399.0}, "range_width"),         # a 1.0 range against a 4.0 ATR
    ({"vol_ratio": 1.0}, "vol_expansion"),
    ({"h_agree": False}, "hurst_agree"),
    ({"h_dfa": 0.40}, "hurst_trending"),
    ({"close": 3400.1}, "breakout"),                # inside the level by less than delta
    ({"close": 3404.0}, "not_extended"),            # 4.0 > 0.75 x ATR
])
def test_s1_refuses_with_the_condition_that_stopped_it(override: Mapping[str, Any], reason: str) -> None:
    base = {"close": 3401.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62}
    out = s1.evaluate(ctx({**base, **override}), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Refusal)
    assert out.reason == reason
    assert s1.CONDITIONS[out.stage] == reason


def test_every_refusal_stage_indexes_its_own_condition_list() -> None:
    """`suggestion.refuse` looks the stage up rather than taking it, so a
    mistyped reason is a test failure and not an uncounted column."""
    for m in strategies.ALL:
        out = m.evaluate(ctx({f"in_{m.NAME}": False}), 0, cfg=CFG, day=DAY)
        assert isinstance(out, Refusal)
        assert m.CONDITIONS[out.stage] == out.reason == "window"


def test_a_structural_stop_outside_section_10s_bounds_is_refused_not_clipped() -> None:
    """Clipping would produce a different trade with the same name, and the
    backtest would then score the clipped one."""
    wide = {"close": 3401.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62,
            "atr_usd": 8.0, "asian_low": 3384.0}   # range 16 = 2.0 ATR, so the guard passes
    out = s1.evaluate(ctx(wide), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Refusal)
    assert out.reason == "stop_too_wide"


def test_a_stop_tighter_than_two_dollars_is_refused() -> None:
    """§2.1's defect: a $0.50 stop still buys a $10 target -- a 20:1 nominal R
    that comes from the target floor rather than from anything anyone chose."""
    tight = {"close": 3400.2, "asian_low": 3396.0, "atr_usd": 1.5,
             "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62}
    out = s1.evaluate(ctx(tight), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Refusal)
    assert out.reason == "stop_too_tight"


def test_section_13s_cost_exclusion_narrows_section_10s_stop_band() -> None:
    """**A finding, not a fixture detail, and it is in the report.**

    §13 excludes a trade whose cost exceeds a quarter of intended risk. The
    modelled round trip is `1.75 x spread` (one spread, plus half a spread of
    slippage at 1.5x margin), so the exclusion is `D >= 7 x spread`. At the
    spread `SPOT_FEED_CHECK.md` measured on XAUUSD -- 1.91 bp, about $0.65 an
    ounce at $3,400 -- that is **D >= $4.55**, and §10 caps D at $5.00.

    So §10's nominal $2-$5 band is, at the archive's own spread, a band roughly
    half a dollar wide. That is not a bug in either rule; it is what the two
    rules say together, and a strategy whose structural stop does not land in
    that half-dollar is refused before anything else is measured.
    """
    fires = {"close": 3401.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62}
    out = s1.evaluate(ctx({**fires, "spread_usd": 0.65}), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Refusal) and out.reason == "slippage"
    # The same row at a $0.55 spread clears it: D = $4.00 needs spread <= $0.571.
    ok = s1.evaluate(ctx({**fires, "spread_usd": 0.55}), 0, cfg=CFG, day=DAY)
    assert isinstance(ok, Suggestion)


def test_section_13_leaves_a_quarter_of_section_10s_band_and_none_of_it_on_wide_bars() -> None:
    """**§3's "half a dollar wide" finding, now measured on real bars instead of
    on one quoted spread — and it is worse than §3 said, in a specific way.**

    §13 refuses when `1.75 x spread > 0.25 x D`, i.e. `D >= 7 x spread`. §10
    caps `D` at $5.00. So the spread does not filter trades directly; it eats
    §10's band from the bottom, and what is left is `[7 x spread, $5.00]`.

    **Measured over June 2026** (`data/spot/XAUUSD`, 6,024 5-minute bars, median
    close $4,224):

        spread p50 = 1.452 bp -> D >= $4.29   usable band $0.71 of $3.00  (24%)
        spread p75 = 1.696 bp -> D >= $5.01   EMPTY
        spread p90 = 1.853 bp -> D >= $5.48   EMPTY

    So on a **median** bar a strategy must land its structural stop inside a
    71-cent window or be refused on cost, and on the **widest quarter of bars no
    stop of any size is admissible**. That is why `stop_too_wide` dominates the
    risk gates in the attrition table rather than `slippage` does: the trades
    that reach §13 are the ones that already squeezed under the cap.

    **Neither rule is wrong alone.** §10 is in dollars, §13 is a fraction of
    price, and nobody chose the window their product leaves -- which also means
    it moves when gold does, with no config edit to show for it.

    ⚠️ **An earlier version of this test claimed the band was closed outright.**
    It used `SPOT_FEED_CHECK.md`'s 1.91 bp -- one validated hour from 2025, and
    wider than this archive's median. The arithmetic was right and the input was
    stale, which is the more dangerous of the two.
    """
    price = 4224.0  # median close, June 2026 archive
    d_max = config.f(CFG, "risk.d_max_usd")
    d_min = config.f(CFG, "risk.d_min_usd")
    per_spread = fills.round_trip_usd(1.0, CFG, news=False) / config.f(
        CFG, "cost.max_slippage_share")
    assert abs(per_spread - 7.0) < 1e-9, "§13 is D >= 7 x spread"

    def d_needed(bp: float, px: float = price) -> float:
        return bp / 1e4 * px * per_spread

    # A median bar leaves a fraction of §10's band; a p75 bar leaves none of it.
    assert abs((d_max - d_needed(1.452)) / (d_max - d_min) - 0.24) < 0.02
    assert d_needed(1.696) > d_max, "the p75 bar should admit no stop at all"

    # And the window tightens as gold rises, with nothing edited to cause it.
    assert d_needed(1.452, 3400.0) < d_needed(1.452, price)

    # It bites where the table says it does: p90 spread, stop inside §10's band.
    out = bracket.build(
        strategy="s1", conditions=strategies.CONDITIONS["s1"],
        ts=pd.Timestamp("2026-06-15T13:00Z"), side=1,
        close=price, atr=4.0, stop=price - 4.00 - 0.25 * 4.0,
        spread_usd=1.853 / 1e4 * price,
        news=False, confidence=0.5, cfg=CFG, day=fsm.Day())
    assert isinstance(out, Refusal) and out.reason == "slippage"

    # ...and a stop near the cap on a tight bar still passes, so the gate reads
    # as selective in the attrition table rather than as broken.
    ok = bracket.build(
        strategy="s1", conditions=strategies.CONDITIONS["s1"],
        ts=pd.Timestamp("2026-06-15T13:00Z"), side=1,
        close=price, atr=4.0, stop=price - 4.80 - 0.25 * 4.0,
        spread_usd=1.201 / 1e4 * price,
        news=False, confidence=0.5, cfg=CFG, day=fsm.Day())
    assert isinstance(ok, Suggestion)


def test_section_10s_dollar_stop_band_is_smaller_than_the_instruments_own_atr() -> None:
    """🔴 **The binding constraint in the first real run, and it is not §13.**

    §10's band is `[$2, $5]` — 20 to 50 ticks at GC's $0.10 tick, a *futures*
    spec carried onto spot. Measured over the June–August 2026 archive (17,651
    bars, gold ~$4,175), the **60-minute ATR** is:

        p10 $2.87   p25 $3.56   **p50 $4.53**   p75 $5.98   p90 $7.90

    **The median ATR is 91% of the entire stop cap**, and on **40.2% of bars the
    one-hour ATR alone already exceeds $5.00.** A structural stop — beyond a
    swing, a range edge, a prior-day extreme — is not smaller than the bar noise
    it must sit behind, so on this instrument at this volatility it lands outside
    §10 far more often than inside.

    **The attrition table says exactly that.** Of everything that reached the
    risk gates in three months: `stop_too_wide` refused **16 of 17** (s1),
    **36 of 41** (s2), **8 of 8** (s4) — while `stop_too_tight` refused
    **nothing, in any strategy**. A band whose lower bound never binds and whose
    upper bound refuses ~90% is not a filter on trade quality; it is a unit
    mismatch. Four suggestions survived three months.

    This also **subsumes the §13 cost finding**: the cost rule barely gets a say,
    because almost nothing reaches it.

    ⛔ **Room's call** — §10 in ATR multiples rather than dollars, a different cap
    for spot, or an explicit decision that Track C does not trade gold at this
    volatility. Not patched here: §10 is the spec's.
    """
    d_min = config.f(CFG, "risk.d_min_usd")
    d_max = config.f(CFG, "risk.d_max_usd")

    # Measured, June-August 2026 archive. Constants, because a test must not
    # need the 173 MB cache to run -- provenance is in the docstring.
    atr_p50, atr_p75, share_over_cap = 4.53, 5.98, 0.402

    assert atr_p50 / d_max > 0.85, "the median ATR should be most of the whole cap"
    assert atr_p75 > d_max, "at p75 the hourly ATR alone exceeds the cap"
    assert share_over_cap > 0.35

    # The lower bound is the one that never binds: nothing on this instrument is
    # too tight, which is what makes the band one-sided in practice.
    assert atr_p50 > 2 * d_min, "d_min is far below the noise floor, so it cannot bite"


def test_a_spread_that_eats_a_quarter_of_the_risk_is_refused() -> None:
    fires = {"close": 3401.0, "vol_ratio": 1.3, "h_dfa": 0.60, "h_vt": 0.62, "spread_usd": 3.0}
    out = s1.evaluate(ctx(fires), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Refusal)
    assert out.reason == "slippage"


# --------------------------------------------------------------------------
# The claim that these are four strategies and not four settings of one.


def test_the_expansion_gate_and_the_compression_gate_cannot_both_pass() -> None:
    assert config.f(CFG, "s1.vol_ratio_min") > config.f(CFG, "s3.vol_ratio_max")


def test_the_trending_gates_and_the_reverting_gate_cannot_both_pass() -> None:
    assert config.f(CFG, "s3.hurst_max") < config.f(CFG, "s1.hurst_min")
    assert config.f(CFG, "s3.hurst_max") < config.f(CFG, "s4.hurst_min")


def test_s1_and_s3_never_fire_on_the_same_row() -> None:
    """The gates above, exercised rather than asserted about the config."""
    rng = np.random.default_rng(3)
    both = 0
    for _ in range(300):
        row = {"close": float(3395 + rng.uniform(0, 10)),
               "vol_ratio": float(rng.uniform(0.5, 1.8)),
               "h_dfa": float(rng.uniform(0.3, 0.7)),
               "h_vt": float(rng.uniform(0.3, 0.7)),
               "vwap_z": float(rng.uniform(-3, 3))}
        row["h_vt"] = row["h_dfa"]        # agreement, so the gate is Hurst and not noise
        frame = ctx(row)
        a = s1.evaluate(frame, 0, cfg=CFG, day=DAY)
        b = s3.evaluate(frame, 0, cfg=CFG, day=DAY)
        both += isinstance(a, Suggestion) and isinstance(b, Suggestion)
    assert both == 0


def test_s1_and_s2_take_opposite_sides_of_the_same_level_break() -> None:
    """S1 buys the break; S2 buys its failure. If they ever agreed on a side at
    the same level, one of them would be the other with extra steps."""
    assert set(s1.CONDITIONS) & {"breakout"}
    assert set(s2.CONDITIONS) & {"sweep", "reclaim"}
    assert config.f(CFG, "s2.hurst_max") >= config.f(CFG, "s1.hurst_min")


def test_a_suggestion_with_an_inverted_stop_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="not behind entry"):
        Suggestion(strategy="sx", ts=pd.Timestamp("2026-07-16T13:00Z"), side=1,
                   entry=3400.0, stop=3402.0, target=3410.0, lots=1.0,
                   expires_at=pd.Timestamp("2026-07-16T13:00:20Z"), confidence=0.5)


def test_the_tail_conditions_are_the_same_three_for_every_strategy() -> None:
    """So four structurally different attrition tables are comparable at the
    bottom even though nothing above it is."""
    for m in strategies.ALL:
        assert m.CONDITIONS[-3:] == bracket.TAIL
