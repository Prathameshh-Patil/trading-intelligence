# Track B pre-commitments — the numbers, written before the runs

**Scope: the six thresholds in [`strategy-split.md`](strategy-split.md) §7.** Three are Varad's and
are **filled and committed below, 2026-09-06**. Three are Prathamesh's and are left as empty blocks
with the same structure — the same move §5 made with the tick-replay time budget.

**The mechanism is the git timestamp and nothing else.** [`varad/thresholds.md`](varad/thresholds.md)
states why, and it applies to this file verbatim:

> after you have seen a distribution, **every threshold you choose is partly a memory of what you
> saw.** You cannot unsee it. Nobody can.

Two people makes it stronger than that file could: each number is committed to the *other* person,
who reads it and says whether it looks **chosen** or looks **fitted**. Five minutes each, and it is
the one genuine methodological upgrade the split buys (§7).

| # | Pre-commitment | Owner | Reviewed by | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | M1's geometry grid — target / stop / horizon | Varad | Prathamesh | ✅ **committed 2026-09-06** |
| 2 | `atr_bp` bucket edges | Varad | Prathamesh | ✅ **committed 2026-09-06** |
| 3 | `MIN_SAMPLES` per cell in `reach.py` | Varad | Prathamesh | ✅ **committed 2026-09-06** |
| 4 | The six session-phase boundaries, in UTC | Prathamesh | Varad | ⏳ **unset** |
| 5 | The event window, in minutes either side | Prathamesh | Varad | ⏳ **unset** |
| 6 | The 2025/2026 split date | Prathamesh | Varad | ⏳ **unset** |

**Where the numbers live in code.** `ATR_BP_EDGES` is in `features/portable.py`, because that is
where `atr_bp` is and a test fails if it drifts from what is written here. The grid and
`MIN_SAMPLES` belong to modules that do not exist yet — the M1 sweep (step 2) and `reach.py`
(step 7) — so for now this file's commit *is* the commitment. That is not an oversight; it is what
`thresholds.md` says the mechanism is.

---

## 0. What was measured to get here, and why it is not cheating

Every number below is derived from **population statistics with no outcome in them** — the
distribution of `atr_bp` across the archive, and the power arithmetic in `horizon.py`. Nothing here
reads a `p_target` conditioned on anything, and **no EV surface has been computed.** That is the
same licence [`BASE_RATES.md`](../../services/signal-data/analysis/BASE_RATES.md) claims for itself:

> Nothing here selects, tunes or fits. It is the population being measured, the same class of
> statistic as `horizon.py`'s sigma — which is why running it over every month costs no
> out-of-sample data.

Reproduce, ~10 minutes over all 19 months:

```sh
cd services/signal-data
PYTHONPATH=. uv run python - <<'EOF'
from pathlib import Path
import pandas as pd
from features.portable import atr_bp
from instruments import GC
from regimes import resample_bars
from s1 import load_ticks, minute_bars
pool = []
for d in sorted(p for p in Path("data").iterdir() if (p / "gc_trades.parquet").exists()):
    bars = resample_bars(minute_bars(load_ticks(d / "gc_trades.parquet")), "5min")
    pool.append(atr_bp(bars, GC, window="60min", min_bars=6).dropna())
print(pd.concat(pool).quantile([0.25, 0.50, 0.75]))
EOF
```

**109,875 bars carry an ATR value across Jan 2025 – Jul 2026.** Pooled `atr_bp` quartiles:

```
q25   6.79        q50   9.65        q75  13.87       bp of price
```

### The finding that made this worth measuring rather than assuming

**Track A's tick buckets are not stable in basis points, and gold's level moved enough over the
archive to matter.** The `<30 / 30–40 / 40–50 / 50+` tick edges `base_rates.py` uses were fixed in
ticks, so what they *mean* drifted with the price:

| | median price | 30 ticks | 40 ticks | 50 ticks |
| :--- | ---: | ---: | ---: | ---: |
| 2025-01 | 2,732.90 | **10.98 bp** | 14.64 | 18.30 |
| 2026-02 | 5,036.80 | **5.96 bp** | 7.94 | 9.93 |

**A 1.84× drift in the same labelled bucket.** The same effect runs the other way through the
committed 70/20 bracket: 70 ticks is **4.24×** the month's median ATR in 2025-01 and **0.84×** in
2026-03, a five-fold range. `thresholds_selector.md` Part B's bracket was not one trade across the
archive; it was several, wearing one name.

