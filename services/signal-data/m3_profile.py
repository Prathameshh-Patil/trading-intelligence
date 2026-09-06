"""M3 — the clock profile, across the archive, split.

Step 3 of `docs/strategy/ARCHITECTURE.md` §6; the clock lane of
`plans/team/strategy-split.md`. Pre-commitments in
`plans/team/prathamesh/clock-lane.md`, all four written before this file ran.

**This produces a clock profile or a clean negative, and the negative is worth
the same as the profile.** ARCHITECTURE §6: three kill conditions can fire on
data already paid for, and dying fast on free data is the most valuable outcome
available here.

WHAT IS MEASURED. `p_target` — how often +target ticks came before −stop ticks
within the horizon — per cell, exactly the statistic `base_rates.py` produces
unconditionally. That is deliberate: **the null is that same measurement on the
same months with the clock axis collapsed**, so a lift is a like-for-like
comparison and not a comparison to a differently-built number.

THREE THINGS THIS ENFORCES RATHER THAN REMEMBERS.

  * **The bucket edges are read from `portable.ATR_BP_EDGES`, never chosen
    here.** They are Varad's pre-commitment (split.md §7, committed 6 Sep at
    `(0, 7, 10, 14, ∞)` bp) and are tripwired by a test in
    `test_instruments.py`. Reading his constant is exactly not the same act as
    picking edges — this lane does not get to choose its own bucket boundaries
    while looking at its own answer, and importing the number means it cannot.
    `--atr-edges` overrides it only for a deliberate sensitivity check, and
    says so loudly when it does.
  * **Both halves of the split, always, in one run.** `clock-lane.md` §3: the
    profile is only a finding if it survives 2025-01–09 against
    2025-10–2026-07. Printing the pooled number alone is how a description of
    2025 becomes a feature, so the pooled number is never printed alone.
  * **All three cuts, always** — phase-only, event-only, union. §5 of
    clock-lane.md pre-commits that, so the union cannot quietly become "the one
    that looked best".

`mde_rate` sits beside every lift. A cell whose lift is inside its own MDE has
not found nothing — it has *not looked*, and those are different sentences.

USAGE
    # Phase profile pooled over ATR — needs no pre-commitment from Varad.
    python m3_profile.py

    # With the bucket axis, once split.md §7's edges exist.
    python m3_profile.py --atr-edges 0 10 15 20 1e9
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest import MIN_SAMPLES, evaluate, first_touch
from calendars import load as load_calendar
from calendars import require_coverage
from features.portable import (
    ATR_BP_EDGES,
    PHASES,
    atr_bp,
    event_proximity,
    session_phase,
)
from horizon import mde_rate
from instruments import GC
from regimes import resample_bars
from s1 import load_ticks, minute_bars

# clock-lane.md §3, and ARCHITECTURE §4.4. Not a parameter: it is the
# pre-committed split and a split chosen at the command line is not one.
SPLIT = "2025-10"

POOLED = "all"  # the label for a cell with the ATR axis collapsed

# Set by main() from the committed bracket, so EV is priced in the same
# ATR units the bracket was placed in.
EV_TARGET, EV_STOP = 3.0, 1.0


def month_cells(
    path: Path,
    *,
    target_atr: float,
    stop_atr: float,
    horizon: int,
    bar_size: str,
    atr_window: str,
    atr_min_bars: int,
    edges: list[float] | None,
    event_window_minutes: int,
    side: int,
) -> pd.DataFrame:
    """One month of ticks -> outcome COUNTS per (bucket x phase x near_event).

    Counts, never rates. `base_rates.py`'s rule and the reason for it applies
    here with an extra axis on top: months differ in bar count by more than 2x,
    so averaging their rates weights a short month like a long one. Every rate
    in this file is computed once, at the end, from pooled counts.

    Entries are every bar, side fixed. **M3's own `phases` argument is not used
    here and that is not an oversight** — a strategy that fires only inside its
    phases produces no legs outside them, and the null this measurement needs
    is the *same population* with the clock collapsed. So every bar becomes a
    leg once, carries its phase as a label, and the cuts are made by grouping.
    `strategies.m3_session_event` is the live-signal form of the same rule and
    is asserted against this in `tests/test_clock.py`.
    """
    bars = resample_bars(minute_bars(load_ticks(path)), bar_size)
    require_coverage(bars)

    trades = evaluate(bars, pd.Series(side, index=bars.index), GC, horizons=(horizon,))

    at = pd.DatetimeIndex(trades["t"])
    measured = atr_bp(bars, GC, window=atr_window, min_bars=atr_min_bars).reindex(at)
    trades["atr_bp"] = measured.to_numpy()
    trades["close"] = bars["close"].reindex(at).to_numpy()
    trades["phase"] = session_phase(bars, GC).reindex(at).to_numpy()
    trades["near_event"] = (
        event_proximity(bars, load_calendar(), window_minutes=event_window_minutes)
        .reindex(at)
        .to_numpy()
    )
    trades["bucket"] = (
        POOLED if edges is None else pd.cut(trades["atr_bp"].to_numpy(), edges).astype("object")
    )

    # **The bracket is resolved from ATR, once per (month x bucket), and this is
    # the whole reason this loop exists.** A FIXED TICK bracket is the §4.6 unit
    # error wearing a measurement's name: gold ran 2,732 -> 5,037 over this
    # archive, so 70 ticks is ~25.6 bp at the start and ~13.9 bp at the end.
    # Bucketing in basis points while bracketing in ticks means the target gets
    # mechanically easier as the archive runs, and the 2025/2026 split -- the
    # test that decides whether M3 is a finding -- then compares two different
    # trades wearing one name. It showed up as the `<7` bucket's null moving
    # 0.0360 -> 0.1088 across the halves, which is not a market fact.
    #
    # Per (month x bucket) and not per trade because `backtest.first_touch`
    # takes one scalar bracket, and giving it a per-trade array is a
    # shared-spine change -- Varad's, split.md §2. Inside one bucket in one
    # month the ATR is near-constant by construction, so this is the same
    # quantity at the resolution this lane is allowed to compute it.
    #
    # The median is a population statistic over the bucket's own bars. No
    # outcome is read to choose it.
    trades["outcome"] = pd.Series(float("nan"), index=trades.index)
    trades["outcome_max"] = pd.Series(float("nan"), index=trades.index)
    trades["atr_ticks"] = pd.Series(float("nan"), index=trades.index)
    sized = trades.dropna(subset=["bucket", "atr_bp", "close"])
    for _, sub in sized.groupby("bucket", observed=True, sort=False):
        atr_ticks = (sub["atr_bp"].median() / 1e4) * sub["close"].median() / GC.tick
        tgt, stp = target_atr * atr_ticks, stop_atr * atr_ticks
        rows = pd.Index(sub.index)
        trades.loc[rows, "atr_ticks"] = atr_ticks
        trades.loc[rows, "outcome"] = first_touch(
            bars, sub, GC, target=tgt, stop=stp, horizon=horizon
        )
        # **The same measurement with same-bar ties read the other way.**
        # `reach_table`'s rule -- report the pair, never the midpoint: bars do
        # not record intrabar order, so the truth is inside the band and they
        # cannot say where. It matters more here than anywhere else in the
        # repo, because a stop at 1x ATR is roughly ONE bar's true range, which
        # is exactly the regime first_touch's docstring flags as widest. An EV
        # quoted off the "stop" convention alone is a lower bound of unstated
        # width, and the width is the thing tick replay (step 5) exists to close.
        trades.loc[rows, "outcome_max"] = first_touch(
            bars, sub, GC, target=tgt, stop=stp, horizon=horizon, ties="target"
        )

    # **What an UNRESOLVED leg is worth, and it is not zero.** Assigning 0 to
    # `neither` treats the horizon as neutral, and it is not: a leg that
    # survived 30 minutes without touching a stop one ATR away did so BECAUSE
    # it drifted the right way, so the survivors are biased upward. Pricing
    # them at 0 charges the strategy for every stop and credits it for no part
    # of the paths that quietly worked -- which made EV read about -0.27 ATR
    # for a series `horizon.py` measured as a random walk, where it should
    # read about zero. The realized move at the horizon is already in
    # `evaluate`'s output; it just has to be carried, in ATR units so it can
    # be added to the barrier payoffs.
    trades["move_atr"] = trades[f"move_{horizon}m"] / trades["atr_ticks"]
    trades["open_pnl"] = trades["move_atr"].where(trades["outcome"] == 0, 0.0)

    done = trades.dropna(subset=["outcome", "bucket", "phase", "open_pnl"])
    g = done.groupby(["bucket", "phase", "near_event"], observed=False)
    return pd.DataFrame(
        {
            "n": g["outcome"].size(),
            "target": g["outcome"].apply(lambda s: int((s == 1).sum())),
            "stop": g["outcome"].apply(lambda s: int((s == -1).sum())),
            "target_max": g["outcome_max"].apply(lambda s: int((s == 1).sum())),
            "stop_min": g["outcome_max"].apply(lambda s: int((s == -1).sum())),
            # Summed, not averaged -- the same counts-never-rates rule.
            "open_pnl": g["open_pnl"].sum(),
        }
    )


def profile(counts: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Pooled counts -> a rate table over `by`, with the null and its MDE beside it.

    The null is this same table with `by`'s clock axes collapsed and everything
    else held — same bucket, same side, same months. **That is what makes the
    lift a lift** rather than a comparison against a number built differently
    somewhere else.
    """
    cols = ["n", "target", "stop", "target_max", "stop_min", "open_pnl"]
    cell = counts.groupby(["bucket", *by], observed=False)[cols].sum()
    null = counts.groupby(["bucket"], observed=False)[["n", "target"]].sum()

    out = cell.reset_index()
    out["p_target"] = (out["target"] / out["n"]).where(out["n"] > 0)
    joined = out.join(
        (null["target"] / null["n"]).rename("p_null"), on="bucket"
    ).join(null["n"].rename("n_null"), on="bucket")

    joined["lift"] = joined["p_target"] - joined["p_null"]
    # What a lift would have had to be, in this cell, to be visible at all.
    joined["mde"] = [
        mde_rate(p0, int(n)) - p0 if n > 0 and pd.notna(p0) else float("nan")
        for p0, n in zip(joined["p_null"], joined["n"], strict=True)
    ]
    joined["visible"] = joined["lift"].abs() >= joined["mde"]
    joined["thin"] = joined["n"] < MIN_SAMPLES

    # EV per leg in ATR units: +target_atr on a target, -stop_atr on a stop,
    # ~0 on neither (price is inside the bracket when the horizon expires).
    # Reported as a BAND because the tie convention is a real uncertainty and
    # not a rounding one -- ev_lo reads same-bar ties to the stop, ev_hi to the
    # target, and no bar frame can say which happened.
    n = joined["n"].where(joined["n"] > 0)
    joined["ev_lo"] = (
        EV_TARGET * joined["target"] - EV_STOP * joined["stop"] + joined["open_pnl"]
    ) / n
    joined["ev_hi"] = (
        EV_TARGET * joined["target_max"] - EV_STOP * joined["stop_min"] + joined["open_pnl"]
    ) / n
    return joined


