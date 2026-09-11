"""Step 5's two claims: it finds the right legs, and it refuses the right ones.

**The population is the whole risk here.** `replay.resolve` walking a tape
correctly is worth nothing if `replay.tied` hands it a different set of legs
than the one `backtest.first_touch_from` resolves by rule -- the numbers would
look fine and would be answering a question nobody asked. So the first test
below does not check a tape walk at all; it checks that the legs this module
calls tied are exactly the legs whose answer FLIPS when the tie rule flips.

The second risk is the opposite one: resolving a tie the tape cannot order,
which would be the bar's rule wearing a tick-resolution label. Every way that
can happen has a test that it comes back `UNRESOLVED` instead.

Nothing here reads a file or the network. Frames are built so the answer is
known by construction.
"""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import NEXT, OPEN, SESSION, bars_at

import replay
from backtest import excursions, first_touch_from
from instruments import GC
from replay import Bracket

# 100.00 entry, GC's 0.10 tick: the target is 101.00 and the stop 99.50.
ENTRY = 100.0
B = Bracket(target=10.0, stop=5.0, horizon=15)


def five_minute_bars(ranges: list[float]) -> pd.DataFrame:
    """Bars at 0, 5, 10, 15, 20 minutes, all one session, all closing at ENTRY."""
    return bars_at([0, 5, 10, 15, 20], [ENTRY] * 5, ranges=ranges)


def leg(side: int = 1) -> pd.DataFrame:
    return pd.DataFrame([{"t": OPEN, "side": side, "entry": ENTRY}])


def tape(prints: list[tuple[int, float]]) -> pd.DataFrame:
    """Prints as (seconds past the tied bar's open, price).

    Seconds rather than minutes because the ordering this module exists to
    recover happens inside one 5-minute bar, which `conftest.ticks_at` cannot
    express.
    """
    bar_open = OPEN + pd.Timedelta(minutes=5)
    return pd.DataFrame({
        "timestamp": [bar_open + pd.Timedelta(seconds=s) for s, _ in prints],
        "price": [p for _, p in prints],
        "size": 1,
    })


# A bar 3.00 wide around 100.00 -- high 101.50, low 98.50 -- clears both.
BOTH = [0.0, 3.0, 0.0, 0.0, 0.0]


# --- the population -------------------------------------------------------

def test_tied_is_exactly_the_legs_the_rule_flips():
    """The load-bearing test. `ties="stop"` and `ties="target"` differ on one
    set of legs, and this module must measure that set and no other."""
    bars, trades = five_minute_bars(BOTH), leg()
    ex = excursions(bars, trades, GC, horizon=B.horizon)

    worst = first_touch_from(ex, target=B.target, stop=B.stop, ties="stop")
    best = first_touch_from(ex, target=B.target, stop=B.stop, ties="target")
    flipped = set(worst.index[worst != best])

    assert set(replay.tied(bars, trades, GC, B)["leg"]) == flipped
    assert flipped, "the fixture is meant to produce a tie"


def test_a_bar_that_clears_one_barrier_is_not_a_tie():
    # 1.20 wide: high 100.60, short of the 101.00 target; low 99.40 takes the stop.
    bars = five_minute_bars([0.0, 1.2, 0.0, 0.0, 0.0])
    assert replay.tied(bars, leg(), GC, B).empty


def test_a_target_hit_before_the_stop_is_not_a_tie():
    """The condition is `hit_t == hit_s`, not `hit_t <= hit_s`. This leg clears
    the target in bar 1 and the stop only in bar 2, so the bar DID order them
    and there is nothing for the tape to resolve. A tie test built only from
    genuine ties cannot tell those two conditions apart."""
    # bar 1: 1.20 wide -> high 101.60 clears the target, low 99.40 does not
    #        reach the 99.50 stop. bar 2: 3.00 wide -> takes the stop.
    bars = bars_at([0, 5, 10, 15, 20],
                   [ENTRY, ENTRY + 1.0, ENTRY, ENTRY, ENTRY],
                   ranges=[0.0, 1.2, 3.0, 0.0, 0.0])
    ex = excursions(bars, leg(), GC, horizon=B.horizon)
    assert first_touch_from(ex, target=B.target, stop=B.stop, ties="stop").iloc[0] == 1
    assert replay.tied(bars, leg(), GC, B).empty