That is ARCHITECTURE §4.6's pooling error, measured in this repo's own data, and it is why the grid
below is in **multiples of the bar's own ATR** and the buckets are in **basis points**.

---

## 1 · M1's geometry grid — Varad, committed 2026-09-06

### The numbers

```
target   ∈ {0.75, 1.0, 1.5, 2.0, 3.0, 4.0}  × the bar's atr_bp
stop     ∈ {0.5,  0.75, 1.0, 1.5}           × the bar's atr_bp
horizon  ∈ {15, 30, 60}                      minutes
                                             = 72 grid points per cell
cost     = 1.4 ticks round trip on GC, converted to bp at the bar's own close
```

Swept per `(atr_bp bucket × phase × side)`, entering every bar, over all 19 months.

### Why these and not others

- **Multiples of ATR, not absolute bp.** A fixed bp target is the same mistake as a fixed tick
  target one level up: §0's table shows the archive's own committed bracket ranging over 5× in ATR
  terms. A multiple means one grid point is the same trade in every bucket and on both instruments,
  which is the only form of this surface that can transfer to spot.
- **The ATR is `expansion.atr` at a 60-minute window on 5-minute bars**, i.e. the mean true range of
  a typical 5-minute bar. So `1.0 ×` is *one typical bar*, and the grid reads in a unit with a
  physical meaning rather than a statistical one.
- **The span brackets the only bracket anyone has committed.** 70/20 at 30m is `1.69 / 0.48` at
  2026-07's median ATR and `0.84 / 0.24` at 2026-03's; the grid's corners (0.75/0.5 and 4.0/1.5)
  contain every month's equivalent. **A grid that only contained 70/20 could only rediscover the
  −4.25 to −1.73 ticks `BASE_RATES.md` already measured**, which is not a frontier.
- **The stop floor is 0.5×, and that is the fragile end on purpose.** `regime_filter.py`: at ATR 40
  a 20-tick stop is *about half a typical bar*, so more volatility makes it **more** prone to
  intrabar noise, not less. `first_touch` resolves same-bar ties to the stop, so exactly there the
  `p_target` / `p_target_max` band is widest. **Report the band at every grid point; never the
  midpoint.** Anything at 0.5× whose two ends disagree about profitability is undecided by bar data
  and stays undecided until step 5's replay.
- **No 5-minute horizon.** `horizon.py` measured the median |move| at 5m as 17 ticks against a
  median ATR of 41.5 in 2026-07 — so even the smallest target here is a tail event at 5m, and the
  cells would be uninformative zeros. 60m is added because reachability is the question and 30m was
  chosen for a *directional* kill gate, which is a different question.
- **72 points is deliberately small.** The grid is where a fit hides: read as 72 independent tests
  per cell, the argmax of a null surface looks like a finding. Keeping it small is a weaker defence
  than the real one, which is the pass line below.

### The pass line — what counts as a positive-EV cell

All three, or the cell is not positive:

