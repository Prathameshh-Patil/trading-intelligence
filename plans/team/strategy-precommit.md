# Track B pre-commitments — the numbers, written before the runs

**Scope: the six thresholds in [`strategy-split.md`](strategy-split.md) §7.** Three are Varad's and
are **filled and committed below, 2026-09-06**. Prathamesh's were filled the same day, plus a
fourth nobody had listed. What follows was originally written as three empty blocks
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
| 4 | The six session-phase boundaries | Prathamesh | Varad | ⚠️ **committed 2026-09-06 — in ET, not UTC. Needs Varad's eye, not his nod** |
| 5 | The event window, in minutes either side | Prathamesh | Varad | ✅ **committed 2026-09-06** |
| 6 | The 2025/2026 split date | Prathamesh | Varad | ✅ **committed 2026-09-06** |
| 7 | The opening-range length | Prathamesh | Varad | ✅ **committed 2026-09-06** — a fourth, not in the original six |

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

### ✅ ANSWERED 2026-09-07 — the surface is a random walk minus cost

Result: [`analysis/M1_SURFACE.md`](../../services/signal-data/analysis/M1_SURFACE.md). 3,456 cells,
19 months, both sides, 1h 35m. **Mean gross EV before cost: −0.0032 ATR. Mean cost: +0.0423.** The
whole negative result is the commission, and it does not move across horizon or bucket.

**The committed pass line admits 159 cells (4.6%), and none of them is a finding.** The two tools
this section committed *before* the run are what disqualify them, rather than any rule invented
after: the side mirror removes 145 (only 68 of 3,456 cells are positive at all once the opposite
side is averaged in), and the `ev_barrier` / `ev_open` split removes 13 of the remaining 14 — they
lose money on trades that closed and get their EV from mark-to-market on legs still open. What
survives both is **one cell at `ev_sym` +0.0005 ATR**, two hundredths of a tick, whose own mirror
fails.

**The prediction, scored.** *"No cell clears the cost floor"* — **wrong on the letter**, 159 do.
*"If one does, expect it at targets ≤ 1.0×"* — **wrong, and in the opposite direction**: the passes
concentrate at 3.0× and 4.0×, because a low `p_target` at a wide target leaves most legs unresolved
and the mark-to-market on those carries the EV. *The mechanism* — random walk, nothing to pay for
cost — **right, and it is the finding.** Wrong conclusion, right mechanism: a random walk does not
imply no cell clears an EV screen, and on 3,456 cells drift and open marks produce passes at exactly
this rate.

**This does not fire the kill condition and it is not being read as though it does.**
`strategy-split.md` §2 requires no positive-EV cell **and** M2 inside its own MDE. Cells cleared.
M2 is still owed.

### One engineering constraint — ✅ MEASURED 2026-09-06, and it does not bind

The sweep as committed is ~**31 million** `first_touch` iterations (107,359 legs × 72 points × 2 for
the tie band × 2 sides), and `first_touch` is a Python loop over `bars.loc` slices. The commitment
said measure one month before launching 19 rather than guess. Measured on 2026-07 — 6,276 bars,
6,253 legs, grouped `(atr_bp bucket × phase)` exactly as the sweep will:

```
6 grid points, 288 first_touch calls : 12.2s      -> 2.03s per grid point
one month,  72 points, one side      : 2.4 min
19 months,  72 points, one side      : 46.4 min
19 months,  72 points, BOTH sides    : 1.55 HOURS
```

**Under two hours, so `first_touch` is not vectorised and the shared spine is not touched.** Cost is
linear in legs and effectively free in the number of groups — splitting 4 buckets into 24
`(bucket × phase)` cells changed the total by 1%, so the per-call `session_ends` rebuild is not
where the time goes. 2026-07 is ~8% larger than the archive's average month, so the projection errs
long.

**One thing the timing run showed that matters more than the runtime.** At `(bucket × phase)` on a
single month the cells run **min 1, max 727 legs**. Pooled over 19 months that is roughly 19 to
13,800 — so §3's `MIN_SAMPLES = 400` will disqualify a large minority of cells outright, exactly as
that section accepted in advance, and the sweep **must** pool across the archive rather than report
per month.

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