def test_a_leg_the_tape_never_offered_is_not_a_tie():
    """`excursions` marks a leg invalid when its session ends inside the
    horizon, and `first_touch_from` returns NaN there rather than a short leg.
    A tie counted on one of those would be an intrabar ordering for a trade
    that was never available -- so `ex.valid` is part of the condition, not a
    tidy-up after it."""
    # The session ends one bar after entry; the horizon runs to minute 15.
    bars = bars_at([0, 5, 10, 15, 20], [ENTRY] * 5, ranges=BOTH,
                   session=[SESSION, SESSION, NEXT, NEXT, NEXT])
    ex = excursions(bars, leg(), GC, horizon=B.horizon)
    assert first_touch_from(ex, target=B.target, stop=B.stop, ties="stop").isna().all()
    assert replay.tied(bars, leg(), GC, B).empty


def test_the_tying_bar_is_reported():
    got = replay.tied(five_minute_bars(BOTH), leg(), GC, B)
    assert got["bar"].iloc[0] == OPEN + pd.Timedelta(minutes=5)


def test_tied_is_the_single_bracket_spelling_of_tied_from():
    bars, trades = five_minute_bars(BOTH), leg()
    ex = excursions(bars, trades, GC, horizon=B.horizon)
    assert replay.tied(bars, trades, GC, B).equals(replay.tied_from(ex, bars, trades, B))


# --- the tape walk --------------------------------------------------------

def resolved(prints: list[tuple[int, float]], side: int = 1) -> int:
    bars, trades = five_minute_bars(BOTH), leg(side)
    got = replay.resolve(tape(prints), replay.tied(bars, trades, GC, B), GC, B)
    return int(got["first"].iloc[0])


def test_target_printing_first_resolves_to_target():
    assert resolved([(0, 100.0), (10, 101.2), (20, 99.0)]) == replay.TARGET_FIRST


def test_stop_printing_first_resolves_to_stop():
    assert resolved([(0, 100.0), (10, 99.0), (20, 101.2)]) == replay.STOP_FIRST


def test_the_rule_and_the_tape_can_disagree():
    """The reason the module exists: the rule sends every tie to the stop, and
    on this leg the tape says the target came first."""
    bars, trades = five_minute_bars(BOTH), leg()
    ex = excursions(bars, trades, GC, horizon=B.horizon)
    by_rule = first_touch_from(ex, target=B.target, stop=B.stop, ties="stop")

    assert by_rule.iloc[0] == -1
    assert resolved([(0, 100.0), (10, 101.2), (20, 99.0)]) == replay.TARGET_FIRST


def test_a_print_exactly_at_the_barrier_counts():
    """`first_touch_from` compares `>= target` and `<= -stop`. A different
    threshold here would resolve ties the bar never had."""
    assert resolved([(0, 100.0), (10, 101.0), (20, 99.0)]) == replay.TARGET_FIRST


def test_a_short_reads_identically():
    """Signed in the trade's favour, so a short's target is BELOW its entry."""
    assert resolved([(0, 100.0), (10, 98.8), (20, 101.0)], side=-1) == replay.TARGET_FIRST


def test_the_gap_between_the_two_touches_is_reported():
    bars, trades = five_minute_bars(BOTH), leg()
    got = replay.resolve(tape([(0, 100.0), (10, 101.2), (20, 99.0)]),
                         replay.tied(bars, trades, GC, B), GC, B)
    assert got["gap_ns"].iloc[0] == 10 * 1e9


# --- the refusals ---------------------------------------------------------

def test_two_prints_in_one_nanosecond_are_unresolved():
    """The tape is then in the bar's position, and picking would be the rule
    wearing a tick-resolution label."""
    assert resolved([(10, 101.2), (10, 99.0)]) == replay.UNRESOLVED


