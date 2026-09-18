"""§13's score and §15's state machine, tested on what they must REFUSE.

§15 is written as a list of transitions but its value is the list of things it
prevents -- more than two trades a day, more than one position, a widened stop,
a martingale size, and a limit order turned into a market order after it
expires. Each of those is a rule someone adds back under pressure at 03:00, so
each gets a test rather than a comment.

§13's renormalisation is the subtle one. Three of its nine components died with
the tape. Scoring them as 0.0 with their weights intact silently lowers every
score by the sum of three weights, and then `Score >= 0.72` means something
different from what the spec wrote -- the threshold would be unreachable
rather than strict.
"""

from __future__ import annotations

import pandas as pd
import pytest

import fsm


def row(**over: float) -> dict[str, float]:
    """A candidate that clears every gate, so a test can break exactly one."""
    base = {
        "s_vol": 1.0, "s_hurst": 1.0, "s_hmm": 1.0, "s_sweep": 1.0,
        "s_spread": 0.0, "s_news": 0.0,
        "r_hat_60_usd": 20.0, "h_agree_value": 0.62, "has_sweep": 1.0,
        "d_usd": 3.0, "slippage_usd": 0.1, "news_lockout": 0.0, "p_e": 0.70,
    }
    return base | over


TS = pd.Timestamp("2025-07-15T13:00:00Z")


def admit(r: dict[str, float], d: fsm.Day):
    """`admit` with the four required non-row inputs supplied."""
    return fsm.admit(r, d, ts=TS, entry=3000.0, side=1, cost_bp=1.91)


def day(**over: float) -> fsm.Day:
    return fsm.Day(**({"trades": 0, "losses": 0, "position_open": False} | over))  # type: ignore[arg-type]


# ------------------------------------------------------------- §13 the score

def test_the_surviving_weights_sum_to_one() -> None:
    # Otherwise the 0.72 threshold means something other than what §13 wrote.
    positive = sum(w for k, w in fsm.WEIGHTS.items() if w > 0)
    assert positive == pytest.approx(1.0)


def test_the_dead_flow_components_are_absent_not_zeroed() -> None:
    # S_OFI, S_CVD and S_Hawkes died with the tape. Keeping them at weight
    # zero would be honest; keeping them at their original weight and feeding
    # 0.0 would cap every score below the threshold forever.
    assert not {"s_ofi", "s_cvd", "s_hawkes"} & set(fsm.WEIGHTS)


def test_a_perfect_candidate_scores_one() -> None:
    assert fsm.score(row()) == pytest.approx(1.0)


def test_spread_and_news_subtract_rather_than_add() -> None:
    # §13 writes them with minus signs. A sign slip here makes a wide spread
    # improve a trade.
    assert fsm.score(row(s_spread=1.0)) < fsm.score(row(s_spread=0.0))
    assert fsm.score(row(s_news=1.0)) < fsm.score(row(s_news=0.0))


def test_a_missing_component_is_an_error_not_a_zero() -> None:
    # A silently-absent component is a score computed on fewer terms, which
    # is a different threshold wearing the same number.
    incomplete = row()
    del incomplete["s_hurst"]
    with pytest.raises(KeyError):
        fsm.score(incomplete)


# -------------------------------------------------------- §13 the exclusions

def test_a_hard_exclusion_overrides_a_passing_score() -> None:
    # §13 lists eight exclusions that override the score outright.
    r = row(news_lockout=1.0)
    assert fsm.score(r) >= fsm.SCORE_MIN
    assert "news_lockout" in fsm.exclusions(r, day())
    assert admit(r, day()) is None


@pytest.mark.parametrize(
    ("field", "value", "name"),
    [
        ("r_hat_60_usd", 10.0, "forecast_range"),
        ("h_agree_value", 0.50, "hurst"),
        ("has_sweep", 0.0, "no_sweep"),
        ("d_usd", 6.0, "stop_too_wide"),
        ("slippage_usd", 1.0, "slippage"),
        ("news_lockout", 1.0, "news_lockout"),
        ("p_e", 0.50, "p_e"),
    ],
)
def test_each_exclusion_fires_on_its_own_condition(field: str, value: float, name: str) -> None:
    assert name in fsm.exclusions(row(**{field: value}), day())