def show(label: str, counts: pd.DataFrame, by: list[str]) -> None:
    print(f"\n--- {label} ---")
    t = profile(counts, by)
    cols = ["bucket", *by, "n", "p_target", "p_null", "lift", "mde", "visible", "thin",
            "ev_lo", "ev_hi"]
    print(t[cols].round(4).to_string(index=False))
    seen = t[t["visible"] & ~t["thin"]]
    if seen.empty:
        print("  -> no cell moved further than its own MDE. That is a NEGATIVE, not a null result.")
    else:
        print(f"  -> {len(seen)} cell(s) outside their own MDE: "
              f"{', '.join(str(r) for r in seen[by[0]].tolist())}")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--data", type=Path, default=Path("data"), help="dir of YYYY-MM/gc_trades.parquet")
    # **Multiples of ATR, not ticks, and both are points on Varad's committed
    # M1 grid** (strategy-precommit.md §1: target {0.75,1,1.5,2,3,4} x stop
    # {0.5,0.75,1,1.5}). 3.0/1.0 is that grid's closest analogue to
    # BASE_RATES.md's 70/20, whose 3.5:1 ratio it nearly matches. Reading a
    # point off an already-committed grid is not the same act as picking a
    # bracket, and this lane does not get to do the second one.
    p.add_argument("--target-atr", type=float, default=3.0, help="multiples of the bucket's ATR")
    p.add_argument("--stop-atr", type=float, default=1.0, help="multiples of the bucket's ATR")
    p.add_argument("--horizon", type=int, default=30, help="minutes")
    p.add_argument("--bar-size", default="5min")
    p.add_argument("--atr-window", default="60min")
    p.add_argument("--atr-min-bars", type=int, default=6)
    p.add_argument(
        "--atr-edges", type=float, nargs="+", default=None,
        help="Override the committed atr_bp bucket edges. The default is "
             "portable.ATR_BP_EDGES -- Varad's pre-commitment, split.md §7. "
             "Passing this is a sensitivity check and is labelled as one in "
             "the output; it is not how the reported profile is produced.",
    )
    p.add_argument(
        "--pool-atr", action="store_true",
        help="Collapse the ATR axis entirely: the phase profile pooled over "
             "volatility. A coarser cut, not a different commitment.",
    )
    p.add_argument("--event-window", type=int, default=15, help="minutes either side; clock-lane.md §2")
    p.add_argument("--side", type=int, choices=[1, -1], default=1)
    p.add_argument("--out", type=Path, help="write pooled per-cell counts to CSV")
    a = p.parse_args()

    global EV_TARGET, EV_STOP
    EV_TARGET, EV_STOP = a.target_atr, a.stop_atr

    months = sorted(d for d in a.data.iterdir() if (d / "gc_trades.parquet").exists())
    if not months:
        raise SystemExit(f"no YYYY-MM/gc_trades.parquet under {a.data}")

    if a.pool_atr:
        edges = None
        print("!! --pool-atr: ATR axis COLLAPSED. This is the phase profile pooled over\n"
              "!! volatility -- a coarser cut of the same commitment, not a second one.\n")
    elif a.atr_edges is not None:
        edges = a.atr_edges
        print(f"!! SENSITIVITY CHECK: --atr-edges {a.atr_edges} overrides the committed\n"
              f"!! {list(ATR_BP_EDGES)} (split.md §7). This output is NOT the reported\n"
              "!! profile. A grid widened after a surface is visible is a fit.\n")
    else:
        edges = list(ATR_BP_EDGES)

    halves: dict[str, pd.DataFrame] = {}
    for month in months:
        counts = month_cells(
            month / "gc_trades.parquet",
            target_atr=a.target_atr, stop_atr=a.stop_atr, horizon=a.horizon, bar_size=a.bar_size,
            atr_window=a.atr_window, atr_min_bars=a.atr_min_bars, edges=edges,
            event_window_minutes=a.event_window, side=a.side,
        )
        half = "train 2025-01..09" if month.name < SPLIT else "held 2025-10..2026-07"
        halves[half] = counts if half not in halves else halves[half].add(counts, fill_value=0)
        print(f"{month.name}  n={int(counts['n'].sum()):6d}  [{half}]", flush=True)

    total = None
    for c in halves.values():
        total = c if total is None else total.add(c, fill_value=0)
    assert total is not None

    side_name = "long" if a.side > 0 else "short"
    print(f"\n{'=' * 78}\nM3 clock profile — {len(months)} months, {side_name}, "
          f"{a.target_atr:g}x/{a.stop_atr:g}x ATR at {a.horizon}m, event ±{a.event_window}m\n"
          f"bracket in MULTIPLES OF ATR, resolved per month x bucket — never fixed ticks\n{'=' * 78}")

    # Every cut, on the pooled archive and on each half. clock-lane.md §5 --
    # committed before the run, so the union cannot become the chosen one.
    for label, counts in [("POOLED — all months", total), *halves.items()]:
        print(f"\n{'#' * 78}\n# {label}   (n={int(counts['n'].sum())})\n{'#' * 78}")
        show("phase only", counts, ["phase"])
        show("event only", counts, ["near_event"])
        show("union (phase x event)", counts, ["phase", "near_event"])

    print("\n**Read the split, not the pooled table.** A phase that lifts on the pooled\n"
          "archive and reverses across the halves is a description of 2025 "
          "(ARCHITECTURE §4.4).")
    print(f"Phase order as delivered to reach.py: {list(PHASES)}")

    if a.out:
        total.to_csv(a.out)
        print(f"\nwrote pooled per-cell counts -> {a.out}")


if __name__ == "__main__":
    main()