def test_a_barrier_the_tape_never_prints_is_unresolved():
    """The bar's extreme can come from a print this window's edges exclude.
    Reported, not smoothed into one of the two answers.

    The trailing print matters: with a missing barrier's index left at -1, a
    tape ending on the OTHER barrier's print makes the two compare equal and
    this passes by accident. Ending elsewhere makes the guard load-bearing."""
    assert resolved([(0, 100.0), (10, 101.2), (20, 100.5)]) == replay.UNRESOLVED


def test_prints_outside_the_tied_bar_do_not_decide_it():
    """A five-minute window, so the next bar's tape cannot reach back."""
    late = [(0, 100.0), (10, 99.0), (5 * 60 + 10, 101.2)]
    assert resolved(late) == replay.UNRESOLVED


def test_no_ties_returns_an_empty_frame_with_the_columns():
    bars = five_minute_bars([0.0, 1.2, 0.0, 0.0, 0.0])
    got = replay.resolve(tape([(0, 100.0)]), replay.tied(bars, leg(), GC, B), GC, B)
    assert got.empty
    assert {"first", "gap_ns"} <= set(got.columns)


# --- the summary ----------------------------------------------------------

def test_unresolved_legs_stay_at_the_lower_bound():
    """Dropping them would select the legs the tape happened to be able to
    answer, which is a different population again."""
    frame = pd.DataFrame({
        "first": [replay.TARGET_FIRST, replay.STOP_FIRST, replay.UNRESOLVED],
        "gap_ns": [1.0, 2.0, float("nan")],
    })
    got = replay.summarize(frame, B, n=100)
    assert (got["target_ticks"], got["stop_ticks"]) == (B.target, B.stop)
    assert got["ties"] == 3
    assert (got["target_first"], got["stop_first"], got["unresolved"]) == (1, 1, 1)
    assert got["tie_rate"] == pytest.approx(0.03)


# --- the mirrored line ----------------------------------------------------

def test_cell_scale_matches_m1_sweep():
    """`replay.cell_atr_ticks` mirrors an inline expression in
    `m1_sweep.month_counts`. Mirrored code is what this repo has twice paid
    for, so the two are asserted equal rather than assumed so."""
    sub = pd.DataFrame({"atr_bp": [8.0, 9.0, 12.0], "close": [3300.0, 3310.0, 3290.0]})
    m1_sweeps_line = (sub["atr_bp"].median() / 1e4) * sub["close"].median() / GC.tick
    assert replay.cell_atr_ticks(sub, GC) == pytest.approx(float(m1_sweeps_line))


def test_summarize_reports_ticks_under_a_tick_name():
    """`Bracket` holds barriers already scaled by the cell's ATR. Reporting
    them as `target_atr` would collide with the multiple the caller groups by
    -- and a groupby on the wrong one silently aggregates nothing, because a
    tick-denominated barrier is different in every cell."""
    assert "target_atr" not in replay.summarize(pd.DataFrame(
        {"first": [], "gap_ns": []}), B, n=0)


def test_the_session_fixture_is_the_one_the_bars_claim():
    assert five_minute_bars(BOTH)["session"].unique().tolist() == [SESSION]


# --------------------------------------------------------------------------
# M4b -- the path-ordering measurement. precommit §11.
# --------------------------------------------------------------------------

def test_path_bars_finds_the_bar_each_extreme_lives_in():
    # bar 1 is the high (favourable for a long), bar 2 the low.
    bars = bars_at([0, 5, 10, 15, 20],
                   [ENTRY, ENTRY + 1.0, ENTRY - 1.0, ENTRY, ENTRY],
                   ranges=[0.0, 0.4, 0.4, 0.0, 0.0])
    ex = excursions(bars, leg(), GC, horizon=B.horizon)
    got = replay.path_bars(ex)
    assert got["mfe_bar"].iloc[0] == 0
    assert got["mae_bar"].iloc[0] == 1
    assert not got["unorderable"].iloc[0]