## 8 · M2's vol-momentum thresholds — Varad, committed 2026-09-07

**Due before M2 runs. An eighth, not in the original six** — §7's table did not list M2 because
`strategy-split.md` §7 was written when M2 was a name in a build order. **Step 4 selects**
(ARCHITECTURE §6), so it needs the same discipline as everything above it.

Reviewed by Prathamesh. **Nothing about a forward move has been read at the time of this commit** —
only `rv_slope`'s own distribution, which is a feature and carries no outcome, on the training half
alone.

### The numbers

```
window, min_bars   60min, 6      the window atr_bp already uses
slope_min          0.20          EXPANDING >= +0.20, CONTRACTING <= -0.20, STABLE between
T                  {1.0, 1.5, 2.0} x the bar's atr_bp        magnitude thresholds
H                  {15, 30, 60} minutes                       horizons
data               TRAINING HALF ONLY -- 2025-01..09, per §6's committed SPLIT
```

### Why these

- **The window is `atr_bp`'s window, not a new one.** 60 minutes on 5-minute bars, `min_bars=6`.
  Using a second window length would put the two axes of `reach.py`'s bucket key on two different
  clocks, and `regime_filter.py`'s rule about re-solving windows applies across features as much as
  across files.
- **`slope_min = 0.20`, symmetric, and the symmetry is the defence.** Measured on the training half
  alone, 49,910 bars:

  | | 1/3 | median | 2/3 |
  | :--- | ---: | ---: | ---: |
  | `rv_slope` | −0.150 | **−0.036** | +0.101 |

  The raw terciles are asymmetric because **volatility decays slowly and expands sharply** — the
  median bar is in mild decay. A symmetric ±0.20 cut yields **CONTRACTING 0.257 / STABLE 0.494 /
  EXPANDING 0.249**: within 1.5 points of equal tail mass without being a tercile, and a round
  symmetric number that cannot be read as chosen to make one arm look good. **It reports the
  distribution's asymmetry rather than absorbing it into the cut.**

  The nine training months agree closely — median `rv_slope` runs −0.030 to −0.046 and median
  `efficiency_ratio` 0.260 to 0.279 — so this is not a number propped up by one month.
- **`T` and `H` are M1's, reused rather than invented.** `{1.0, 1.5, 2.0} × ATR` are three of M1's
  six committed targets and `{15, 30, 60}` are its horizons exactly. A second grid here would be a
  second place a number could be chosen.
- **One side, and that is a property of the claim rather than a shortcut.** M2 predicts
  `|move|`, and a long and a short entered on the same bar have the same `|move|` by construction.
  **A magnitude claim has no side**, so a side-matched null is not merely unnecessary here, it
  would be measuring the same legs twice.

### The pass line

`P(|move| ≥ T within H)` in the EXPANDING arm, against the **ATR-matched null** — the same
`atr_bp` bucket, pooled over `vol_state`:

1. **n ≥ 400** legs in the cell, else it reports nothing (§3).
2. **`P(|move| ≥ T)` in EXPANDING exceeds the null by more than `mde_rate(null, n)`.**

**And there is deliberately no EV condition, which needs saying rather than passing over.**
Prathamesh's correction — *a kill condition must be stated in EV net of cost* — is right for M3 and
for M1, and it does not apply here, because **M2's output is not a trade.** It is
`P(|move| ≥ T within H)` feeding stage 7 as a second conditioning dimension; there is no bracket, no
stop and therefore no round trip to clear. A rate against a matched null with `mde_rate` beside it
is the whole of what M2 claims.

**What that costs, stated now so it is not discovered later:** a real M2 result is a **forecasting**
result and the bridge to a **trading** one is not free. The moment it is converted into a bracket it
meets M1's surface, where gross EV is −0.0032 ATR against a cost of +0.0423. M2 clearing its MDE
would not by itself make anything tradeable.

### What result makes the vol axis dead

