# M1 conditioned on EXPANDING — a magnitude edge a symmetric bracket cannot harvest

**Run 2026-09-07 by `m1_sweep.py --axis vol_state`, training half only — 2025-01…09, both sides,
~40m.** [`strategy-precommit.md`](../../../plans/team/strategy-precommit.md) §9, committed in
`2c781c2` before the driver was changed. Surface in [`m1_expanding.csv`](m1_expanding.csv).

```sh
PYTHONPATH=. uv run python m1_sweep.py --axis vol_state \
  --months 2025-01 … 2025-09 --out analysis/m1_expanding.csv
```

**1,728 cells — 72 grid points × 4 `atr_bp` buckets × 3 vol states × 2 sides. Every cell n ≥ 400.**
The held-out half (2025-10…2026-07) was not touched.

---

## 1. The verdict

**Conditioning on an EXPANDING vol state adds +0.004 ATR per leg. The cost floor is +0.0423. It is
short by a factor of ten.**

`ev_delta` — what conditioning added, against the same cell with `vol_state` pooled out, on the same
months and the same geometry:

| | mean `ev_delta` | mean `ev_lo` | mean `ev_barrier` | mean `ev_open` |
| :--- | ---: | ---: | ---: | ---: |
| CONTRACTING | −0.0006 | −0.0524 | −0.1130 | +0.1114 |
| STABLE | −0.0028 | −0.0546 | −0.1155 | +0.1106 |
| **EXPANDING** | **+0.0040** | **−0.0479** | −0.1092 | +0.1092 |
| **all 1,728 cells** | **+0.0002** | | | |

**EXPANDING is genuinely the best of the three states.** It is also the best by **one tenth of what
a round trip costs.** M2's lift is real, it survives into the bracket, and it is an order of
magnitude too small to pay for itself.

**The committed falsification condition returned zero.** §9 said the prediction would be wrong if any
cell showed `ev_delta > +0.0423` **and** `ev_sym > 0` **and** `ev_barrier > 0`. **No cell meets all
three.** 13 cells pass the §1 pass line; 5 survive the side mirror; **none of those 5 makes money on
trades that closed.**

---

## 2. Why — and the mechanism is measured, not argued

This is the number the run existed to produce:

| | `p_target` | `p_stop` | `p_neither` |
| :--- | ---: | ---: | ---: |
| CONTRACTING | 0.2222 | 0.4819 | 0.2958 |
| EXPANDING | 0.2325 | 0.4981 | 0.2695 |
| **EXPANDING − CONTRACTING** | **+0.0103** | **+0.0162** | **−0.0263** |

**Both barriers get hit more, and the stop gets hit more than the target.**

That is what "scale, not direction" costs when you attach a bracket to it. The extra movement M2
found has no preferred sign, so it distributes across the two barriers roughly in proportion to how
close they are — and **the stop is the nearer one at almost every point on M1's grid** (stops run
0.5–1.5× ATR, targets 0.75–4.0×). A non-directional increase in how far price travels therefore
lands disproportionately on the side you did not want it to.

The arithmetic reconciles to the observed number. At the grid's mean geometry — target 2.04×, stop
0.94× —

```
dEV  =  T x dp_target  -  S x dp_stop
     =  2.04 x (+0.0103)  -  0.94 x (+0.0162)
     =  +0.0210  -  0.0152  =  +0.0058 ATR
```

against an observed `ev_delta` of **+0.0040** for EXPANDING, the small remainder being the shift in
`ev_open` as `p_neither` falls. **The +0.033 probability lift M2 measured converts to +0.004 ATR,
and the conversion factor is the geometry.**

**This is the same fact `M3_CLOCK.md` §2 measured from the other side.** `London-NY` had the highest
`p_target` on the board and the worst EV, because `p_stop` rose with it. M3 found it in the clock;
M1-conditioned finds it in the vol state. **Two different conditioners, one mechanism: anything that
makes the tape move more resolves both barriers, and a symmetric bracket is indifferent to it.**

---

## 3. The 113 cells above the cost floor are a variance tail

6.5% of cells show `ev_delta > +0.0423`. That looks like a result until it is read against its
mirror image:

| | cells | by state |
| :--- | ---: | :--- |
| `ev_delta` > **+**0.0423 | 113 (6.5%) | CONTRACTING 101 · EXPANDING 11 · STABLE 1 |
| `ev_delta` < **−**0.0423 | 121 (7.0%) | CONTRACTING 101 · STABLE 13 · EXPANDING 7 |

**A near-symmetric two-sided tail, and both sides are the same 101 CONTRACTING cells.** Those live
in the `14+ bp` bucket at n ≈ 850 — the thinnest cells in the run, sitting just above the
`MIN_SAMPLES` floor, where the variance on `ev_delta` is largest. **It is dispersion, not signal**,
and only 19 of the 113 have positive `ev_barrier` at all.

The 13 cells that pass the §1 line are the same story as `M1_SURFACE.md`: mean `ev_barrier`
**−0.1437** against mean `ev_open` **+0.2088**. Every one of them loses on closed trades.

---

## 4. The prediction, scored

`strategy-precommit.md` §9, committed before the run:

> **"I expect conditioning to add nothing. `ev_delta` ≈ 0 and no cell clears symmetrically."**
> **Right.** Mean `ev_delta` +0.0002 across all cells, +0.0040 for EXPANDING. Zero cells meet the
> falsification condition.

> **"EXPANDING raises `P(move ≥ +T)` and `P(move ≤ −T)` together, so both barriers get hit more and
> the EV is unchanged."**
> **Right, and the run sharpened it.** The stop is hit **more** than the target — +0.0162 against
> +0.0103 — because it is the nearer barrier. Conditioning on EXPANDING is mildly **adverse** on the
> barrier side, and the small net positive comes from `p_neither` falling rather than from the
> target tail.

**This is the first prediction in the track that was right on both the conclusion and the
mechanism.** M1's was wrong twice with the mechanism right; M2's was right that it clears and wrong
about where. The difference is that this one was derived from two prior measurements rather than
from a prior — which is the thing to keep doing.

---

## 5. What this settles

**The finding, stated as a fact about the product rather than about gold:**

> **A magnitude edge with no directional content cannot be harvested by a symmetric bracket.**
> It is real — M2 measured it at 9 of 9 — and it belongs in a forecast, not in a trade.

That is not a disappointment; it is what `PipForecast` was designed to sell. ARCHITECTURE §4.4 asked
M2 to be *"a second conditioning dimension for stage 7"*, and this run confirms that is the **only**
thing it can be. `vol_state` earns its place in `reach.py`'s bucket key on M2's evidence and
**forfeits any claim to being an entry filter** on this one.

**Does not:**

- **Kill the vol lane.** `strategy-split.md` §2 requires no positive-EV cell **and** M2 inside its
  MDE. Neither happened, and this run does not change either.
- **Say the conversion is impossible in general.** It says a **symmetric bracket** cannot harvest
  it. An asymmetric exit — trailing, time-based, or path-dependent — is a different question, and it
  is M4's, blocked on `replay.py` and not on data.
- **Spend the held-out half.** Training only, and this is now the second result pointing at the same
  held-out question: does the EXPANDING lift hold out of sample, and is its +0.024 up-tilt real.
