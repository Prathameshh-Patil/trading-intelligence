# M1 — the geometry frontier, measured. The surface is a random walk minus cost.

**Run 2026-09-07 by `m1_sweep.py`, 19 months, both sides, 1h 35m.** *(CSV regenerated 2026-09-10 in
2m 54s — `ff569bb` had added `ev_null`/`ev_delta` after the original run, so the committed file no
longer matched the code that writes it. **Every number published below was re-checked against the
new file and none of them moved**: 3,456 cells, gross EV −0.0032, cost +0.0423, 159 passers, 68
positive after the mirror, 351 undecided, 116 London-NY passers, 49 at 4.0× and 36 at 3.0×. The only
differences are the two added columns and a 1-ULP drift in three derived ones.)* Step 2 of
[`docs/strategy/ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6; the vol lane of
[`plans/team/strategy-split.md`](../../../plans/team/strategy-split.md). Full surface in
[`m1_surface.csv`](m1_surface.csv).

```sh
PYTHONPATH=. uv run python m1_sweep.py
```

**3,456 cells · 72 grid points × 4 `atr_bp` buckets × 6 phases × 2 sides · every cell n ≥ 400.**
Grid, cost floor, pass line, bucket edges and `MIN_SAMPLES` all from
[`strategy-precommit.md`](../../../plans/team/strategy-precommit.md), committed before the sweep
existed. Phase boundaries are Prathamesh's, from the same file. **Nothing in this run chose
anything.**

---

## 1. The verdict

**Gold's bracket geometry carries no premium. The surface is zero, minus the cost of trading it.**

| | ATR per leg |
| :--- | ---: |
| mean gross EV, before cost, all 3,456 cells | **−0.0032** |
| mean cost per leg (1.4 ticks round trip) | **+0.0423** |
| mean net EV (`ev_lo`) | **−0.0455** |
| mean net EV after the side mirror (`ev_sym`) | **−0.0455** |

**Gross EV is −0.0032 ATR — zero to three decimal places — and the entire negative result is the
commission.** That is exactly what `horizon.py` predicted when it measured GC as a random walk at
5/15/30m and `ohlcv_edge.py` reproduced it on spot to within 0.4%. It is the benchmark
[`test_m3_ev.py`](../tests/test_m3_ev.py) names: *EV on a driftless random walk is about zero*.

It does not move anywhere:

```
gross EV by horizon      15m −0.0037   30m −0.0033   60m −0.0026
gross EV by bucket       <7 +0.0007   7-10 −0.0002   10-14 −0.0057   14+ −0.0077
```

Sixteen months of tape, six phases, seventy-two brackets, both sides — and no corner of it pays for
a 1.4-tick round trip.

---

## 2. The committed pass line admits 159 cells. None of them is a finding.

This is reported before the interpretation, because the line was committed and it is not being
moved.

**159 of 3,456 cells (4.6%) clear all three conditions**: `n ≥ 400`, `ev_lo > 0`, and
`p_target > mde_rate(cell_null, n)`. Each condition on its own admits more — `ev_lo > 0` alone
admits 10.1%, `beats_mde` alone 16.8%.

**The pre-commitment named two tools for reading a surface like this, and both were built before the
run. They are what disqualifies the 159, not a new rule invented afterwards.**

### 2.1 The side mirror removes 145 of them

`ev_sym` is the mean of a cell and its opposite side — the only figure a claim about *geometry* is
entitled to, because entering every bar on one side inherits the archive's direction.

| | cells |
| :--- | ---: |
| pass the committed line | 159 |
| …and `ev_sym > 0` | **14** |
| …and the mirror cell **also** passes | **1 geometry** (counted twice, once per side) |

**Across the whole surface only 68 of 3,456 cells (2.0%) are positive after the mirror.** A cell
that pays on one side and loses on the other is the archive's drift wearing a bracket's clothes —
measured on 2026-07 before the run at +0.088 ATR long against −0.095 short.

### 2.2 The barrier/open split removes 13 of the remaining 14

Prathamesh applied this split to M3 the day before and it is the most important qualification on
that page. It does the same work here.

**Of the 14 cells that survive the mirror, 13 lose money on trades that closed.** Their entire EV is
mark-to-market on legs still open at the horizon — and that set is *selected*, since a leg that
never touched a nearby stop is biased toward the target by construction. Mean over the 159 passers:

```
ev_barrier  −0.0802     ev_open  +0.1420      (mark-to-market is 42.3% of |EV| surface-wide)
```

### 2.3 What is left

**One cell**, of 3,456:

```
bucket (7,10] bp · London-NY · long · target 3.0x · stop 0.75x · 60m · n=1,712
ev_barrier +0.0083   ev_open +0.0821   ev_lo +0.0446   ev_sym +0.0005
```

**`ev_sym` is +0.0005 ATR. At the archive's median ATR that is two hundredths of a tick.** It is
one cell out of three thousand four hundred and fifty-six, at a size indistinguishable from zero,
and its own mirror does not pass. **There is nothing here.**

---

## 3. Where the passes concentrate — and it is M3's artefact, not geometry

`London-NY` is **17% of the surface and 73% of the passing cells** (116 of 159).

That is the same phase [`M3_CLOCK.md`](M3_CLOCK.md) §2 diagnosed, and for the same reason. `atr_bp`
looks **backwards** 60 minutes: at 08:00 ET that window covers quiet late-London, so a bracket sized
off it is too small for the 08:30 release and the 09:30 open that follow, and everything resolves.
The signature is in this surface too — **`London-NY`'s mean `p_neither` is 0.164 against 0.264
across the whole grid.**

A bracket that resolves more often, measured against a null pooled over phases that resolve less
often, produces a `p_target` lift. **M1 is rediscovering M3's volatility seasonality, and M3 already
established it converts to no EV.**

The passes cluster at the widest targets — 49 of 159 at `4.0×` and 36 at `3.0×` — which is exactly
where `p_neither` is highest and `ev_open` therefore largest. The two facts are the same fact.

**On contiguity, held to the pre-committed standard.** §1 said a lone grid point inside a flat
surface is a multiple-comparisons artefact while *"a contiguous region clearing it is a finding"*.
The passes **are** contiguous — `London-NY` long in the `(7,10]` bucket passes a solid block at
`target ≥ 3.0×` across all three horizons. **That test is met and it does not rescue the result**,
because the block sits precisely where `ev_barrier` is most negative and `ev_open` largest. It is a
contiguous region of mark-to-market on open positions. The short side's block in the `<7` bucket
sits in the opposite corner of the grid — tight targets, short horizons — which is not what a real
geometry premium looks like; it is what drift plus seasonality looks like.

---

## 4. The tie band

**351 cells (10.2%) are profitable on one tie convention and unprofitable on the other.** They are
flagged `undecided` and none of them passes.

That is not a footnote at this grid. Prathamesh measured 20.45% of bars wide enough to tie at
`0.75×/0.5×` against 0.13% at `3.0×/1.0×` ([`M3_CLOCK.md`](M3_CLOCK.md) §3.2), so at the tight
corner the band *is* the uncertainty. **Those cells stay undecided until step 5's tick replay** —
which is the tie-resolution argument for `replay.py`, standing exactly where he said it stands.

---

## 5. The prediction, scored

`strategy-precommit.md` §1 carried a written prediction, committed 2026-09-06, before any of this
ran. Scored honestly:

> **"I expect no cell to clear the cost floor."**
> **WRONG on the letter.** 159 cells clear it. Not one, not a handful — 4.6% of the surface.

> **"If something does clear it, I expect it at short targets (≤ 1.0×) where `p_target` is high."**
> **WRONG, and wrong in the opposite direction.** The passes concentrate at `3.0×` and `4.0×`, the
> two widest targets on the grid. The reasoning was that a high `p_target` would be eaten by cost;
> what actually happens is that a *low* `p_target` at a wide target leaves most legs unresolved, and
> the mark-to-market on those is what carries the EV.

> **The mechanism behind the prediction — random walk, nothing to pay for the cost.**
> **RIGHT, and it is the finding.** Gross EV −0.0032 ATR across the whole surface.

**Wrong conclusion, right mechanism.** The error was assuming a random walk implies no cell clears
an EV screen; it does not. On 3,456 cells, drift and mark-to-market produce passes at exactly the
rate seen here, and the pre-committed mirror and decomposition are what tell the two apart. **That
is the calibration lesson and it is worth more than having been right.**

---

## 6. What this does and does not license

**Does:**

- **M1's surface is the corrected null M2 is quoted against**, which is what step 2 existed to
  produce. It is on disk, per cell, with N.
- **The cost floor is the binding constraint on this instrument at these geometries**, and it is now
  measured rather than assumed: gross EV zero, net EV −0.0455 ATR, all of it commission.
- **`phase` earns its place in `reach.py`'s bucket key** — for the second time and by a second
  route. Not because it produces edge, but because trailing `atr_bp` mis-sizes the bracket in a
  stable, direction-free, time-of-day-dependent way.

**Does not:**

- **Kill the vol lane.** `strategy-split.md` §2's amended line is *"no cell clears EV − cost > 0 at
  n ≥ 400 **and** M2 lands inside its own MDE"*. Cells do clear it. **M1 does not fire the kill
  condition on the letter, and it is not being reinterpreted to make it fire.** M2 is still owed.
- **Say direction is unpredictable in general.** It says these 72 geometries, entered on every bar,
  do not pay. Nothing here conditions on a signal, because M1 has no entry rule by design.
- **Spend the held-out half.** Nothing here selected, tuned or fitted — the grid was committed
  first — so by `BASE_RATES.md`'s reasoning this cost no out-of-sample data. **The one cell at
  `ev_sym +0.0005` is not worth spending it on.**
- **Settle the tight corner.** 351 cells are undecided by same-bar ties and stay that way until
  `replay.py`.
