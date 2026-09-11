# M4b — path ordering. Bars can sequence MFE against MAE 95.8% of the time, so the PDE premise is weak.

`replay.py --what path`, 19 months, all 327,135 legs. Step 5's second question —
[`ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6 step 5 is *"intrabar ordering —
unblocks M4b"*. **Prediction and kill condition committed in
[`strategy-precommit.md`](../../../plans/team/strategy-precommit.md) §11 (`d648938`), before the
first line of the code that reads them.** Budget: 3 days.

```
question     can a 5-minute bar say whether MFE came before MAE?
unorderable  both extremes fall in the SAME bar -- the bar has no sequence to offer
build        155s, 19 months, checkpointed per month
out          analysis/replay_path.csv -- per month x cell x side x horizon
```

---

## 1. The verdict

**13,744 of 327,135 legs have MFE and MAE in the same bar — 4.20%. The other 95.8% are ordered by
the bars themselves.**

§11's kill condition reads on that number: *"under 10% unorderable and the PDE premise is weak —
bars already carry the sequence, no tick replay is needed to act on it, and the reason M4b was
blocking M4 disappears."* **It fires.**

**What this is evidence for:** deciding M4's path-dependent candidate against, on the grounds that
its blocker was never really there. **What it is not:** a finding that path information is
worthless. Bars carry the sequence; whether the sequence pays is `strategy-architecture.md`'s own S4
gate — *"EV improvement < 10% vs. fixed → use static brackets"* — which needs the rules built and a
threshold nobody has committed, and is not this measurement.

---

## 2. The prediction, scored — and it is not a clean pass

§11 predicted **fewer than 10%**, reasoning that a leg's window is 3, 6 or 12 bars and the two
extremes should usually land in different ones simply because there are several.

| Horizon | Legs | Unorderable | Rate | |
| :--- | ---: | ---: | ---: | :--- |
| pooled | 327,135 | 13,744 | **4.20%** | ✅ |
| 15m | 110,721 | 11,242 | **10.15%** | ❌ **over the line** |
| 30m | 109,464 | 2,111 | 1.93% | ✅ |
| 60m | 106,950 | 391 | 0.37% | ✅ |

**The pooled prediction is right and the 15-minute horizon breaches it**, by 0.15 pp. Recorded as a
miss rather than rounded to a pass, because **15m is exactly where a PDE rule would live** — S4's
own conditions are *"`mae > 0.6 * stop` in the first 5 bars"* and *"`speed_to_mfe < 5 bars`"*, and
five bars is 25 minutes.

**The reasoning behind the prediction was right and the arithmetic was the miss.** A 15-minute
horizon at 5-minute bars is **three** bars, not several — and with three bars, two extremes landing
in the same one is not a tail event. §11 wrote "3, 6 or 12 bars" and then reasoned as though the
number were always large.

---

## 3. What was measured is ORDERING, not magnitude, and that was fixed before the run

`backtest.evaluate` takes MFE from `leg["high"].max()`. **A bar's high IS the maximum tick price
inside it**, so bar MFE and tick MFE are the same number and no replay can improve it. §11 committed
to this before the run so the write-up could not drift into claiming a magnitude correction.

**Verified rather than argued:** `excursions`-derived MFE and MAE equal `evaluate`'s to
**`0.00e+00`** at all three horizons across 18,345 legs, by independent code paths. That agreement
is what licenses using `excursions` for the path question at all.

What a bar cannot carry is **when**, and therefore in what order — which is what every PDE rule
reads, since *retracement after MFE* and *MAE in the first five bars* are both sequence claims.
`features/regime_filter.py` named this in advance as *"exactly what D4 must measure at tick
resolution"*.

---

## 4. The finding: there is no conditioning structure

§11 anticipated a middle case — *"between the two it is a conditioning question, not a verdict, and
the per-cell table says where."* **The table says there is no where.**

Over the 63 non-thin cells at 15m the unorderable rate spans **7.13% to 12.89% — 1.81×**. The axis
marginals are nearly flat:

```
bucket      9.40% ((14.0, inf])  ..  10.89% ((0.0, 7.0])
phase       9.00% (NY)           ..  11.05% (NY-Asia)
vol_state   9.77% (EXPANDING)    ..  10.33% (CONTRACTING)
```

**Real and small are different claims, so both are tested.** Against a single common rate the cells
give **χ² = 186.7 on 62 dof — 3.01 per cell**, with 6 of 63 beyond ±3 SE. The variation is not
sampling noise. **The magnitude is what decides it**, and the comparison is on the same archive from
the same module:

```
tie rate, 72 brackets (step 5)     0.014%  ..  3.97%     276x
unorderable, 63 cells (M4b)         7.13%  .. 12.89%     1.8x
```

Step 5 found a quantity that concentrates hard — 0.75/0.50 alone carries 26.6% of every tie. This
one does not. **So a path-dependent rule cannot be rescued by restricting it to a pocket where bars
are blind, because there is no such pocket.** That strengthens §1's verdict rather than complicating
it.

**The worst cell is the warm-up.** Legs with no `atr_bp` — inside `reach.cell_of`'s ~120-minute
window — are labelled `unclassified` rather than dropped, are 1.93% of legs, and run 12.87% at 15m.
They sit near the session open. Dropping them would have moved the denominator and made §1's 4.20%
irreproducible from this table.

---

## 5. ⚠️ `side` is a relabelling, and this module has now produced that artefact twice

**A long and a short entered on the same bar read the same two prices.** The bar's high is the
long's favourable extreme and the short's adverse one. So:

```
unorderable          identical across sides, every month x horizon
long  mfe_first  ==  short mae_first     exactly
long  mae_first  ==  short mfe_first     exactly
```

**The ordering carries one number — did the high come before the low — and pooling the sides forces
it to 50/50.** Reported once, from the long leg's view:

```
horizon   unorderable   high-before-low
   15m         11,242        50.9%
   30m          2,111        55.1%
   60m            391        62.1%
```

This is [`REPLAY.md`](REPLAY.md) §4's symmetric-bracket artefact arriving a second time inside the
same module, and it is worth stating as a property of these measurements rather than as two
coincidences: **wherever a quantity is defined relative to the trade's own direction, pooling the
two sides reports one observation twice and forces any ratio to 0.5.** Both `path_summary` and
`by_cell` drop `side` rather than summing it, and a test asserts each does.

---

## 6. What this does not settle

- **No PDE rule is implemented and none is proposed.** §11 is explicit that S4's five thresholds —
  `speed_to_mfe < 5 bars`, `mfe > 1.5 * ATR`, `retracement > 0.8 * mfe` — are invented constants
  wearing the word pre-committed, and that M4b implements none of them.
- **`backtest.py` is untouched**, as in step 5.
- **M4 is not decided here.** `strategy-reconciliation.md` §415 orders M4 after tick replay *and*
  route-2 spot, and spot is blocked on the Dukascopy IP block (`plans/current.md` R7). This removes
  one of the two blockers and supplies evidence for the decision; it does not make it.
- **The 15m breach is a real result, not a rounding.** Any rule operating on a 3-bar window is
  reading a sequence bars cannot give it one time in ten.
