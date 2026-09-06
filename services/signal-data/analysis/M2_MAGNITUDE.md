# M2 — vol momentum. The clearest signal in the track, and it is about scale.

**Run 2026-09-07 by `m2_magnitude.py`, training half only — 2025-01…09, 9 months.** Step 4 of
[`docs/strategy/ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6, the vol lane of
[`plans/team/strategy-split.md`](../../../plans/team/strategy-split.md). Surface in
[`m2_magnitude.csv`](m2_magnitude.csv).

```sh
PYTHONPATH=. uv run python m2_magnitude.py
```

Every threshold from [`strategy-precommit.md`](../../../plans/team/strategy-precommit.md) §8,
committed **before the driver existed and before anything read a forward move**. `slope_min` was
grounded on `rv_slope`'s own distribution — a feature, no outcome in it — on the training half
alone.

**Step 4 selects, so unlike M1 and M3 this spends out-of-sample data. The held-out half
(2025-10…2026-07) has not been touched.**

---

## 1. The verdict

**An EXPANDING volatility state raises the probability that price travels a given multiple of its
own ATR. The effect is real, small, monotone, and about scale rather than direction.**

`P(|move| ≥ T × ATR within H)`, pooled over buckets, by vol state:

| T | H | CONTRACTING | STABLE | EXPANDING | EXP − CON | relative |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 | 15 | 0.3362 | 0.3320 | **0.3408** | +0.0046 | +1.4% |
| 1.0 | 30 | 0.4760 | 0.4860 | **0.4905** | +0.0145 | +3.1% |
| 1.0 | 60 | 0.6243 | 0.6266 | **0.6399** | +0.0156 | +2.5% |
| 1.5 | 15 | 0.1642 | 0.1690 | **0.1778** | +0.0136 | **+8.3%** |
| 1.5 | 30 | 0.3084 | 0.3133 | **0.3182** | +0.0098 | +3.2% |
| 1.5 | 60 | 0.4736 | 0.4709 | **0.4841** | +0.0104 | +2.2% |
| 2.0 | 15 | 0.0789 | 0.0856 | **0.0898** | +0.0109 | **+13.8%** |
| 2.0 | 30 | 0.1914 | 0.1962 | **0.2001** | +0.0086 | +4.5% |
| 2.0 | 60 | 0.3472 | 0.3450 | **0.3547** | +0.0075 | +2.2% |

- **EXPANDING beats CONTRACTING in 9 of 9.** Nine independent sign tests all landing the same way is
  a 1-in-512 event under a coin flip.
- **EXPANDING beats STABLE in 9 of 9**, and the full ordering
  `CONTRACTING < STABLE < EXPANDING` holds in 6 of 9.
- **17 of the 36 EXPANDING cells clear their own `mde_rate`** at n ≥ 400.

### The comparison that makes this different in kind from M1

**M1 passed 4.6% of 3,456 cells, which is what noise produces. M2 passes 47% of its 36 EXPANDING
cells.** That is not a difference of degree. The two ran through the same power arithmetic, the same
`mde_rate`, the same bucket edges and the same archive.

---

## 2. It is scale, not direction — which is what makes it consistent with `horizon.py`

The pre-commitment named this as the check that keeps the claim honest, because a magnitude finding
that is secretly directional would contradict a result this repo already has.

```
EXPANDING     P(move >= +T) 0.1816     P(move <= -T) 0.1578     gap 0.0238
CONTRACTING   P(move >= +T) 0.1527     P(move <= -T) 0.1557     gap -0.0030
```

**The gap is 7.5% of the hit rate.** Both tails rise together, which is a statement about how far
price goes and not about which way. `horizon.py` measured GC as a directional random walk and
`ohlcv_edge.py` reproduced that on spot to within 0.4%; **M2 does not contradict either, because
only the first was ever tested.** A random walk in direction can have entirely predictable scale.

**⚠️ One residue, flagged rather than smoothed over.** EXPANDING carries a **+0.024 up-tilt that
CONTRACTING does not** (−0.003). Gold rose across the archive, so vol expansions may simply
co-occur with up-moves in a rising market — but that is a hypothesis, not a measurement. **M2 does
not claim a direction and this file does not read one into it.** It is the single most obvious thing
for the held-out half to be asked about.

---

## 3. Where it works, and where it does not

Mean lift over the nine (T, H) combinations, by bucket, with cells clearing MDE:

| bucket | mean lift | cells clearing MDE |
| :--- | ---: | ---: |
| `<7 bp` | +0.0169 | 3 of 9 |
| `7–10 bp` | **+0.0337** | **9 of 9** |
| `10–14 bp` | +0.0292 | 5 of 9 |
| `14+ bp` | **+0.0066** | **0 of 9** |

**The information is in the middle of the volatility distribution and it vanishes at the top.**

That has a reading and it is not a disappointment. `atr_bp` already conditions on the level, so in
the `14+` bucket the bucket has done the work the slope would have done — a bar that is already in
the loudest quartile has little room to be told it is getting louder. **`vol_state` and `atr_bp` are
partly the same information, and this is the measurement of how much.** In the middle two buckets
they are not, and that is where `reach.py` gets a genuinely second dimension out of the pair.

The single largest cell: `10–14 bp · T=1.5 · H=60m`, **`p_hit` 0.4709 against a null of 0.4194 —
lift +0.0516 against an MDE of 0.4457.**

---

## 4. How big it is, said plainly

**Mean lift over the 17 passing cells: +0.033. Over all 36: +0.022.**

Two to five percentage points of probability. That is a real conditioner and it is not a large one.
It is the right size for what §4.4 asked M2 to be — **a second conditioning dimension for stage 7**,
sitting beside `atr_bp` and `phase` — and it is nowhere near the size of thing that survives being
turned into a trade on its own.

---

## 5. The prediction, scored

`strategy-precommit.md` §8, committed before the run:

> **"I expect M2 to clear its MDE, at all three `T` and all three `H`, with the largest lift at 60
> minutes."**
> **Right on the first clause, half wrong on the rest.** It clears — 17 of 36 cells, EXPANDING above
> the null in 9 of 9 pooled combinations. But not in every bucket: the `14+` bucket clears nothing.
> And the largest lift is at 60 minutes only at `T = 1.0`; at `T = 1.5` and `2.0` the **relative**
> lift is biggest at **15 minutes** (+8.3% and +13.8%). Vol clustering shows up fastest in the tail,
> which is the opposite of what I wrote down.

> **"Pure scale, with no directional content."**
> **Right in the main and wrong in a detail that is now on the record.** The gap is 7.5% of the hit
> rate, so the claim is scale — but EXPANDING carries an up-tilt CONTRACTING does not, and I
> predicted none.

> **"I expect it not to convert."**
> **Untested here, by construction.** M2 has no bracket, so this file cannot answer it. §6.

**Better calibrated than M1, where both stated clauses were wrong.** The useful correction is the
same in both: I keep predicting *where* an effect will show up and getting the location wrong while
getting the mechanism right.

---

## 6. What this does and does not license

**Does:**

- **`vol_state` earns its place in `reach.py`'s bucket key**, on evidence, and it is the first axis
  in this track to do so by clearing its own MDE rather than by explaining an artefact.
- **The vol lane is alive.** `strategy-split.md` §2 kills it only if M1 finds no positive-EV cell
  **and** M2 lands inside its own MDE. Neither happened.
- **It says how much `vol_state` and `atr_bp` overlap** — completely in the `14+` bucket, not at all
  in `7–10`.

**Does not:**

- **Make anything tradeable.** M2's output is `P(|move| ≥ T)`, not a trade. The moment it becomes a
  bracket it meets M1's surface, where gross EV is **−0.0032 ATR against a cost of +0.0423**. A
  +0.033 lift in reach probability has to be worth more than that gap before it is a trade, and
  **nothing here has measured whether it is.** The natural next run is M1's sweep conditioned on
  EXPANDING — which spends more out-of-sample data and should be decided rather than drifted into.
- **Survive out of sample yet.** This is the training half. **The held-out 2025-10…2026-07 is
  unspent**, and it is the right place to ask the two questions this file opens: does the lift hold,
  and is the up-tilt real.
- **Explain itself.** That EXPANDING predicts larger moves is consistent with fifty years of
  volatility-clustering literature; nothing here establishes the mechanism on gold specifically, and
  the `14+` result says the effect is partly redundant with a level the pipeline already knows.
