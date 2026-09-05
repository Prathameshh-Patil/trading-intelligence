"""The rate-power arithmetic, checked against its own inverse and its edges.

`mde_ticks` and `n_for` are covered by their algebra being one line each; what
needs testing is the proportion pair, because the noise on a rate is a
different quantity from the noise on a mean and using the wrong one produces a
number that reads as perfectly reasonable.
"""

import pytest

from horizon import mde_rate, n_for_rate


def test_mde_rate_and_n_for_rate_are_inverses() -> None:
    # Round trip: the lift 46 signals can detect, fed back, asks for ~46.
    p1 = mde_rate(0.155, 46)
    assert n_for_rate(0.155, p1) == pytest.approx(46, abs=1)


def test_more_signals_detect_a_smaller_lift() -> None:
    lifts = [mde_rate(0.155, n) - 0.155 for n in (30, 100, 500, 2000)]
    assert lifts == sorted(lifts, reverse=True)


def test_the_iteration_beats_the_fixed_variance_shortcut() -> None:
    # The shortcut holds the variance at p0. Since p1 > p0 in this range it
    # understates the lift needed -- and it errs toward flattering the
    # strategy, which is the direction that must not be free.
    from horizon import Z, _se

    p0, n = 0.155, 46
    assert mde_rate(p0, n) > p0 + Z * _se(p0, n)


def test_a_rate_that_cannot_be_beaten_saturates_rather_than_exceeding_one() -> None:
    assert mde_rate(0.9, 5) == 1.0


def test_a_lift_that_is_not_a_lift_is_refused() -> None:
    with pytest.raises(ValueError, match="must exceed"):
        n_for_rate(0.2, 0.2)
