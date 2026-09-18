"""The constraint that defines Track C, enforced by the build rather than by care.

**NO CVD, NO ORDER FLOW, NO OFI, NO HAWKES, NO FOOTPRINT, NO TICK VOLUME
PROFILE, NO SENTIMENT, NO NEWS CONTENT.** Every Track C input must be a
closed-form quantity of OHLC bars (plus the measured spread). The rule is easy
to state, easy to agree with, and easy to break by importing one convenient
helper eight weeks from now -- so it is a test, and the test reads the actual
import graph rather than a list somebody maintains.

WHY THE IDENTIFIER SCAN EXISTS ALONGSIDE THE IMPORT SCAN. `features/frame.py`
carries `cvd_z` as a column name; a module could read it off a frame without
importing anything forbidden. The identifier scan catches that. It deliberately
ignores this file, comments and docstrings -- the words have to appear in the
code, not in the prose explaining why they may not.

WHAT IS ALLOWED AND MIGHT LOOK FORBIDDEN. `spot.py`'s `ticks` column is a
quote-update COUNT, not traded volume; `instruments.XAUUSD.has_flow` is False
and `require_flow` raises if anything tries. Two Track C strategies use that
count as a declared proxy (S3's VWAP weighting, S4's liquidity filter) and both
say so in their docstrings and in every report header.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TRACK_C = Path(__file__).resolve().parent.parent / "track_c"

# Modules Track C may not import, directly or via `from X import Y`.
FORBIDDEN_MODULES = frozenset({
    "features.orderflow", "orderflow", "compute_delta_cvd", "m3_profile",
    "classifier", "regimes", "m1_sweep", "m2_magnitude", "s1", "stage1",
    "strategies",           # the repo-level Track A module, not `track_c.strategies`
})

# Identifiers that cannot appear in Track C code whatever their source.
FORBIDDEN_NAMES = frozenset({
    "cvd", "cvd_z", "cvd_slope", "delta_cvd", "ofi", "ofi_z", "hawkes",
    "footprint", "aggressor", "sentiment", "volume_profile", "lvn", "hvn",
})

SOURCES = sorted(TRACK_C.rglob("*.py"))


def test_there_are_sources_to_scan() -> None:
    """A scan over zero files passes vacuously, which is the one way this
    whole test file could quietly stop protecting anything."""
    assert len(SOURCES) >= 10


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_tape_imports(path: Path) -> None:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            root = node.module or ""
            names = [root] + [f"{root}.{a.name}" for a in node.names]
        else:
            continue
        for name in names:
            assert name not in FORBIDDEN_MODULES, (
                f"{path.name} imports {name}: Track C is forbidden from reading the tape, "
                "and spot XAUUSD has no tape to read")


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_tape_identifiers(path: Path) -> None:
    """Names, attributes and string subscripts -- the three ways a column is read."""
    tree = ast.parse(path.read_text())
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            seen.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            seen.add(node.attr.lower())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            seen.add(node.value.lower())
    banned = seen & FORBIDDEN_NAMES
    assert not banned, f"{path.name} refers to {sorted(banned)}, which spot XAUUSD does not have"


def test_the_guard_would_catch_a_violation() -> None:
    """The scan is only worth having if it fails on a file that breaks the rule.

    A test that only ever passes is a test nobody has seen fail, and an AST
    walk that silently matched nothing would look exactly like a clean
    codebase. So: hand it a violating module and require it to object.
    """
    tree = ast.parse("import compute_delta_cvd\nx = row['cvd_z']\n")
    imports = {n.name for node in ast.walk(tree) if isinstance(node, ast.Import)
               for n in node.names}
    strings = {n.value.lower() for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert imports & FORBIDDEN_MODULES
    assert strings & FORBIDDEN_NAMES
