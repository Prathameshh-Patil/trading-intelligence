"""§7's walk-forward, tested on the leaks it exists to close.

`mathematical.md` §14 says "avoid random train/test splits because they leak
time-series information" and then specifies a rolling split. **A rolling split
leaks too**, and the leak it does not mention is the larger one here: a
90-minute label opened at 15:00 on the last training day resolves inside the
validation fold. Purging closes it; nothing in §14 asks for purging.

So what gets tested hardest is not that folds have the right shape -- it is
that a sample whose LABEL crosses a boundary is gone from training, and that
deleting the purge turns a test red rather than quietly improving every score.
"""

from __future__ import annotations

from itertools import pairwise

import pandas as pd
import pytest

import tuning

HOLDOUT = pd.Timestamp("2025-01-01", tz="UTC")


def idx(start: str, months: int) -> pd.DatetimeIndex:
    """One bar every 30 minutes for `months` months -- dense enough that a
    boundary falls between bars rather than on one."""
    return pd.date_range(start, periods=months * 30 * 48, freq="30min", tz="UTC")


# ---------------------------------------------------------------- fold shape

def test_folds_are_train_then_validate_never_the_reverse() -> None:
    for tr, va in tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT):
        assert tr.max() < va.min()


def test_validation_windows_do_not_overlap_each_other() -> None:
    # Overlapping validation is the same sample scored twice, which makes a
    # lucky month look like two independent confirmations.
    fs = tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT, roll_m=6, val_m=6)
    for (_, a), (_, b) in pairwise(fs):
        assert a.max() < b.min()


def test_the_holdout_never_appears_in_any_fold() -> None:
    for tr, va in tuning.folds(idx("2020-01-01", 72), holdout_start=HOLDOUT):
        assert tr.max() < HOLDOUT
        assert va.max() < HOLDOUT


def test_too_little_history_yields_no_folds_rather_than_a_degenerate_one() -> None:
    # 12 months cannot hold a 24-month train window. Returning one short fold
    # would be a walk-forward in name only.
    assert tuning.folds(idx("2024-01-01", 12), holdout_start=HOLDOUT) == []


# -------------------------------------------------------------------- purge

def test_a_label_crossing_the_boundary_is_purged_from_training() -> None:
    # THE LEAK §14 DOES NOT MENTION. With a 90-minute label, the last 90
    # minutes of training resolve inside validation.
    tr, va = tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                          label_minutes=90, embargo_days=0)[0]
    assert tr.max() + pd.Timedelta(minutes=90) <= va.min()


def test_removing_the_purge_would_admit_those_samples() -> None:
    # The mutation test. If purging is a no-op, this comparison is equal and
    # the guard above is passing for the wrong reason.
    purged, _ = tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                             label_minutes=90, embargo_days=0)[0]
    none, _ = tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                           label_minutes=0, embargo_days=0)[0]
    assert len(purged) < len(none)


def test_a_longer_label_purges_strictly_more() -> None:
    def n(label: int) -> int:
        return len(tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                                label_minutes=label, embargo_days=0)[0][0])

    assert n(0) > n(90) > n(600)


# ------------------------------------------------------------------ embargo

def test_the_embargo_removes_a_further_day_beyond_the_purge() -> None:
    with_e, va = tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                              label_minutes=90, embargo_days=1)[0]
    assert with_e.max() + pd.Timedelta(days=1) <= va.min()


def test_removing_the_embargo_would_admit_those_samples() -> None:
    a = len(tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                         label_minutes=90, embargo_days=1)[0][0])
    b = len(tuning.folds(idx("2020-01-01", 60), holdout_start=HOLDOUT,
                         label_minutes=90, embargo_days=0)[0][0])
    assert a < b


# ------------------------------------------------------------ trial counter

def test_the_counter_records_every_configuration() -> None:
    c = tuning.Trials()
    for _ in range(7):
        c.record()
    assert c.count == 7


def test_the_counter_cannot_be_reset_by_the_caller() -> None:
    # The haircut is only honest if the count is. A counter the summary writer
    # can zero is not a guard, it is a formality.
    c = tuning.Trials()
    c.record()
    with pytest.raises(AttributeError):
        c.count = 0  # type: ignore[misc]
    assert c.count == 1


def test_the_counter_has_no_reset_or_decrement() -> None:
    assert not [m for m in dir(tuning.Trials) if "reset" in m or "clear" in m or "dec" in m]


