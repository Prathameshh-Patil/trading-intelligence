"""The intra-bar audit: what the 5-minute backtest cannot know, quantified.

**THIS MODULE DOES NOT FIX THE PROBLEM. IT MEASURES IT.** §9's limit lives 20
seconds and a 5-minute bar cannot resolve a 20-second order; neither can a
1-minute one. What 1-minute bars CAN say is how much of the 5-minute answer
came from the extra four minutes of hindsight -- and that is a number, per
trade, rather than a caveat.

TWO QUESTIONS, ASKED SEPARATELY BECAUSE THEY FAIL DIFFERENTLY:

  * **Was the entry real?** The 5-minute engine fills a limit if the NEXT
    5-minute bar traded through it. At 1 minute the same test over the FIRST
    minute after the signal is four times closer to the 20 seconds §9 actually
    grants. A 5-minute fill with no 1-minute fill behind it is a trade the
    backtest invented -- and every such trade is scored at its own entry price,
    so they do not cancel out.
  * **Was the outcome real?** A 5-minute bar that clears both barriers is
    resolved to the stop by convention (`backtest.first_touch`'s rule), because
    the order is not in the bar. At 1 minute the order often IS in the bars,
    and `first_touch_from` -- the repo's one definition of first touch, called
    here rather than re-spelled -- gives the finer answer.

`replay.py` is the template: it asked the same question for Track B at tick
resolution and found bars carry the MFE/MAE order 95.8% of the time. **That
number is Track B's and does not transfer**, because Track C's brackets are
$2-$5 wide where Track B's were measured in ATR multiples.

WHAT A DISAGREEMENT MEANS. It does not mean the 1-minute answer is the truth --
it is a finer upper bound, not a measurement. It means the 5-minute number is
optimistic by at least the disagreement rate, and every headline derived from
it must be labelled an upper bound. Only a tick replay settles it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import backtest as bt
from instruments import Instrument
from track_c import fills

OUTCOME = {1: "target", -1: "stop", 0: "neither"}


def entry_agreement(trades: pd.DataFrame, bars_1m: pd.DataFrame,
                    cfg: dict[str, Any]) -> pd.Series:
    """Would the first MINUTE after each signal have filled the limit too?

    The same `fills.limit_filled` test, so the two answers differ only in the
    window they are asked over -- if this called a second fill rule, a
    disagreement would be a fact about the two rules rather than about the bars.
    """
    out = []
    # `to_dict("records")` rather than `itertuples`: a namedtuple field off a
    # mixed-dtype frame is typed as the union of every column's dtype, and the
    # casts needed to satisfy that are noise around the one real question here.
    for t in trades.to_dict("records"):
        after = bars_1m.loc[bars_1m.index > t["ts_signal"]]
        if after.empty:
            out.append(False)
            continue
        first = after.iloc[0]
        out.append(fills.limit_filled(
            first, limit=float(t["entry"]), side=int(t["side"]),
            spread_usd=float(first["spread_bp"]) / 1e4 * float(first["close"]),
            cfg=cfg, news=False))
    return pd.Series(out, index=trades.index, dtype=bool)


def outcome_at_one_minute(trades: pd.DataFrame, bars_1m: pd.DataFrame,
                          inst: Instrument) -> pd.Series:
    """First touch of each trade's bracket, judged on 1-minute bars.

    `backtest.first_touch_from` is called once per trade rather than vectorised
    across them, because each Track C trade carries its own D and R and the
    shared function takes a scalar bracket. A few dozen calls is nothing; a
    second copy of the first-touch convention is the thing this repo has
    already paid for once.

    NaN where the trade's own bars are absent or the horizon runs past the
    session -- the same meaning `first_touch` gives it: a leg the tape never
    offered is not a leg that went nowhere.
    """
    out = []
    for t in trades.to_dict("records"):
        entry_ts, exit_ts = pd.Timestamp(t["ts_entry"]), pd.Timestamp(t["ts_exit"])
        minutes = int((exit_ts - entry_ts).total_seconds() // 60) + 1
        leg = pd.DataFrame({"t": [entry_ts], "side": [int(t["side"])],
                            "entry": [float(t["entry"])]})
        try:
            ex = bt.excursions(bars_1m, leg, inst, horizon=minutes)
            touch = bt.first_touch_from(
                ex, target=abs(float(t["target"]) - float(t["entry"])) / inst.tick,
                stop=float(t["d_usd"]) / inst.tick)
            out.append(float(touch.iloc[0]))
        except (KeyError, IndexError, ValueError):
            # The 1-minute frame does not cover this trade. Unknown, and
            # unknown must not be read as agreement.
            out.append(float("nan"))
    return pd.Series(out, index=trades.index, dtype=float)


def compare(trades: pd.DataFrame, bars_1m: pd.DataFrame, inst: Instrument,
            cfg: dict[str, Any]) -> pd.DataFrame:
    """Per trade: did the finer bars agree about the entry and about the exit?

    **Trades whose stop moved to break-even are excluded from the outcome
    column, not from the entry column.** A moved stop is not a fixed bracket,
    and `first_touch_from` answers a fixed-bracket question; scoring them
    against it would produce disagreements that are an artefact of the
    comparison rather than of the resolution.
    """
    if trades.empty:
        return pd.DataFrame(columns=["entry_agrees", "bar_outcome", "min_outcome",
                                     "outcome_agrees"])
    out = pd.DataFrame(index=trades.index)
    out["entry_agrees"] = entry_agreement(trades, bars_1m, cfg)
    out["bar_outcome"] = trades["exit_reason"]
    fine = outcome_at_one_minute(trades, bars_1m, inst)
    out["min_outcome"] = [OUTCOME.get(int(v)) if np.isfinite(v) else None for v in fine]
    comparable = trades["exit_reason"].isin(["stop", "target"]) & ~trades["be_moved"]
    # Plain Python `bool | None` rather than a masked boolean column: `None`
    # here means "not judged", and a numpy boolean array has no room for a
    # third state -- it would have to be False, which reads as disagreement.
    out["outcome_agrees"] = [
        bool(b == m) if (ok and m is not None) else None
        for b, m, ok in zip(out["bar_outcome"], out["min_outcome"], comparable, strict=True)]
    return out


def summary(cmp: pd.DataFrame) -> dict[str, float | str]:
    """The three numbers that go in the report, and the label they force.

    `label` is the sentence every headline from this run has to carry. It is
    produced here rather than written by whoever writes the report, because a
    caveat that depends on someone remembering it is a caveat that goes
    missing in month four.
    """
    n = len(cmp)
    if n == 0:
        return {"n": 0, "entry_agreement": float("nan"), "outcome_agreement": float("nan"),
                "label": "no trades to audit"}
    entry = float(cmp["entry_agrees"].mean())
    judged = cmp["outcome_agrees"].dropna()
    outcome = float(judged.mean()) if len(judged) else float("nan")
    return {
        "n": n,
        "entry_agreement": entry,
        "outcome_agreement": outcome,
        "n_outcome_judged": len(judged),
        "label": (f"UPPER BOUND: {1 - entry:.1%} of 5-minute fills are not confirmed by the "
                  f"first minute after the signal, and {1 - outcome:.1%} of resolvable outcomes "
                  "flip at 1-minute resolution. Neither resolves §9's 20-second order life; "
                  "only a tick replay does."),
    }