def test_one_bar_holding_both_extremes_is_unorderable():
    """The population M4b exists to size: bar data has no sequence to offer."""
    bars = five_minute_bars(BOTH)
    got = replay.path_bars(excursions(bars, leg(), GC, horizon=B.horizon))
    assert got["mfe_bar"].iloc[0] == got["mae_bar"].iloc[0]
    assert got["unorderable"].iloc[0]


def test_an_invalid_leg_is_never_unorderable():
    """`excursions` marks a leg invalid when its session ends inside the horizon.
    Counting one of those would be a path ordering for a trade never offered."""
    bars = bars_at([0, 5, 10, 15, 20], [ENTRY] * 5, ranges=BOTH,
                   session=[SESSION, SESSION, NEXT, NEXT, NEXT])
    got = replay.path_bars(excursions(bars, leg(), GC, horizon=B.horizon))
    assert not got["unorderable"].any()


def test_side_is_a_relabelling_not_a_second_observation():
    """⚠️ The artefact this module has now produced twice. A long and a short on
    the same bar read the SAME two prices -- the high is the long's favourable
    extreme and the short's adverse one -- so `unorderable` cannot differ by
    side, and pooling the two would force the ordering to 50/50."""
    bars = five_minute_bars(BOTH)
    lo = replay.path_bars(excursions(bars, leg(1), GC, horizon=B.horizon))
    sh = replay.path_bars(excursions(bars, leg(-1), GC, horizon=B.horizon))
    assert lo["unorderable"].tolist() == sh["unorderable"].tolist()
    # The long's favourable bar is the short's adverse one, and vice versa.
    assert lo["mfe_bar"].tolist() == sh["mae_bar"].tolist()
    assert lo["mae_bar"].tolist() == sh["mfe_bar"].tolist()


def path_resolved(prints, side=1):
    bars = five_minute_bars(BOTH)
    ex = excursions(bars, leg(side), GC, horizon=B.horizon)
    un = replay.path_bars(ex)
    un = un[un["unorderable"]].copy()
    un["bar"] = OPEN + pd.Timedelta(minutes=5)
    un["entry"] = ENTRY
    un["side"] = side
    return int(replay.resolve_path(tape(prints), un, GC)["first"].iloc[0])


def test_the_tape_orders_the_two_extremes():
    # high at +10s, low at +20s -> for a long, MFE first.
    assert path_resolved([(0, 100.0), (10, 101.5), (20, 98.5)]) == replay.MFE_FIRST
    assert path_resolved([(0, 100.0), (10, 98.5), (20, 101.5)]) == replay.MAE_FIRST


def test_a_short_reads_the_same_prints_the_other_way_round():
    """The same tape, the same two prices, the opposite answer -- which is what
    makes `side` a relabelling rather than evidence."""
    prints = [(0, 100.0), (10, 101.5), (20, 98.5)]
    assert path_resolved(prints, side=1) == replay.MFE_FIRST
    assert path_resolved(prints, side=-1) == replay.MAE_FIRST


def test_both_extremes_in_one_nanosecond_is_unresolved():
    assert path_resolved([(10, 101.5), (10, 98.5)]) == replay.UNRESOLVED


def test_path_summary_reports_the_ordering_once_not_per_side():
    """A per-side table would report one measurement twice; a pooled ordering
    would be forced to 50/50. `path_summary` takes the long leg's view."""
    t = pd.DataFrame([
        {"side": 1, "horizon": 15, "legs": 100, "unorderable": 10,
         "mfe_first": 7, "mae_first": 3, "tape_unresolved": 0},
        {"side": -1, "horizon": 15, "legs": 100, "unorderable": 10,
         "mfe_first": 3, "mae_first": 7, "tape_unresolved": 0},
    ])
    got = replay.path_summary(t)
    assert len(got) == 1, "one row per horizon, not per (horizon, side)"
    assert got["legs"].iloc[0] == 100, "sides are not summed into the denominator"
    assert got["high_first"].iloc[0] == 7
    assert got["unorderable_rate"].iloc[0] == pytest.approx(0.10)
    assert got["high_first_share"].iloc[0] == pytest.approx(0.70)

