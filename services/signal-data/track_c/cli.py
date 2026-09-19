"""`python -m track_c {preload,suggest,backtest,walkforward,audit,report,live}`.

Thin by design: every subcommand parses arguments, calls one function, and
prints. Nothing here decides anything -- a CLI that holds logic is a second
engine with no tests.

⚠️ **`live` IS NOT REAL TIME AND THE COMMAND SAYS SO EVERY TIME IT RUNS.**
Dukascopy's S3 objects are one per instrument-day and update daily
(`spot_s3.py`), so the freshest bar this pipeline can build is hours old. The
command evaluates the latest available bar close, which is the same code path
the backtest uses; it is a dry run of the live loop, not a trading session. A
real-time path needs a streaming feed this repo does not have and a broker
connection §7's gates have not authorised.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

import calendars
import dukascopy
import spot
import spot_s3
import tuning
from instruments import XAUUSD, Instrument
from track_c import (
    audit,
    config,
    engine,
    funnel,
    metrics,
    report,
    strategies,
    suggest,
    walkforward,
)

CACHE = Path("data/spot/XAUUSD")
LAST_RUN = report.REPORTS / "last_run"


def load_bars(months: list[str], inst: Instrument, cfg: dict[str, Any],
              cache: Path = CACHE) -> pd.DataFrame:
    """Cached Dukascopy ticks -> 1-minute mid bars -> `[data].bar` bars.

    `spot.py`'s functions, composed. Not re-spelled: a second resampler is how
    two files come to disagree about which minute a bar belongs to.
    """
    ticks = spot.load_ticks(cache, months)
    return spot.resample(spot.minute_bars(ticks, inst), config.get(cfg, "data.bar"), inst)


def _events() -> pd.DatetimeIndex:
    """§12's release calendar. Absent file is a hard failure, not an empty index:
    a silent empty calendar disables the one filter whose failure is invisible."""
    return calendars.load()


# The same day frame from either transport, and the choice is the caller's.
# `s3` is one object per day and wants an AWS account; `http` is that day's 24
# hour-files, wants nothing, and costs ~3 minutes a day. See `dukascopy.fetch_day`.
TRANSPORTS: dict[str, Callable[[str, date], pd.DataFrame]] = {
    "s3": spot_s3.fetch_day,
    "http": dukascopy.fetch_day,
}


def cmd_preload(a: argparse.Namespace) -> None:
    """Dukascopy days into the cache. Resumable; a cached day is skipped."""
    spot.pull(a.symbol, a.months, a.out, fetch=TRANSPORTS[a.transport])


def cmd_suggest(a: argparse.Namespace) -> None:
    """"Any setups now?" -- the four strategies against the last cached bar."""
    cfg = config.load()
    bars = load_bars(a.months, XAUUSD, cfg)
    for o in suggest.at(bars, XAUUSD, cfg, events=_events(), when=a.at):
        print(o)


def cmd_backtest(a: argparse.Namespace) -> None:
    """One pass over the cached archive. Attrition first, metrics second."""
    cfg = config.load()
    bars = load_bars(a.months, XAUUSD, cfg)
    res = engine.run(bars, XAUUSD, cfg, events=_events())
    print(funnel.table(res.counts, strategies.CONDITIONS).to_string(index=False))
    print()
    per = {s: metrics.summarize(res.trades[res.trades["strategy"] == s], cfg)
           for s in config.STRATEGIES}
    print(pd.DataFrame(per).T.to_string())
    print(f"\n{len(res.trades)} trades, {res.unresolved} of them with fills this bar size "
          f"cannot resolve. Every number above is an upper bound.")
    _save(res, bars)


def cmd_walkforward(a: argparse.Namespace) -> None:
    """The windows, the holdout, and §7's gate table."""
    cfg = config.load()
    bars = load_bars(a.months, XAUUSD, cfg)
    res = engine.run(bars, XAUUSD, cfg, events=_events())
    _save(res, bars)
    print(_gates(res, bars, cfg).to_string(index=False))
    span = (bars.index[0], bars.index[-1])
    if not walkforward.supports_gates(span, cfg):
        # The table above is printed either way; what changes is whether C6 and
        # C8 mean anything. Said here as well as in the report, because this is
        # the command whose output gets read at the terminal and quoted.
        print(f"\nNOTE: this archive is shorter than the {walkforward.months_needed(cfg)} months "
              "§14 needs, so there are no validation windows and no separable holdout. C6 and C8 "
              "read False for every strategy by arithmetic, not by evidence. `report` issues no "
              "verdict on a run like this.")


