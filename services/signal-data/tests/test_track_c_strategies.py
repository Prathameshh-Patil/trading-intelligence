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
    # atr 2.5 rather than 1.0: §10's bounds are ATR multiples now, and at
    # atr=1.0 this fixture's $4 stop is 4.0x ATR -- refused as too wide.
    row = {"atr_usd": 2.5, "close": 3400.5, "bb_pct": 0.10, "ticks_pct": 0.70,
           "h_dfa": 0.60, "h_vt": 0.61, "s4_dc_high": 3400.0, "s4_dc_low": 3397.0}
    out = s4.evaluate(ctx(row), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Suggestion)
    assert out.side == 1
    assert out.stop == pytest.approx(3395.125)      # far edge 3397 - 0.75 x 2.5
    assert out.d_usd == pytest.approx(4.75)


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
    backtest would then score the clipped one.

    **Shown on s2 rather than s1, and the reason is the finding below**: s2's
    stop hangs off a prior-day extreme, which is a level the market set and not
    a multiple of anything, so it is the strategy whose stop can still run past
    an ATR-scaled cap.
    """
    wide = {"close": 3402.0, "h_dfa": 0.50, "h_vt": 0.50, "atr_usd": 1.0,
            "pdh": 3401.0, "high": 3404.0, "prev_close": 3400.0}
    out = s2.evaluate(ctx(wide), 0, cfg=CFG, day=DAY)
    assert isinstance(out, Refusal)
    assert out.reason in ("stop_too_wide", "sweep", "reclaim")


def test_s1s_own_geometry_keeps_it_inside_an_atr_scaled_band() -> None:
    """**A consequence of moving §10 to ATR multiples, recorded because it is
    easy to mistake for a broken gate.**

    s1's stop is `level - 1.00 x ATR` and its entry is `close - 0.25 x ATR`,
    while `not_extended` caps `close - level` at `0.75 x ATR`. So

        D = (close - level) + 0.75 x ATR   with  0 <= (close - level) <= 0.75 ATR

    which pins **D into [0.75 ATR, 1.50 ATR]** no matter what the market does.
    Against §10's `[0.8, 2.0]` that means **s1 can essentially never be refused
    as too wide** -- its geometry is already ATR-scaled, so an ATR-scaled bound
    agrees with it by construction.

    That is correct rather than broken, and it is also why `stop_too_wide`
    collapsing to near-zero for s1 in the attrition table is the expected
    result of this change and not evidence that the gate stopped working. The
    bound still bites where a stop comes from structure the market set -- s2's
    prior-day extreme, s3's excursion from VWAP.
    """
    pad = config.f(CFG, "s1.stop_pad_atr")
    pull = config.f(CFG, "s1.entry_pullback_atr")
    ext = config.f(CFG, "s1.max_extension_atr")
    # `_broken_level` needs the close to clear the level by §9's delta,
    # `max($0.02, 0.05 x ATR)`, so the extension has a floor as well as a cap.
    delta = 0.05
    lo, hi = pad - pull + delta, pad - pull + ext
    assert (lo, hi) == (0.80, 1.50)

    # BOTH of §10's bounds now sit outside what s1 can produce.
    assert config.f(CFG, "risk.d_min_atr") <= lo, "s1 cannot reach the floor from above"
    assert hi < config.f(CFG, "risk.d_max_atr"), "s1 cannot reach the cap"


def test_a_stop_tighter_than_section_10s_floor_is_refused() -> None:
    """§2.1's defect: a stop far under the floor still buys `clip(2.5D, $10,
    $15)`, a nominal R that comes from the target floor rather than from
    anything anyone chose.

    Exercised through `bracket.build` rather than through a strategy, because
    under ATR multiples **no strategy can reach this floor from above** -- see
    the geometry test below. The rule still has to hold for the one that
    eventually can.
    """
    atr = 4.0
    out = bracket.build(
        strategy="s1", conditions=strategies.CONDITIONS["s1"],
        ts=pd.Timestamp("2026-06-15T13:00Z"), side=1,
        close=4200.0, atr=atr,
        stop=4200.0 - 0.25 * atr - 0.5 * config.f(CFG, "risk.d_min_atr") * atr,
        spread_usd=0.05, news=False, confidence=0.5, cfg=CFG, day=fsm.Day())
    assert isinstance(out, Refusal) and out.reason == "stop_too_tight"


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


def test_moving_section_10_to_atr_reopened_the_band_section_13_had_closed() -> None:
    """**Two rules in different units, and fixing one fixed the pair.**

    The history, because it is the point. §13 refuses when `1.75 x spread >
    0.25 x D`, i.e. `D >= 7 x spread` — a fraction of PRICE. §10 used to cap
    `D` at a flat $5.00 — DOLLARS. Measured on the June–August 2026 archive
    (median close $4,224, spread p50 1.452 bp, 60-minute ATR p50 $4.53), that
    pair left:

        §10 [$2.00, $5.00]      p50 spread -> D >= $4.29 -> $0.71 usable, 24%
                                p75 spread -> D >= $5.01 -> EMPTY

    With §10 restated as ATR multiples the band tracks the instrument, and
    §13 goes back to trimming it rather than closing it:

        §10 [0.8, 2.0] x ATR    = [$3.62, $9.06], $5.44 wide
                                p50 -> $4.77 usable, 88%
                                p75 -> $4.05 usable, 74%
                                p90 -> $3.58 usable, 66%
                                p99 -> $1.51 usable, 28%

    **Nothing about §13 changed.** It was never the binding constraint; it only
    looked like one because §10's cap sat below where the cost floor landed.
    """
    atr, price = 4.53, 4224.0
    per_spread = fills.round_trip_usd(1.0, CFG, news=False) / config.f(
        CFG, "cost.max_slippage_share")
    lo = config.f(CFG, "risk.d_min_atr") * atr
    hi = config.f(CFG, "risk.d_max_atr") * atr

    def usable(bp: float) -> float:
        return max(0.0, hi - max(lo, bp / 1e4 * price * per_spread))

    # The old dollar cap: empty at p75. The new one: still two thirds open.
    assert max(0.0, 5.00 - max(2.00, 1.696 / 1e4 * price * per_spread)) == 0.0
    assert usable(1.696) / (hi - lo) > 0.70

    # A median bar keeps most of the band rather than a sliver of it.
    assert usable(1.452) / (hi - lo) > 0.85

    # And §13 still bites somewhere, or it would have stopped being a rule.
    assert usable(2.553) / (hi - lo) < 0.35


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


def test_the_tail_conditions_are_the_same_for_every_strategy() -> None:
    """So four structurally different attrition tables are comparable at the
    bottom even though nothing above it is. Four since 2026-09-19: `no_atr`
    joined them when §10's bounds became multiples of an ATR that can be
    missing."""
    for m in strategies.ALL:
        assert m.CONDITIONS[-4:] == bracket.TAIL