`strategy-split.md` §2: **no cell on M1's surface clears EV − cost > 0 at n ≥ 400 *and* M2 lands
inside its own MDE.** M1's half did not fire — 159 cells cleared, for reasons `M1_SURFACE.md`
disqualifies but which the letter of the line admits. **So M2 landing inside its MDE does not kill
the lane on its own either.** If both readings are taken together the lane is dead in substance and
alive on the letter, and that gap is a finding about the kill line rather than about gold.

### ✅ ANSWERED 2026-09-07 — M2 clears, and it is about scale

Result: [`analysis/M2_MAGNITUDE.md`](../../services/signal-data/analysis/M2_MAGNITUDE.md).
**EXPANDING beats CONTRACTING in 9 of 9 (T, H) combinations and STABLE in 9 of 9; 17 of 36 cells
clear their own `mde_rate`.** Largest cell `10–14 bp · T=1.5 · H=60m`, lift **+0.0516** against an
MDE of 0.4457. Mean lift over passing cells +0.033.

**The comparison that makes it different in kind from M1: M1 passed 4.6% of 3,456 cells, which is
noise. M2 passes 47% of its 36.** Same power arithmetic, same bucket edges, same archive.

**It is scale, not direction** — both tails rise together and the gap is 7.5% of the hit rate. ⚠️
**One residue on the record: EXPANDING carries a +0.024 up-tilt that CONTRACTING does not** (−0.003),
which I predicted would not exist. Gold rose across the archive, so it may be drift co-occurrence;
that is a hypothesis and the held-out half is where to ask.

**Where it fails is informative:** the `14+ bp` bucket clears nothing, mean lift +0.0066. `atr_bp`
already conditions on the level, so at the top of the distribution the bucket has done the slope's
work. **That is the measurement of how much `vol_state` and `atr_bp` overlap** — completely there,
not at all in `7–10`.

**Prediction scored: right that it clears, wrong on where.** Not every bucket; and the largest
*relative* lift is at **15 minutes** for T=1.5 and 2.0 (+8.3%, +13.8%), not 60. Vol clustering shows
up fastest in the tail, the opposite of what was written. The directional clause was right in the
main and wrong in the residue. **Better calibrated than M1, and the same correction applies to both:
mechanism right, location wrong.**

**The lane is alive.** §2 kills it only if M1 finds no positive-EV cell **and** M2 lands inside its
MDE. Neither happened. **The held-out half is still unspent.**

### My honest prediction, written before the run

**I expect M2 to clear its MDE, at all three `T` and all three `H`, with the largest lift at 60
minutes.** Volatility clustering is one of the most replicated facts in empirical finance and it is
the reason ARCHITECTURE §4.4 gave M2 the highest prior of the four. Predicting failure here merely
because M1 and M3 failed would be a fit to this repo's recent mood rather than a belief.

**I expect the effect to be pure scale, with no directional content** — `P(move ≥ +T)` and
`P(move ≤ −T)` should rise together and by similar amounts. That is what makes it consistent with
`horizon.py`'s random walk rather than a contradiction of it.

**And I expect it not to convert.** If the lift is real and I attach any bracket to it, M1's surface
says the cost floor eats it. **The interesting outcome is a large, clean, useless lift** — which
would say the product's forecast has genuine information in it that no trade of ours can harvest,
and that is a product question rather than a research one.

---

## 9 · M1 conditioned on EXPANDING — Varad, committed 2026-09-07

**Due before the conditioned sweep runs.** A ninth. `M2_MAGNITUDE.md` §6 named this run as the
natural next step and said it *"spends more out-of-sample data and should be decided rather than
drifted into"*. **Varad decided it. This block is what makes it a decision rather than a drift.**

Reviewed by Prathamesh.

### The question, and the number that answers it

**Does conditioning M1's geometry sweep on an EXPANDING vol state move any cell from negative EV to
positive EV net of cost?**

The arithmetic is settled before the run and it is one line. `M1_SURFACE.md` measured **gross EV of
−0.0032 ATR** across 3,456 cells against a **cost of +0.0423**. So:

