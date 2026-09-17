"""The cost arithmetic, pinned. This is where an order-of-magnitude slip hides.

WHY THIS FILE IS MORE PARANOID THAN ITS SUBJECT DESERVES. `to_bp` is one
division. A draft of the design divided it wrong -- it put a $0.30 spread at
8.8 bp instead of 0.88 -- and that single factor of ten flipped the expectancy
at the spec's own parameters from +6 bp to -2 bp, i.e. it reversed the decision
about whether the strategy was viable at all. A one-line function that can
reverse a decision earns tests against known values.

The two known values are chosen because they are independently checkable:
one GC tick is $0.10 and `M3B_DRIFT.md` already prices the GC round trip at
0.3504 bp including commission, so 0.294 bp of spread is the number that must
come back.
"""

from __future__ import annotations

import pytest

import e3_cost

GOLD = 3400.0


def test_thirty_cents_at_3400_is_under_one_basis_point():
    # The check that catches a 10x slip. 0.30 / 3400 = 8.82e-5 = 0.882 bp.
    assert e3_cost.to_bp(0.30, GOLD) == pytest.approx(0.882, abs=0.001)


def test_one_gc_tick_at_3400_is_the_m3b_floor():
    # Cross-check against a number this repo published independently:
    # M3B_DRIFT.md's 0.3504 bp round trip is one tick of spread plus commission.
    assert e3_cost.to_bp(0.10, GOLD) == pytest.approx(0.294, abs=0.001)


def test_the_dukascopy_median_round_trips_back_to_its_dollar_value():
    # SPOT_FEED_CHECK.md §1 measured 1.91 bp. Going back the other way must
    # land near $0.65, not $0.065 -- the same slip in reverse.
    assert 1.91 / 1e4 * GOLD == pytest.approx(0.649, abs=0.001)


def test_breakeven_win_rate_at_the_spec_parameters():
    # D = $5.00, R = $12.50 at 3400 -> 14.71 / 36.76 bp, at the venue's 0.88 bp.
    assert e3_cost.breakeven(d_bp=14.71, r_bp=36.76, cost_bp=0.88) == pytest.approx(0.303, abs=0.002)


@pytest.mark.parametrize("cost_bp", [0.35, 0.88, 1.91])
def test_ev_is_positive_at_forty_two_percent_at_every_venue_considered(cost_bp: float):
    # The corrected conclusion, pinned so the withdrawn one cannot come back.
    assert e3_cost.ev_bp(p=0.42, d_bp=14.71, r_bp=36.76, cost_bp=cost_bp) > 0


def test_cost_enters_ev_once_not_twice():
    # A round trip is one full spread. Charging it on entry and again on exit
    # is the classic double-count, and it turns a real edge into a fake loss.
    a = e3_cost.ev_bp(p=0.42, d_bp=14.71, r_bp=36.76, cost_bp=0.0)
    b = e3_cost.ev_bp(p=0.42, d_bp=14.71, r_bp=36.76, cost_bp=2.0)
    assert a - b == pytest.approx(2.0)


def test_breakeven_is_the_win_rate_at_which_ev_is_zero():
    # The two functions must agree, or one of them is wrong and nothing says so.
    p = e3_cost.breakeven(d_bp=14.71, r_bp=36.76, cost_bp=1.91)
    assert e3_cost.ev_bp(p=p, d_bp=14.71, r_bp=36.76, cost_bp=1.91) == pytest.approx(0.0, abs=1e-9)


def test_s13_excludes_a_stop_whose_spread_eats_a_quarter_of_the_risk():
    # §13 rejects a trade when estimated slippage exceeds 25% of intended risk.
    # At D = $2.00/oz (5.88 bp) against the archive's 1.91 bp that is 32%.
    surf = e3_cost.surface(price=GOLD, cost_bp=1.91, p=0.42,
                           d_usd=[2.00, 5.00], r_mult=[2.5])
    assert bool(surf.loc[surf.d_usd == 2.00, "excluded_by_s13"].iloc[0]) is True
    assert bool(surf.loc[surf.d_usd == 5.00, "excluded_by_s13"].iloc[0]) is False


def test_the_d_floor_is_cost_over_the_quarter_risk_ceiling():
    # Design §4 predicts $2.60/oz at the archive's 1.91 bp. Derived, not asserted:
    # c / 0.25 = 7.64 bp, and 7.64 bp of 3400 is $2.598.
    assert e3_cost.d_floor_usd(cost_bp=1.91, price=GOLD) == pytest.approx(2.598, abs=0.002)


def test_the_target_floor_of_ten_dollars_binds_at_tight_stops():
    # §10: R = max(2.5D, $10.00). At D = $2.00 the multiple leg gives $5.00,
    # so the floor binds and the realised payoff is 5:1, not 2.5:1 -- which is
    # a much stronger claim than the spec argues for anywhere.
    surf = e3_cost.surface(price=GOLD, cost_bp=1.91, p=0.42, d_usd=[2.00], r_mult=[2.5])
    assert surf["r_bp"].iloc[0] == pytest.approx(e3_cost.to_bp(10.00, GOLD), abs=1e-6)


def test_a_zero_stop_is_refused_rather_than_dividing_by_zero() -> None:
    # A zero-width stop is not an excluded trade, it is invalid input, and
    # ZeroDivisionError names neither. Found by review 2026-09-18.
    with pytest.raises(ValueError, match="d_usd"):
        e3_cost.surface(price=GOLD, cost_bp=1.91, p=0.42, d_usd=[0.0], r_mult=[2.5])


def test_a_zero_price_is_refused() -> None:
    with pytest.raises(ValueError, match="price"):
        e3_cost.to_bp(0.30, 0.0)