def cmd_report(a: argparse.Namespace) -> None:
    """Render the last saved run as markdown. Does not re-run the engine."""
    cfg = config.load()
    res, bars_span = _load_run()
    sp = walkforward.split(pd.DatetimeIndex(bars_span), cfg)
    trials = tuning.Trials()
    trials.record()
    per = {s: metrics.summarize(res.trades[res.trades["strategy"] == s], cfg)
           for s in config.STRATEGIES}
    windows = walkforward.window_totals(res.trades, sp, config.STRATEGIES)
    holdout = walkforward.holdout_summary(res.trades, sp, config.STRATEGIES, cfg)
    gates = metrics.gate_table(per_strategy=per, counts=res.counts, windows=windows,
                               holdout=holdout, trials=trials, cfg=cfg)
    text = report.render(res=res, cfg=cfg, per_strategy=per, gates=gates, windows=windows,
                         holdout=holdout, trials=trials,
                         span=(bars_span[0], bars_span[-1]),
                         independent=walkforward.independent(sp, cfg),
                         supported=walkforward.supports_gates(
                             (bars_span[0], bars_span[-1]), cfg),
                         months_needed=walkforward.months_needed(cfg))
    print(report.write(text, a.name))


def cmd_audit(a: argparse.Namespace) -> None:
    """§6.1's honest limit, measured: 5-minute trades re-judged at 1 minute.

    Both frames come from the same cached ticks, so the only difference between
    them is resolution -- which is the whole point, and would not hold if one
    side came from a different pull.
    """
    cfg = config.load()
    bars = load_bars(a.months, XAUUSD, cfg)
    res = engine.run(bars, XAUUSD, cfg, events=_events())
    fine = spot.minute_bars(spot.load_ticks(CACHE, a.months), XAUUSD)
    cmp = audit.compare(res.trades, fine, XAUUSD, cfg)
    print(cmp.to_string())
    for k, v in audit.summary(cmp).items():
        print(f"{k}: {v}")


def cmd_live(a: argparse.Namespace) -> None:
    """The latest available bar close. NOT real time -- see the module docstring."""
    print("NOTE: Dukascopy day objects update daily. This is the latest AVAILABLE bar, "
          "not a live quote. No order is placed by this command or by any other.")
    cmd_suggest(a)


def _gates(res: engine.Result, bars: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    sp = walkforward.split(pd.DatetimeIndex(bars.index), cfg)
    trials = tuning.Trials()
    trials.record()
    per = {s: metrics.summarize(res.trades[res.trades["strategy"] == s], cfg)
           for s in config.STRATEGIES}
    return metrics.gate_table(
        per_strategy=per, counts=res.counts,
        windows=walkforward.window_totals(res.trades, sp, config.STRATEGIES),
        holdout=walkforward.holdout_summary(res.trades, sp, config.STRATEGIES, cfg),
        trials=trials, cfg=cfg)


def _save(res: engine.Result, bars: pd.DataFrame) -> None:
    """Trades, counts and the bar span, so `report` need not re-run the engine."""
    LAST_RUN.mkdir(parents=True, exist_ok=True)
    res.trades.to_parquet(LAST_RUN / "trades.parquet")
    (LAST_RUN / "counts.json").write_text(json.dumps(
        {"counts": [[s, k, n] for (s, k), n in res.counts.items()],
         "vetoes": [[s, k, n] for (s, k), n in res.vetoes.items()],
         "bars": res.bars, "unresolved": res.unresolved,
         "span": [str(bars.index[0]), str(bars.index[-1])]}))


def _load_run() -> tuple[engine.Result, pd.DatetimeIndex]:
    meta = json.loads((LAST_RUN / "counts.json").read_text())
    res = engine.Result(trades=pd.read_parquet(LAST_RUN / "trades.parquet"),
                        counts=funnel.new(), bars=meta["bars"],
                        unresolved=meta["unresolved"])
    for s, k, n in meta["counts"]:
        res.counts[(s, k)] = n
    for s, k, n in meta["vetoes"]:
        res.vetoes[(s, k)] = n
    return res, pd.DatetimeIndex([pd.Timestamp(t) for t in meta["span"]])


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="track_c", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pre = sub.add_parser("preload", help="pull Dukascopy day objects into the cache")
    pre.add_argument("--symbol", default="XAUUSD")
    pre.add_argument("--months", nargs="+", required=True, help="YYYY-MM")
    pre.add_argument("--out", type=Path, default=CACHE)
    pre.add_argument("--transport", choices=sorted(TRANSPORTS), default="s3",
                     help="s3 needs AWS credentials and is the bulk path; "
                          "http needs none and is ~3 min/day")
    pre.set_defaults(fn=cmd_preload)

    for name, fn, doc in (("suggest", cmd_suggest, "evaluate one bar"),
                          ("backtest", cmd_backtest, "one pass over the archive"),
                          ("walkforward", cmd_walkforward, "windows, holdout, gates"),
                          ("audit", cmd_audit, "5-minute fills re-judged at 1 minute"),
                          ("live", cmd_live, "the latest available bar close")):
        s = sub.add_parser(name, help=doc)
        s.add_argument("--months", nargs="+", required=True, help="YYYY-MM")
        s.add_argument("--at", type=pd.Timestamp, default=None,
                       help="evaluate at this instant instead of the last bar")
        s.set_defaults(fn=fn)

    rep = sub.add_parser("report", help="render the last saved run as markdown")
    rep.add_argument("--name", default="run")
    rep.set_defaults(fn=cmd_report)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