> **Conditioning has to add more than 0.042 ATR of gross EV per leg. Anything less is not a trade,
> however large the lift in `p_target`.**

### The design

```
axis      (atr_bp bucket x vol_state x side)     -- PHASE IS DROPPED, see below
grid      M1's committed 72 points, unchanged    -- precommit §1
states    rv_slope cut at +/-0.20                -- precommit §8
data      TRAINING HALF ONLY, 2025-01..09        -- precommit §6's SPLIT
null      the same cell with vol_state POOLED OUT -- the unconditioned M1 EV, same months
```

- **Phase is dropped and that is a deliberate trade.** `M1_SURFACE.md` §3 established that phase's
  apparent lift is trailing-ATR mis-sizing rather than edge, so a third axis would buy an artefact
  and cost sample: `(bucket × phase × vol_state × side)` is 144 cells against 24, and §3's
  `MIN_SAMPLES = 400` would disqualify most of them on nine months. **Fat cells on the question
  being asked beat thin cells on a question already answered.**
- **Training half only, and the reason is sharper than "step 4 selects".** The decision to condition
  on EXPANDING *at all* was made from M2's training-half result. Running on all 19 months would push
  a choice made on the training half into the held-out half, which is the exact contamination the
  split exists to prevent. **The held-out half stays unspent.**
- **The null is the same cell with `vol_state` pooled out**, so `ev_delta` is what conditioning
  added, on the same months and the same geometry. That comparison, not the raw EV, is the answer.

### The pass line

§1's three conditions unchanged — `n ≥ 400`, `ev_lo > 0`, `p_target > mde_rate(null, n)` — read
with §1's two pre-committed tools: **the side mirror (`ev_sym`) and the `ev_barrier` / `ev_open`
split.** A cell passing on drift or on mark-to-market is not a finding here either.

**Plus one number this run exists to produce: `ev_delta`, the EV added by conditioning.** A cell can
clear the pass line and still have `ev_delta ≈ 0`, which would mean the bucket was already there and
the vol state contributed nothing.

### ✅ ANSWERED 2026-09-07 — it adds +0.004 ATR against a cost of +0.042

Result: [`analysis/M1_EXPANDING.md`](../../services/signal-data/analysis/M1_EXPANDING.md). 1,728
cells, training half, both sides. **Mean `ev_delta` +0.0002 across all cells and +0.0040 for
EXPANDING — short of the cost floor by a factor of ten.** The committed falsification condition
returned **zero cells**.

**The mechanism, measured:**

| | `p_target` | `p_stop` | `p_neither` |
| :--- | ---: | ---: | ---: |
| EXPANDING − CONTRACTING | **+0.0103** | **+0.0162** | −0.0263 |

**Both barriers get hit more and the stop gets hit more than the target**, because the stop is the
nearer barrier at almost every point on the grid. The arithmetic reconciles: at the grid's mean
geometry, `2.04 × (+0.0103) − 0.94 × (+0.0162) = +0.0058 ATR` against an observed +0.0040.
**M2's +0.033 probability lift converts to +0.004 ATR, and the conversion factor is the geometry.**

**The 113 cells above the cost floor are a variance tail**: 121 cells sit symmetrically below
−0.0423, and both tails are the same 101 thin CONTRACTING cells at n ≈ 850. Of the 13 cells passing
§1's line, 5 survive the side mirror and **none of those makes money on trades that closed.**

**Prediction scored: right on the conclusion AND the mechanism** — the first in the track to be
both. The run sharpened it: conditioning is mildly *adverse* on the barrier side, and the small net
positive comes from `p_neither` falling rather than from the target tail.

**What it settles:** *a magnitude edge with no directional content cannot be harvested by a
symmetric bracket.* `vol_state` earns its place in `reach.py`'s key on M2's evidence and **forfeits
any claim to being an entry filter** on this one. An asymmetric exit is a different question and it
is M4's, blocked on `replay.py`.

### My honest prediction, written before the run

**I expect conditioning to add nothing. `ev_delta` ≈ 0 and no cell clears symmetrically.**