# ---------------------------------------------------------- deflated Sharpe

def test_deflated_sharpe_falls_as_trials_rise() -> None:
    # SR HERE IS PER OBSERVATION, NOT ANNUALISED. 1.2 per trade over 500
    # trades is a t-stat of 20; the CDF saturates at 1.0 and the comparison
    # becomes 1.0 > 1.0, which is vacuously false. Realistic per-trade
    # Sharpe is 0.05-0.15, and at 0.10 the haircut does visible work:
    # 0.908 at one configuration against 0.298 at two hundred.
    assert tuning.deflated_sharpe(0.10, n_trials=1, n_obs=500) > \
        tuning.deflated_sharpe(0.10, n_trials=200, n_obs=500)


def test_one_trial_still_haircuts_something() -> None:
    # Even a single configuration was selected by someone. A DSR that equals
    # the raw Sharpe's p-value at K=1 is not deflating anything.
    assert 0.0 < tuning.deflated_sharpe(0.10, n_trials=1, n_obs=500) < 1.0


def test_a_sharpe_below_the_expected_maximum_under_the_null_deflates_below_half() -> None:
    # 200 configurations will produce a Sharpe near 1.0 by chance alone at
    # this sample size. Reporting that as a result is what the haircut stops.
    assert tuning.deflated_sharpe(0.02, n_trials=200, n_obs=500) < 0.5


def test_more_observations_raise_confidence_at_the_same_sharpe() -> None:
    assert tuning.deflated_sharpe(0.10, n_trials=10, n_obs=2000) > \
        tuning.deflated_sharpe(0.10, n_trials=10, n_obs=200)


def test_expected_max_sharpe_grows_with_trials_and_shrinks_with_sample() -> None:
    assert tuning.expected_max_sharpe(n_trials=100, n_obs=500) > \
        tuning.expected_max_sharpe(n_trials=2, n_obs=500)
    assert tuning.expected_max_sharpe(n_trials=100, n_obs=5000) < \
        tuning.expected_max_sharpe(n_trials=100, n_obs=500)


def test_the_haircut_is_not_optional_at_zero_trials() -> None:
    # Zero configurations means nothing was searched, which never happens and
    # would silently disable the haircut if it were allowed.
    with pytest.raises(ValueError, match="n_trials"):
        tuning.deflated_sharpe(0.10, n_trials=0, n_obs=500)


def test_it_refuses_a_sample_too_small_to_estimate_a_sharpe() -> None:
    with pytest.raises(ValueError, match="n_obs"):
        tuning.deflated_sharpe(0.10, n_trials=10, n_obs=1)


# ------------------------------------------------------- monotonicity guard

def test_a_monotone_profile_passes() -> None:
    assert tuning.is_monotone([1.0, 2.0, 3.0, 4.0])
    assert tuning.is_monotone([4.0, 3.0, 2.0, 1.0])


def test_a_jagged_profile_fails() -> None:
    # §7.3: a parameter whose profile is jagged is being fit to noise, and
    # that is a finding rather than a setting.
    assert not tuning.is_monotone([1.0, 5.0, 2.0, 6.0])


def test_a_single_dip_costs_two_reversals_not_one() -> None:
    # Worth pinning because it is the arithmetic everyone gets wrong when
    # setting the allowance: one excursion is TWO sign changes -- down, then
    # back up. An allowance of 1 forbids any dip at all.
    dip = [1.0, 2.0, 1.9, 3.0, 4.0]
    assert not tuning.is_monotone(dip, max_reversals=1)
    assert tuning.is_monotone(dip, max_reversals=2)


def test_a_monotone_profile_with_a_flat_step_still_passes() -> None:
    # A parameter with no effect over part of its range is flat, not jagged.
    # Equal neighbours are dropped rather than counted as a zero-sign change.
    assert tuning.is_monotone([1.0, 2.0, 2.0, 3.0])


def test_the_d_profile_measured_on_2026_09_18_is_not_monotone() -> None:
    # The exemption in design §7.3, pinned. EV against D dips to a minimum at
    # $4.00 and rises, because §10's R = max(2.5D, $10.00) makes the target
    # FLOOR bind below $4.00. The dip is the spec's own formula, so applying
    # this guard to D would reject the construction rather than find noise.
    assert not tuning.is_monotone([7.03, 6.01, 5.33, 3.62, 5.00])
    assert "d_usd" in tuning.MONOTONICITY_EXEMPT
