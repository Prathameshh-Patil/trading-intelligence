"""Every Track C parameter, read from `config/track_c.toml` and checked on load.

WHY A FILE AND NOT MODULE CONSTANTS. A parameter change becomes a reviewable
diff in one place, and the annotation that justifies each number sits beside
it. `fsm.py` holds §13's numbers as module constants and that is correct for
§13 -- those are the spec's, shared with Track B. Track C's are Track C's.

WHY DOTTED STRINGS AND NOT A DATACLASS PER SECTION. Eight frozen dataclasses
mirroring eight TOML tables is 150 lines of scaffolding whose only job is to
restate the file. `require()` does the thing the dataclasses were wanted for --
it fails at load if a key the engine reads is missing, rather than at bar
183,000 of a walk-forward.

⚠️ THE RESTATEMENT TRAP, AND WHAT GUARDS IT. Four numbers in the TOML are
already defined in `fsm.py` and `e3_cost.py`: the stop bounds, the target floor
and the target cap. A restatement that drifts is two files quietly disagreeing
about the same quantity -- the failure `spot.py`'s docstring records. So
`require()` asserts the TOML equals the modules, and the TOML is where the
provenance comment lives, not where the number is decided.
"""

from __future__ import annotations

import tomllib
from datetime import time
from pathlib import Path
from typing import Any

import e3_cost
import fsm

CONFIG = Path(__file__).resolve().parent.parent / "config" / "track_c.toml"

STRATEGIES: tuple[str, ...] = ("s1", "s2", "s3", "s4")

# Keys the engine reads. Listed rather than discovered, so deleting one from
# the TOML is a load-time failure and not a KeyError three hours into a run.
REQUIRED: tuple[str, ...] = (
    "data.bar", "data.audit_bar", "data.symbol",
    "risk.equity_usd", "risk.risk_fraction", "risk.value_per_lot",
    "risk.d_min_usd", "risk.d_max_usd", "risk.r_multiple", "risk.be_at_r",
    "risk.max_trades_per_day", "risk.max_losses_per_day",
    "risk.daily_loss_cap_usd", "risk.dll_firm_usd", "risk.limit_life_s",
    "cost.slippage_spread_frac", "cost.slippage_margin", "cost.news_spread_mult",
    "cost.max_slippage_share",
    "news.internal_lockout_min", "news.hard_lockout_min",
    "regime.atr_window", "regime.atr_min_bars", "regime.yz_fast_bars",
    "regime.yz_slow_bars", "regime.hurst_window_bars", "regime.hurst_step_bars",
    "regime.hurst_agree_tol", "regime.pct_lookback_bars",
    "session.asian_start", "session.asian_end",
    "gates.c1_min_funnel_events", "gates.c2_min_ev_r", "gates.c3_min_pf",
    "gates.c4_min_dsr", "gates.c5_max_dd", "gates.c6_min_window_share",
    "gates.c7_worst_day_r",
    "walkforward.train_m", "walkforward.val_m", "walkforward.roll_m",
    "walkforward.holdout_m", "walkforward.label_minutes", "walkforward.embargo_days",
)


def load(path: Path = CONFIG) -> dict[str, Any]:
    """Parse and validate. The only way Track C gets its numbers."""
    with path.open("rb") as fh:
        cfg = tomllib.load(fh)
    require(cfg)
    return cfg


def get(cfg: dict[str, Any], dotted: str) -> Any:
    """`get(cfg, "risk.d_min_usd")`. Missing keys name themselves."""
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"track_c.toml has no {dotted!r}")
        node = node[part]
    return node


def f(cfg: dict[str, Any], dotted: str) -> float:
    return float(get(cfg, dotted))


def i(cfg: dict[str, Any], dotted: str) -> int:
    """An int, and it must already BE one.

    `int(2.7)` silently becomes 2, and a lookback of 2 bars where 2880 was
    meant looks like a quiet strategy rather than a misread config.
    """
    v = get(cfg, dotted)
    if not isinstance(v, int) or isinstance(v, bool):
        raise TypeError(f"{dotted} must be an integer, got {v!r}")
    return v


def windows(cfg: dict[str, Any], strategy: str) -> tuple[tuple[time, time], ...]:
    """A strategy's trading windows as New York local clock times.

    Half-open `[start, end)`, the convention `features/structure.py` sets and
    the reason a 15:30 bar is not counted in two windows at once.
    """
    return tuple((clock(a), clock(b)) for a, b in get(cfg, f"{strategy}.windows"))


def clock(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def require(cfg: dict[str, Any]) -> None:
    """Every key the engine reads exists, every strategy table exists, and the
    four restated numbers still equal the modules that define them."""
    for key in REQUIRED:
        get(cfg, key)
    for s in STRATEGIES:
        windows(cfg, s)          # parses, so a malformed clock fails here
        get(cfg, f"{s}.entry_pullback_atr")
    _agree(cfg, "risk.d_min_usd", fsm.D_MIN_USD, "fsm.D_MIN_USD")
    _agree(cfg, "risk.d_max_usd", fsm.D_MAX_USD, "fsm.D_MAX_USD")
    _agree(cfg, "risk.risk_fraction", fsm.DEFAULT_RISK_FRACTION, "fsm.DEFAULT_RISK_FRACTION")
    _agree(cfg, "cost.max_slippage_share", e3_cost.MAX_SLIPPAGE_SHARE, "e3_cost.MAX_SLIPPAGE_SHARE")
    if f(cfg, "risk.dll_firm_usd") > 0:
        # §11's real rule. With no firm chosen the TOML carries 0 and the
        # placeholder $1,100 stands -- which every report header must say.
        cap = min(f(cfg, "risk.daily_loss_cap_usd"), 0.75 * f(cfg, "risk.dll_firm_usd"))
        cfg["risk"]["daily_loss_cap_usd"] = cap


def _agree(cfg: dict[str, Any], dotted: str, value: float, name: str) -> None:
    if f(cfg, dotted) != value:
        raise ValueError(
            f"track_c.toml {dotted} = {f(cfg, dotted)} disagrees with {name} = {value}. "
            "One quantity, one definition: change the module, not the restatement.")


def target_usd(d_usd: float, cfg: dict[str, Any]) -> float:
    """§10's `R = clip(2.5D, $10, $15)`, off `e3_cost`'s floor and cap."""
    return min(max(f(cfg, "risk.r_multiple") * d_usd, e3_cost.TARGET_FLOOR_USD),
               e3_cost.TARGET_CAP_USD)


def opt_i(cfg: dict[str, Any], dotted: str) -> int | None:
    """An optional integer -- `None` where the key is absent.

    Exactly one parameter is optional: S3's time stop. The other three
    strategies trade an event, and an event that has not resolved is still an
    event (`strategies/s3.py` says why). So "no key" means "no time stop"
    rather than a default someone has to remember.
    """
    try:
        return i(cfg, dotted)
    except KeyError:
        return None