**And the mechanism is already measured, which is what makes this a prediction rather than a
mood.** `M2_MAGNITUDE.md` §2 found EXPANDING raises `P(move ≥ +T)` **and** `P(move ≤ −T)` together —
that is what "scale, not direction" means. A bracket has a target on one side and a stop on the
other, so **both barriers get hit more and the EV is unchanged.** That is not a new argument: it is
exactly what `M3_CLOCK.md` §2 measured for `London-NY`, which had the highest `p_target` on the board
and the worst EV, because `p_stop` rose with it.

**So M2's +0.033 lift in reach probability should convert to roughly zero.** If I am right, the
finding is that *a magnitude edge with no directional content cannot be harvested by a symmetric
bracket* — which is a real result about what `PipForecast` can and cannot promise, and it points at
stage 7 rather than at a trade.

**What would falsify it:** a cell where `ev_delta` exceeds +0.042 ATR, survives its side mirror, and
has positive `ev_barrier`. That would mean EXPANDING raises the target tail *more* than the stop
tail at some geometry — an asymmetry M2 did not find at any `T` and would be a genuinely new fact.

---

## 10 · `reach.py` — the served table. Varad, committed 2026-09-09

**Due before the table is built.** A tenth.

**First, a correction to a claim made on 9 Sep: `reach.py` is not blocked on steps 5 and 6.**
`strategy-split.md` §1's own dependency graph is `1 ▶ 2 ▶ 4 ▶ 7` — the serial spine — with 3, 5 and
6 hanging off step 1 as branches. Steps 1, 2 and 4 are done and step 3 delivered the `phase` column.
**Step 5 is a float that unblocks M4, and step 6 adds the second instrument to an axis that already
exists.** Neither gates the GC table.

### The decisions

```
key        (instrument x atr_bp x phase x vol_state x side)   ARCHITECTURE §3 stage 7, verbatim
           GC only for now. The instrument axis is PRESENT and carries one value.
geometry   M1's committed 72 points                            precommit §1
edges      ATR_BP_EDGES                                        precommit §2
phases     Prathamesh's six, in ET                             precommit §4
states     rv_slope cut at +/-0.20                             precommit §8
floor      MIN_SAMPLES = 400                                   precommit §3
data       ALL 19 MONTHS
```

**Why all 19 months, when M2 was training-half only.** `reach.py` **tabulates; it does not select.**
Every threshold above was committed before it ran, the geometry grid is M1's, and the `vol_state`
cut was grounded on a feature distribution carrying no outcome. That is the same licence
`BASE_RATES.md` claims and M1 and M3 used.

**And the table's own validation is forward calibration, not a held-out split.** `calibration.py`
exists to answer *"when it says 61%, does it happen 61% of the time"* on live data — ARCHITECTURE §8
— which is a stronger test than any split of the archive because the trader can check it themselves.
Splitting the archive to validate a table that fits nothing would spend data to buy a weaker answer.

**This does not spend the held-out half for M2's two open questions.** Whether the EXPANDING lift
holds and whether its +0.024 up-tilt is real are tests of a *fitted claim*, and a table that fits
nothing does not contaminate them. **They stay available.**

### Three rules the table has to obey

1. **Below `MIN_SAMPLES`, the answer is null — and NOT a coarser bucket.** No falling back to the
   same cell with `phase` dropped, no pooling to the parent. **A forecast computed from a different
   population wearing this cell's label is the same error class as `has_flow` degrading instead of
   raising**, and it is invisible in the output for the same reason: it looks exactly like the real
   one. `forecast: null` is a valid and common answer (§6.3 rule 3).
2. **Every cell carries the tie band, never a midpoint.** `p_target` and `p_target_max` both, always.
   M1 measured **10.2% of cells undecided** by same-bar ties, and at the tight corner of the grid
   20.45% of bars are wide enough to tie. A single `p` there is a precision the data does not have.
3. **The table is a lookup, not a chooser.** It answers "what happened in this bucket at this
   bracket". It does not pick the bracket. `suggested` is derived from `reach` or it is null.

### ⚠️ Two places the S7 draft and this table disagree — flagged, not silently reconciled

