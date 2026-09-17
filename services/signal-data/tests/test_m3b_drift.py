"""M3b's statistic and its windowing, tested against the ways it can lie.

Written against failure modes rather than the happy path, following
`test_m1_sweep.py` and `test_m3_ev.py`. The shapes that matter here:

  * the pooled mean NOT removed, so a period's drift reads as every phase's --
    which is exactly the null `M3_CLOCK.md` §6 said M3 did not have,
  * a window spanning a weekend or a session break priced as a quiet 30
    minutes, because `resample_bars` drops empty bars,
  * windows sharing bars, which inflates n about sixfold and manufactures
    significance out of autocorrelation,
  * and no power at all -- a test that can never find a drift would "confirm"
    §12's prediction by being broken.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import bars_at

import m3b_drift as m3b
from features.portable import PHASES
from instruments import GC

N = 1000


def w(**drift_by_phase: float) -> pd.DataFrame:
    """`n` disjoint windows per phase, with a known mean and unit spread.

    Returns alternate around each phase's mean, so the mean is exact by
    construction and the test never depends on a seed.
    """
    rows = []
    for p in PHASES:
        mu = drift_by_phase.get(p.replace("-", "_"), 0.0)
        swing = np.where(np.arange(N) % 2 == 0, 1.0, -1.0)
        rows.append(pd.DataFrame({"phase": p, "ret_bp": mu + swing, "cost_bp": 0.45}))
    return pd.concat(rows, ignore_index=True)


def test_a_flat_tape_has_no_residual_and_clears_nothing() -> None:
    t = m3b.drift(w())
    assert t["resid_bp"].abs().max() == pytest.approx(0.0, abs=1e-12)
    assert not t["clears"].any()


def test_a_drift_shared_by_every_phase_is_the_null_and_survives_none_of_it() -> None:
    """The null M3 did not have, and the reason this experiment exists.

    A period's drift -- gold's 84% -- lands on every phase at once. Subtracting
    the POOLED mean is what makes that a period claim rather than six phase
    claims, and without it every phase would read +5 bp and "clear" easily.
    """
    t = m3b.drift(w(**{p.replace("-", "_"): 5.0 for p in PHASES}))
    assert t["mean_bp"].min() == pytest.approx(5.0), "the drift is really there"
    assert t["resid_bp"].abs().max() == pytest.approx(0.0, abs=1e-12), "and is not a phase's"
    assert not t["clears"].any()


def test_a_drift_in_one_phase_alone_is_found() -> None:
    """Power. A test that can never fire would 'confirm' §12 by being broken."""
    t = m3b.drift(w(London_NY=2.0))
    assert t.loc["London-NY", "clears"], "the injected phase must clear"
    assert t.drop(index="London-NY")["clears"].sum() == 0, "and no other may"
    assert t["resid_bp"].idxmax() == "London-NY"


def test_a_window_never_spans_a_gap_in_the_bars() -> None:
    """`resample_bars` drops empty bars, so six bars is not always 30 minutes.

    Two clean windows exist here (0..30 and 30..60). The bar at 65 is followed
    by a hole, so the window starting there ends an hour later in bar-count
    terms and must be dropped rather than priced as a half hour.
    """
    minutes = list(range(0, 65, 5)) + [120, 125, 130, 135, 140, 145, 150]
    bars = bars_at(minutes, [100.0] * len(minutes))
    got = m3b.windows(bars, GC)
    spans = got.index.to_series().diff().dropna()
    assert len(got) == 2, f"expected the two whole windows, got {len(got)}"
    assert (spans == pd.Timedelta(minutes=30)).all()


def test_windows_are_disjoint_and_never_share_a_bar() -> None:
    minutes = list(range(0, 24 * 5, 5))
    bars = bars_at(minutes, [100.0 + i for i in range(len(minutes))])
    got = m3b.windows(bars, GC)
    gaps = got.index.to_series().diff().dropna()
    assert (gaps >= pd.Timedelta(minutes=30)).all(), "windows overlap"


def test_a_rising_tape_reads_positive_and_a_falling_one_negative() -> None:
    """The sign convention, pinned. A drift study that flips sign is worthless."""
    minutes = list(range(0, 24 * 5, 5))
    up = m3b.windows(bars_at(minutes, [100.0 * 1.001**i for i in range(len(minutes))]), GC)
    down = m3b.windows(bars_at(minutes, [100.0 * 0.999**i for i in range(len(minutes))]), GC)
    assert (up["ret_bp"] > 0).all()
    assert (down["ret_bp"] < 0).all()
