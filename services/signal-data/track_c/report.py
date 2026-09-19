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
           span: tuple[pd.Timestamp, pd.Timestamp], independent: int,
           supported: bool, months_needed: int) -> str:
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
        *_verdicts(gates, supported=supported, months_needed=months_needed),
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
        *([] if supported else [
            ("\u26d4 **NOT OUT OF SAMPLE ON THIS RUN.** The holdout starts far enough back "
             "from the last bar to land before the FIRST one, so every trade below is also in "
             "\u00a74's table. C8 restates the in-sample result and is not evidence."),
            ""]),
        _md(pd.DataFrame(holdout).T.reset_index(names="strategy")),
        "",
        "## 7. Trial count",
        "",
        (f"`tuning.Trials` has recorded **{trials.count}** configuration(s) across the "
         "programme. The counter does not reset. A Sharpe quoted without it is not a result."),
        "",
    ]
    return "\n".join(lines)


def _verdicts(gates: pd.DataFrame, *, supported: bool, months_needed: int) -> list[str]:
    """KEEP or KILL per strategy -- **or no verdict, when nothing measured the gates.**

    **A failing strategy is killed and the reason is printed. It is not quietly
    re-tuned** -- `TRACK_C_ENGINE.md` §10.4, and the whole point of committing
    the gate table before the run.

    That finality is exactly why a verdict must not be issued from a gate the
    archive could not measure. Below `walkforward.months_needed` months there
    are no validation windows and no separable holdout, so C6 and C8 read
    `False` for every strategy by arithmetic. Printing KILL there would retire
    four strategies on the length of the archive and call it evidence.
    """
    if not supported:
        return [(f"\u26d4 **NO VERDICT.** The archive is shorter than the {months_needed} "
                 "months \u00a714's geometry needs, so **C6 and C8 were not measured** -- every "
                 "strategy reads `False` on both because there are no windows and no separable "
                 "holdout, not because it failed them. \u00a77 makes a KILL final, so none is "
                 "issued here. Extend the archive to the full span, or amend \u00a714's "
                 "windows; both are the room's call, not this report's.")]
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