The pipeline design's `PipForecast` is **proposed, not frozen** (§6.3, "not frozen until all three
agree"), and it was drafted against Track A. Two mismatches, for the room:

- **`bucket` is `{regime, atrBucket, horizonBars, n}`.** Track B's key has no `regime` — that axis is
  `regimes.py`, which is parked and does not port to spot — and it has `phase`, `vol_state` and
  `instrument`, which S7 has no field for. **The bucket a trader audits has to be the bucket the
  number came from.**
- **`reach` is `{target, stop, p}[]` — one `p` per bracket.** That cannot express the tie band, which
  rule 2 says is mandatory. It needs `pMax` beside `p`, or the product quotes a number the bars
  cannot support.

**Neither is resolved here.** S7 is a frozen-by-agreement contract and this file is not the place.

### My honest prediction, written before the table is built

**I expect between a third and a half of the 144 cells to clear the 400-leg floor**, and the thin
ones to concentrate where two thin axes cross — `Asia-London` (the shortest phase, one hour) against
the extreme `atr_bp` buckets, in the CONTRACTING and EXPANDING states rather than STABLE.

**I expect the table to be honest and mostly empty at the edges**, which is the correct outcome
rather than a disappointment: 144 cells over ~220,000 legs is ~1,500 each if they were even, and
`M1_SURFACE.md` and the mix table both say they are nowhere near even.

---

## 4 · Session-phase boundaries — Prathamesh, committed 2026-09-06

**⚠️ Committed in ET wall clock, not in UTC — which is a departure from the heading this block
was given, and from the argument written underneath it. That is the one number here that needs
Varad's eye rather than his nod.**

> ## ✅ SIGNED 2026-09-11 by Varad. The ET boundaries stand.
>
> Given verbally in session; **not a logged artefact from the moment**, the same basis rows #2 and
> #8 are closed on and the same way S7's two approvals are recorded. This block asked for one
> person's eye — Varad's — and it has it, so it closes here rather than needing the room.
>
> **The boundaries do not move**, and the review below is the reason it is a decision rather than
> an omission: it was made knowing that `London-NY` at 08:00–09:30 ET contains the 08:30 release
> and is therefore EXPANDING almost by construction, and that `REACH.md` §2 measured the cost of
> that — 16 of 28 dead cells. Frozen in `features/portable.py` as `PHASE_TZ`, `_PHASE_EDGES` and
> `PHASES`; `M3_CLOCK.md`, `M1_SURFACE.md` and `REACH.md` all rest on them and none is invalidated.
>
> *The review as it stood before the signature, kept because it is why the answer means anything:*
>
> **The evidence that arrived after 6 Sep.**
> `REACH.md` §2 measured the two transition phases losing their entire CONTRACTING state — 16 of
> 28 dead cells — because `CONTRACTING` is **4.7%** of `London-NY`'s legs against 28–36% in the
> three phases that are not handoffs. **`phase` and `vol_state` are not independent where they
> cross**, and both boundaries in question are these.
>
> **That is not a reason to move a boundary and this block is not a licence to.** The surface has
> been looked at, so a boundary moved now is a fit — the rule at the bottom of this file. What it
> changes is the *review*: the question is no longer "is ET defensible in principle" but "is ET
> defensible knowing that `London-NY` at 08:00–09:30 contains the 08:30 release and is therefore
> EXPANDING almost by construction". The answer may well still be yes. **It has to be said out
> loud by Varad either way**, because three files of results now depend on it.

### The numbers

```
Asia          18:00 – 02:00 ET     = 22:00 – 06:00 UTC (EDT)  /  23:00 – 07:00 (EST)
Asia-London   02:00 – 03:00 ET     = 06:00 – 07:00 UTC (EDT)  /  07:00 – 08:00 (EST)
London        03:00 – 08:00 ET     = 07:00 – 12:00 UTC (EDT)  /  08:00 – 13:00 (EST)
London-NY     08:00 – 09:30 ET     = 12:00 – 13:30 UTC (EDT)  /  13:00 – 14:30 (EST)
NY            09:30 – 13:30 ET     = 13:30 – 17:30 UTC (EDT)  /  14:30 – 18:30 (EST)
NY-Asia       13:30 – 18:00 ET     = 17:30 – 22:00 UTC (EDT)  /  18:30 – 23:00 (EST)
```