1. **n ≥ 400** legs in the cell (§3's number), else the cell reports `null` and is not read.
2. **EV − cost > 0**, with EV `= p_target × target_bp − p_stop × stop_bp` and cost the 1.4-tick
   round trip converted at the bar's close.
3. **`p_target` > `horizon.mde_rate(cell_null, n)`** — the cell beats its own power floor, where
   `cell_null` is the mix- and side-matched unconditional rate for that same bucket and geometry.

**The deliverable is the shape of the surface, not its maximum.** A single grid point clearing the
line inside an otherwise flat surface is a multiple-comparisons artefact and is reported as one. A
contiguous *region* clearing it is a finding.

### What result makes me say no

**No cell clears all three conditions.** That is M1's half of the vol lane's kill condition
(split.md §2), it fires on data already paid for, and it is worth knowing.

### My honest prediction, written before the run

**I expect no cell to clear the cost floor.** `horizon.py` measured the series as a random walk at
5/15/30m from two independent directions, `BASE_RATES.md` found every ATR bucket negative at 70/20
and the gap to breakeven narrowing monotonically but *never closing*, and `FAMILIES.md` found the
order-flow arms flat at power. If something does clear it, I expect it at **short targets
(≤ 1.0 ×)** where `p_target` is high — and I expect the cost floor to eat most of it, because a
0.75× target is roughly three quarters of one bar's range and the round trip is a real fraction of
that. **Being wrong here is the useful outcome; record it either way.**

### One engineering constraint, named now

The sweep as committed is ~**32 million** `first_touch` iterations (219,750 legs × 72 points × 2 for
the tie band). `first_touch` is a Python loop over `bars.loc` slices. **Measure it on one month
before launching 19** — Prime's rule, and this repo's. If the projection is more than a few hours,
vectorise `first_touch` first. That is a shared-spine change: additive, Varad's, Track A's tests as
the gate, and it must not change the tie-to-stop semantics that make every `p_target` a lower bound.

---

## 2 · `atr_bp` bucket edges — Varad, committed 2026-09-06

### The numbers

```python
ATR_BP_EDGES = (0.0, 7.0, 10.0, 14.0, inf)     # features/portable.py
```

Four buckets: `<7`, `7–10`, `10–14`, `14+`, in basis points of price.

### Why these

**They are the pooled quartiles of the archive, rounded to whole basis points.**

| | q25 | q50 | q75 |
| :--- | ---: | ---: | ---: |
| measured, 109,875 bars | 6.79 | 9.65 | 13.87 |
| **committed** | **7** | **10** | **14** |

Pooled share per bucket at the committed edges: **0.270 / 0.259 / 0.227 / 0.245.**

- **Quartiles, because the alternative is worse.** Round numbers borrowed from Track A's tick edges
  would carry §0's 1.84× drift straight into a bp scheme, and edges chosen to make a bucket look
  good are the thing this file exists to prevent. Quartiles are the one split that is a property of
  the data and not of anybody's preference.
- **Rounded, because 6.79 looks fitted even when it is not.** The rounding costs 2 points of balance
  (0.270/0.259/0.227/0.245 against a perfect 0.25 each) and buys a number nobody has to defend.
- **Four buckets, matching `base_rates.py`'s four.** Not because four is right, but because keeping
  the count means Track A's archive null and Track B's surface can be read side by side. Splitting
  finer is a change to this commitment and needs a reason on the page.

### ⚠️ The mix moves violently, and the sweep must be pooled over the archive

Share of each month's bars per bucket. **This is BASE_RATES.md §3's lesson and it is louder here:**

| | `<7` | `7–10` | `10–14` | `14+` |
| :--- | ---: | ---: | ---: | ---: |
| **min** | 0.027 (2026-03) | 0.096 (2026-03) | 0.071 (2025-08) | 0.026 (2025-07) |
| **max** | 0.693 (2025-08) | 0.370 (2025-06) | 0.350 (2025-11) | 0.660 (2026-03) |

**2025-08 spends 69% of its bars in `<7`; 2026-03 spends 66% in `14+`.** A per-month sweep would
produce cells of wildly different weight and a per-month average would weight a 26-leg cell like a
6,000-leg one. **Pool counts across the archive; compute the rate once, at the end** — the same rule
`base_rates.py` already enforces.

It also means §3's floor will bite hard and unevenly. That is the floor working, not failing.

### What would make me change this

A measured reason, not a look at the surface. Two qualify: the bucket boundaries land inside a
structure `rv_slope` reveals more sharply (in which case the axis is `vol_state`, not `atr_bp`, and
the edges are a different commitment), or the spot instrument's `atr_bp` distribution is so
different that the same edges are not the same quartiles there. **Neither is "the 10–14 bucket
looked better at 12."**

---

## 3 · `MIN_SAMPLES` per cell in `reach.py` — Varad, committed 2026-09-06

### The number

```
MIN_SAMPLES = 400        # legs per cell. Below it, PipForecast.forecast is null.
```

### Why 400, derived rather than picked

**A cell may only quote a probability if its own N can tell "tradeable" apart from "the null".**
That is one arithmetic question with one answer.

- The pooled archive null at 70/20/30m long is **0.1644** (`BASE_RATES.md` §1, 107,359 legs).
- The **highest per-bucket breakeven in the archive is 0.224** (`p_stop × 20/70`, the 50+ bucket).
- `horizon.n_for_rate(0.1644, 0.224)` = **327 legs.**

Round up to **400**, where `mde_rate(0.1644, 400) = 0.2181` — clear of the 0.224 line with margin,
and the quoted probability carries **±3.9 pp** at 95% (SE 0.0200 at p ≈ 0.20).

**What the existing floor of 30 actually buys, stated so it is never reused here:**

| n | `mde_rate` | relative lift needed | 95% band at p ≈ 0.20 |
| ---: | ---: | ---: | ---: |
| 30 | 0.3713 | **+126%** | ±14.3 pp |
| 100 | 0.2746 | +67% | ±7.8 pp |
| 200 | 0.2412 | +47% | ±5.5 pp |
| **400** | **0.2181** | **+33%** | **±3.9 pp** |
| 1000 | 0.1980 | +20% | ±2.5 pp |

**At n = 30 a cell needs to more than double the base rate before it can say anything.** Nothing in
this repo has ever produced a lift near that — `FAMILIES.md`'s best arm was +0.0184 — so a 30-leg
cell is not a thin forecast, it is noise with a number attached. `backtest.MIN_SAMPLES = 30` stays
where it is for Track A's *reporting* flag; `reach.py`'s serving floor is this one and they are not
the same object.

### The consequence, accepted in advance

`reach.py`'s key is `(instrument × atr_bp × phase × vol_state × side)`. On GC that is
`4 × 6 × 3 × 2 = 144` cells over 219,750 legs — **~1,500 per cell if they were even, and §2 says
they are nowhere near even.** Many cells will be under 400.

**Those cells return `forecast: null` and that is the correct product behaviour**, not a gap to fill
— ARCHITECTURE §9.4's own words, and stage 9 already treats `forecast: null` as a valid common
answer. **The failure mode this floor exists to stop is a confident 61% off forty legs**, which is
indistinguishable from a good forecast on the screen and is the single cheapest way to destroy the
calibration curve `calibration.py` was built to measure.

### What would make me change this

Only the null moving. `MIN_SAMPLES` is a function of `(null, breakeven)` and nothing else, so if the
sweep's per-cell nulls come back materially different from 0.1644, the number is recomputed **from
the same formula**, in a commit, before any surface is read. It is never adjusted to make a cell
qualify.

---

## 4 · Session-phase boundaries, in UTC — Prathamesh

**Due before M3 runs.** Six phases, `strategy-architecture.md` §2. Reviewed by Varad.

```
phase 1  ______  –  ______ UTC     name: ______
phase 2  ______  –  ______ UTC     name: ______
phase 3  ______  –  ______ UTC     name: ______
phase 4  ______  –  ______ UTC     name: ______
phase 5  ______  –  ______ UTC     name: ______
phase 6  ______  –  ______ UTC     name: ______
```

**Why:** ______

**What result makes the phase axis dead:** ______

Two things worth knowing before writing them. **`reach.py` is written against this column exactly as
delivered** (split.md §6) — a boundary moved after the surface is visible is a fit, so these are the
boundaries. And **the archive crosses DST**: `s1.py`'s `SESSION_SHIFT` is a fixed +2h that assumes
the summer Globex window, and `ohlcv_edge.py` already cut sessions on gaps instead *because the
break moves*. A UTC boundary is stable; a "London open" that is not pinned to UTC is not.

## 5 · The event window, in minutes either side — Prathamesh

**Due before M3 runs.** BLS + FOMC public calendars. Reviewed by Varad.

```
window = ______ minutes either side of a release
```

**Why:** ______

## 6 · The 2025/2026 split date — Prathamesh

**Due before M3 runs.** Reviewed by Varad.

```
split at ______
```

**Why:** ______

ARCHITECTURE §4.4 proposes **2025-01–09 against 2025-10–2026-07**, and `BASE_RATES.md` §3 measured
the step at exactly that seam — pooled monthly `p_target` runs 0.082 before it and 0.178 after. §2's
mix table above is the same break seen from the other side: `<7`'s share collapses from a 2025-08
high of 0.693 to 0.027 by 2026-03. **Adopting the proposed date needs no justification; moving it
does**, because a split date chosen after seeing which one the profile survives is the fit this
whole file is built to prevent.

---

## The rule that outlives this file

**A number in here changes only in a commit that says what measurement moved it, and never after
the surface it governs has been looked at.** If that rule and a promising result ever disagree, the
result is the thing that is wrong.
