"""One markdown report per run. **Gate table first, assumptions in the header.**

THE ORDER IS THE ARGUMENT. A reader who stops after the first screen should
have seen the pass/fail table and the assumptions it rests on -- not an equity
curve. `Quant_trading/reports/` keeps that project honest across months by
putting the contract at the top, and this is that idea with this repo's
assumption header bolted onto it.

THE ASSUMPTION BLOCK IS NOT DECORATION. Six of Track C's inputs are assumptions
rather than measurements, and a number quoted without them is a number that
will be believed more than it deserves. They are printed in full, every run,
even when nothing changed -- a header nobody has to remember to add is a header
that is still there in month four.

`to_markdown` is not used: it needs `tabulate`, which is not a dependency of
this service, and a nine-line formatter is cheaper than a dependency added for
pipe characters.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

import tuning
from track_c import config, fills, funnel, strategies

REPORTS = Path(__file__).resolve().parent.parent / "analysis" / "track_c"


def assumptions(cfg: dict[str, Any]) -> list[str]:
    """Every place a Track C number rests on something unmeasured."""
    return [
        (f"**Fills are unresolved at {config.get(cfg, 'data.bar')} bars.** §9 gives the limit a "
         f"{config.f(cfg, 'risk.limit_life_s'):.0f}-second life; a bar this size cannot say "
         "whether it was touched inside that life. Every number below is an UPPER BOUND until "
         f"tick replay exists (`fills.resolves_limit` = {fills.resolves_limit(cfg)})."),
        ("**Slippage is assumed, not measured.** No live trade journal exists. The model is "
         f"{config.f(cfg, 'cost.slippage_spread_frac')} x "
         f"{config.f(cfg, 'cost.slippage_margin')} x the measured spread, charged on market "
         "exits only."),
        ("**Session VWAP is weighted by quote-update count, not volume.** Spot XAUUSD has no "
         "tape. S3 is the only strategy that depends on this."),
        ("**S4's liquidity filter is the same proxy** -- quote-update percentile, which measures "
         "repricing activity rather than traded size."),
        ("**S2's reclaim is weaker than §9's.** §9 requires the reclaim within 30 seconds on "
         f"ticks; this requires it within {config.i(cfg, 's2.reclaim_bars')} bars."),
        (f"**The daily loss cap of ${config.f(cfg, 'risk.daily_loss_cap_usd'):,.0f} is a "
         "PLACEHOLDER.** §11's rule is min($1100, 0.75 x DLL_firm) and no firm has been chosen."),
        (f"**Hurst is recomputed every {config.i(cfg, 'regime.hurst_step_bars')} bars and held** "
         f"over a {config.i(cfg, 'regime.hurst_window_bars')}-bar window; it is stale by up to "
         "that step and never early."),
    ]


def render(*, res: Any, cfg: dict[str, Any], per_strategy: dict[str, dict[str, float]],
           gates: pd.DataFrame, windows: dict[str, list[float]],
           holdout: dict[str, dict[str, float]], trials: tuning.Trials,
           span: tuple[pd.Timestamp, pd.Timestamp], independent: int) -> str:
    """The whole report, as one markdown string."""
    lines = [
        "# Track C -- run report",
        "",
        (f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. "
         f"Bars: {span[0]:%Y-%m-%d} to {span[1]:%Y-%m-%d}, {res.bars:,} at "
         f"{config.get(cfg, 'data.bar')}. Config: `config/track_c.toml` "
         f"(committed {config.get(cfg, 'meta.committed')})."),
        "",
        "## Assumptions this run rests on",
        "",
        *[f"{n}. {a}" for n, a in enumerate(assumptions(cfg), 1)],
        "",
        "## 1. Gates -- §7's contract, committed before the first run",
        "",
        _md(gates),
        "",
        "### Verdict",
        "",
        *_verdicts(gates),
        "",
        "## 2. Attrition -- which condition refused what",
        "",
        ("Read this before the numbers above. A stage that refuses everything means the strategy "
         "is untestable rather than untested; a late stage still holding thousands of bars means "
         "the conditions above it condition on nothing."),
        "",
        _md(funnel.table(res.counts, strategies.CONDITIONS)),
        "",
        "## 3. Layer-4 vetoes -- suggestions the risk layer refused",
        "",
        _md(_vetoes(res.vetoes)),
        "",
        "## 4. Metrics per strategy (R-based, net of modelled cost)",
        "",
        _md(pd.DataFrame(per_strategy).T.reset_index(names="strategy")),
        "",
        "## 5. Out-of-sample windows (total R each)",
        "",
        (f"{len(next(iter(windows.values()), []))} windows, of which **{independent} are "
         "independent** -- §14's 6-month window rolled 3 months overlaps by half, so a good "
         "quarter is scored twice and the deflated Sharpe may only be given the independent "
         "count."),
        "",
        _md(pd.DataFrame(windows).T.reset_index(names="strategy")),
        "",
        "## 6. Holdout -- opened once",
        "",
        _md(pd.DataFrame(holdout).T.reset_index(names="strategy")),
        "",
        "## 7. Trial count",
        "",
        (f"`tuning.Trials` has recorded **{trials.count}** configuration(s) across the "
         "programme. The counter does not reset. A Sharpe quoted without it is not a result."),
        "",
    ]
    return "\n".join(lines)


def _verdicts(gates: pd.DataFrame) -> list[str]:
    """KEEP or KILL per strategy, and the gates that decided it.

    **A failing strategy is killed and the reason is printed. It is not quietly
    re-tuned** -- `TRACK_C_ENGINE.md` §10.4, and the whole point of committing
    the gate table before the run.
    """
    out = []
    for name, g in gates.groupby("strategy"):
        failed = list(g[~g["pass"]]["gate"])
        if failed:
            out.append(f"- **{name}: KILL** -- failed {', '.join(failed)}. No re-tune follows.")
        else:
            out.append(f"- **{name}: KEEP** -- cleared all {len(g)} gates.")
    return out


def _vetoes(vetoes: Counter[tuple[str, str]]) -> pd.DataFrame:
    rows = [{"strategy": s, "veto": v, "count": n} for (s, v), n in sorted(vetoes.items())]
    return pd.DataFrame(rows, columns=["strategy", "veto", "count"])


def _md(df: pd.DataFrame) -> str:
    """A DataFrame as a markdown table. Empty frames say so rather than render
    a header with nothing under it -- an empty table reads as a missing
    measurement, and "no rows" is usually the finding."""
    if df.empty:
        return "_(no rows)_"
    head = f"| {' | '.join(map(str, df.columns))} |"
    rule = f"|{'|'.join(['---'] * len(df.columns))}|"
    body = [f"| {' | '.join(_cell(v) for v in row)} |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def _cell(v: Any) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def write(text: str, name: str, out: Path = REPORTS) -> Path:
    """One file per run, named by the minute, never overwritten silently."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now(UTC):%Y-%m-%dT%H%M}_{name}.md"
    path.write_text(text)
    return path