Left-inclusive: 09:30 ET is the first bar of `NY`, not the last of `London-NY`.
Frozen in `features/portable.py` as `PHASE_TZ`, `_PHASE_EDGES` and `PHASES`.

### Why — and the argument this block made for UTC, answered

The block as written said: *"A UTC boundary is stable; a 'London open' that is not pinned to UTC is
not."* **That is true and it is not the property that matters.** A frozen UTC boundary is stable in
its *number* and unstable in its *referent*. 12:00 UTC is 08:00 in New York from March to November
and 07:00 from November to March. Freeze the number and the bucket labelled `London-NY` holds the
NY handoff for seven months of the archive and the middle of the London session for the other five
— **one label, two populations, the average reported as a base rate.** That is §4.6's unit error,
arriving through the clock instead of through the tick, and it is invisible downstream for the same
reason: the table still has six rows and every cell still has an N.

Five of the archive's nineteen months are EST (2025-11 … 2026-03). This is not an edge case.

**On the two supporting facts, which point the other way on inspection.** `s1.SESSION_SHIFT`'s
fixed +2h *is* a summer assumption — and `s1.py`'s own docstring calls it a hole that a real
exchange calendar has to close. It is a known defect, so citing it as precedent generalises the
defect rather than the design. And `ohlcv_edge.py` cutting sessions on gaps **because the break
moves** is the same observation as this one: the market's clock moves in UTC, so a UTC constant
does not track it.

**What it costs, stated plainly:** the UTC instant of a boundary moves twice a year. Nothing
downstream pins on it — `reach.py` consumes the phase *label*, not the boundary — so the cost is
that this table needs two columns instead of one. That is the whole price.

**One accepted imprecision.** London and New York change DST on different dates, ~3 weeks apart in
March and ~1 in November. Inside those windows "London 03:00 ET" is not London's 08:00 local.
Following two zones means two calendars and a phase table that is not one clock; not worth it for
~4 weeks of 19 months, and written down rather than discovered.

### What result makes the phase axis dead

**No phase's `p_target` separates from the ATR-matched, side-matched null by more than that cell's
own `mde_rate`, on both halves of §6's split.** Specifically dead, not merely quiet:

- A phase that clears its MDE on the pooled archive but **changes sign or loses the lift across the
  split** is a description of 2025 and the axis does not survive on it.
- A lift that only appears with the event arm OR'd in is an **event** finding, not a phase finding,
  which is why §5 of `prathamesh/clock-lane.md` pre-commits that all three cuts — phase-only,
  event-only, union — are reported together every run.

If the phase axis is dead, `reach.py`'s bucket key loses one of its four axes and that is a real
result: it makes every surviving cell larger and the `MIN_SAMPLES`=400 problem §3 accepts in advance
correspondingly easier.

### ✅ ANSWERED 2026-09-06 — and the test was the wrong one

Result: [`analysis/M3_CLOCK.md`](../../services/signal-data/analysis/M3_CLOCK.md).

**By the test as written, the phase axis is NOT dead.** `London-NY` clears its own `mde_rate` in
**14 of 16 cells** across both halves and both sides, and survives a ~6x overlapping-leg haircut in
the middle buckets.

**But the test asks the wrong question, and that is recorded here rather than quietly upgraded.** It
asks whether the clock moves `p_target`. It does. It does not ask whether the movement is worth
anything — and it is not: `London-NY` has the highest `p_target` on both sides **and the worst long
EV on the board**, because its `p_stop` rises with it. Best phase net of cost is **−0.83 ticks**.

**A kill condition in this lane must be stated in EV net of cost, not in `p_target` against a null.**
Reach is a property of the bracket; EV is the property of the trade. That correction applies to any
future block in this file.

### My honest prediction, written before the run

