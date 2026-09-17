"""S13's contract, tested against the ways a lane can violate it silently.

The failure this file exists to prevent is not a crash. It is a lane adding or
renaming a column, the other lane never learning, and a scorer reading a
NaN it was never told about. So `require` is tested on what it *names*, not
merely on what it rejects -- an error that says "bad frame" costs an hour
that an error saying "r_hat_60_bp" does not.
"""

from __future__ import annotations

import pandas as pd
import pytest

from features import frame


def full() -> pd.DataFrame:
    return pd.DataFrame({c: [0.0] for c in frame.FEATURES})


def test_a_complete_frame_passes():
    frame.require(full())


def test_a_missing_column_is_named_not_just_rejected():
    df = full().drop(columns=["r_hat_60_bp"])
    with pytest.raises(ValueError, match="r_hat_60_bp"):
        frame.require(df)


def test_an_extra_column_is_rejected():
    # A lane that adds a column has changed the seam without saying so.
    df = full().assign(ofi_z=[0.0])
    with pytest.raises(ValueError, match="ofi_z"):
        frame.require(df)


@pytest.mark.parametrize("bad", ["stop_ticks", "target_pips"])
def test_ticks_and_pips_are_refused_by_name(bad: str):
    # The one unit rule the whole spec rests on, enforced mechanically rather
    # than by review. USD/oz and basis points only -- a pip is a broker's
    # opinion. Caught as an extra column, and the message names it.
    with pytest.raises(ValueError, match=bad):
        frame.require(full().assign(**{bad: [0.0]}))


def test_the_seam_has_no_duplicate_columns():
    # A duplicate in FEATURES makes `require` pass a frame that is missing one
    # real column, because set() collapses it. Cheap to check, silent if not.
    assert len(frame.FEATURES) == len(set(frame.FEATURES))


def test_no_seam_column_is_named_in_ticks_or_pips():
    # The unit rule applied to the seam itself, not just to what passes through
    # it. Stops the rule being broken by whoever next edits FEATURES.
    assert not [c for c in frame.FEATURES if "tick" in c or "pip" in c]