def test_a_clean_candidate_has_no_exclusions() -> None:
    assert fsm.exclusions(row(), day()) == ()


def test_the_slippage_exclusion_is_a_share_of_risk_not_an_absolute() -> None:
    # §13: "Slippage estimate > 25% of intended risk". At D = $4.00 a $0.90
    # estimate is 22.5% and clears; at D = $3.00 the same $0.90 is 30%.
    assert "slippage" not in fsm.exclusions(row(d_usd=4.0, slippage_usd=0.90), day())
    assert "slippage" in fsm.exclusions(row(d_usd=3.0, slippage_usd=0.90), day())


# --------------------------------------------------------- §15 what it stops

def test_the_third_trade_of_a_day_is_refused() -> None:
    assert admit(row(), day(trades=1)) is not None
    assert admit(row(), day(trades=2)) is None
    assert "trade_limit" in fsm.exclusions(row(), day(trades=2))


def test_a_second_loss_stops_the_day() -> None:
    assert "loss_limit" in fsm.exclusions(row(), day(losses=2))


def test_only_one_position_may_exist_at_a_time() -> None:
    assert "position_open" in fsm.exclusions(row(), day(position_open=True))


def test_an_unfilled_limit_never_becomes_a_market_order() -> None:
    # §15's forbidden transition, and the one most likely to be added back
    # "just to catch the move".
    order = fsm.place_limit(admit(row(), day()))
    expired = fsm.expire(order)
    assert expired.state is fsm.State.FLAT
    assert expired.filled is False
    assert not hasattr(expired, "market_order")


def test_the_limit_expires_after_twenty_seconds() -> None:
    order = fsm.place_limit(admit(row(), day()))
    assert order.expiry_s == 20.0


def test_the_limit_sits_at_half_the_reclaim_wick() -> None:
    # §9: P_entry = P_s + 0.50W.
    c = admit(row(), day())
    assert c is not None
    assert fsm.limit_price(sweep_extreme=2998.0, wick_w=3.0, side=1) == pytest.approx(2999.5)


def test_a_stop_is_never_widened() -> None:
    order = fsm.place_limit(admit(row(), day()))
    with pytest.raises(ValueError, match="widen"):
        fsm.move_stop(order, new_stop=order.candidate.stop - 1.0)


def test_a_stop_may_be_tightened_to_breakeven() -> None:
    # §10 permits breakeven only after 1.5D, but tightening itself is legal.
    order = fsm.place_limit(admit(row(), day()))
    moved = fsm.move_stop(order, new_stop=order.candidate.stop + 0.5)
    assert moved.candidate.stop > order.candidate.stop


def test_size_never_increases_after_a_loss() -> None:
    # Martingale, named and refused. §15 forbids it in terms.
    base = fsm.size_lots(equity=100_000.0, risk_frac=0.004, d_usd=3.0, day=day())
    after = fsm.size_lots(equity=100_000.0, risk_frac=0.004, d_usd=3.0, day=day(losses=1))
    assert after <= base


def test_risk_fraction_defaults_to_the_conservative_end() -> None:
    # §11: "The strategy should default to 0.4%, not 0.7%."
    assert fsm.DEFAULT_RISK_FRACTION == 0.004


def test_a_refused_candidate_cannot_be_placed() -> None:
    with pytest.raises(ValueError, match="no candidate"):
        fsm.place_limit(None)


def test_the_candidate_carries_a_real_timestamp_and_real_basis_points() -> None:
    # An earlier version defaulted ts to 0.0 behind a type: ignore and left
    # d_bp/r_bp/cost_bp at zero -- a candidate that type-checks, reads
    # plausibly, and carries a 1970 timestamp into whatever consumes it.
    c = admit(row(), day())
    assert c is not None
    assert c.ts == TS
    assert c.d_bp == pytest.approx(3.0 / 3000.0 * 1e4)
    assert c.cost_bp == 1.91


def test_the_target_floor_and_cap_come_from_one_definition() -> None:
    # §10's $10 floor and $15 cap live in e3_cost and are imported, not
    # retyped -- two copies is how two files quietly disagree about a target.
    import e3_cost

    assert fsm.TARGET_FLOOR_USD is e3_cost.TARGET_FLOOR_USD
    assert fsm.TARGET_CAP_USD is e3_cost.TARGET_CAP_USD