**`London-NY` and `NY` carry a magnitude difference that survives; the direction-free `p_target`
lift does not clear MDE in any phase.**

> **Scored 2026-09-06: half right.** `London-NY` does carry the surviving magnitude difference — 14
> of 16 cells. The second clause is **wrong**: the lift clears MDE comfortably. The closing sentence
> below is **right, and for the reason given** — M3's value is bracket conditioning, not entry
> filtering, and the EV table is what proves it. `horizon.py` already measured GC as a directional random
walk at 5/15/30m and `ohlcv_edge.py` reproduced that on spot to within 0.4%. The clock changes how
much gold moves, and I expect it changes almost nothing about which way. If that is right, M3's
value is as a **conditioning axis for the bracket**, not as an entry filter — which is what stage 7
wants from it anyway.

## 5 · The event window — Prathamesh, committed 2026-09-06

**Due before M3 runs.** BLS + FOMC public calendars. Reviewed by Varad.

```
window = 15 minutes either side of a release
```

**Why.** `strategy-architecture.md` §2's table is asymmetric per event — NFP and CPI run 08:25–08:40
(−5/+10), FOMC 14:00–14:30 (0/+30) — and `event_proximity`'s committed signature carries one
symmetric number. ±15 covers the BLS window with margin on both sides and the front half of FOMC's.

**What it costs, and the direction it costs it in:** the back fifteen minutes of the FOMC reaction
land in the non-event population. That **biases against the event arm** — it pollutes the null with
event bars and thins the signal cell. That is the right direction for a number nobody should be able
to talk themselves into.

**The release list is transcribed from BLS and the Fed, never generated** — `calendars.py`,
`reference/us_releases.csv`. The rule "first Friday, 08:30 ET" is wrong on this exact archive in
both directions at once: there is **no October 2025 Employment Situation at all**, September's
landed **2025-11-20**, and September CPI landed **2025-10-24**. A generated calendar marks a quiet
Friday as payrolls *and* leaves the highest-volatility gold bar of that quarter in the null.
`calendars.require_coverage` catches the other half — an uncovered month returns all-False, which is
byte-identical to a genuinely quiet month and is not the same fact.

## 6 · The 2025/2026 split date — Prathamesh, committed 2026-09-06

**Due before M3 runs.** Reviewed by Varad.

```
split at 2025-10  —  train 2025-01…09  against  held 2025-10…2026-07
```

**Why.** **The proposed date is adopted unchanged, and that is the entire justification.**
ARCHITECTURE §4.4 proposes it, `BASE_RATES.md` §3 measured the step at exactly that seam — pooled
monthly `p_target` runs 0.082 before and 0.178 after — and §2's mix table above is the same break
from the other side, with `<7`'s share collapsing from 0.693 in 2025-08 to 0.027 by 2026-03.

As this block already says: adopting the proposed date needs no justification, moving it does. It is
frozen as the module constant `SPLIT` in `m3_profile.py`, **not as a command-line argument**, because
a split date that can be passed at the prompt is a split date that can be tried twice.

---

## 7 · The opening-range length — Prathamesh, committed 2026-09-06

**A fourth, not in the original six.** `features.portable.anchors` computes an opening range, and an
opening range has a length, so it is a threshold and it is committed like the rest rather than
sitting as a literal in a function body.

```
OPENING_RANGE = 30 minutes
```

**Why.** The conventional reading, and it is one `atr_bp` window, which keeps the two comparable.

**Two properties that are the point, not the length.** It is **NaN until the band has closed** — a
bar twelve minutes into the session cannot know the thirty-minute range — and a session shorter than
30 minutes has **no** opening range rather than a partial one, because a 12-minute range reported in
a column labelled 30-minute is a different quantity wearing the same name. And it emits **two**
columns, `opening_range_high` and `opening_range_low`: a band collapsed to its midpoint loses the
only thing it is ever consulted for.

---

## The rule that outlives this file

**A number in here changes only in a commit that says what measurement moved it, and never after
the surface it governs has been looked at.** If that rule and a promising result ever disagree, the
result is the thing that is wrong.
