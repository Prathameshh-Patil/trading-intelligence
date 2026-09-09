# Stage 7 — the served table. 81% of it is answerable, and the two axes are not independent.

`reach.py`, 19 months, both sides, all 144 cells. Decisions in
[`strategy-precommit.md`](../../../plans/team/strategy-precommit.md) §10, committed 2026-09-09 in
`99ecb6f`, before the file existed. Step 7 of
[`ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6 and the rejoin of
[`strategy-split.md`](../../../plans/team/strategy-split.md) §6.

```
key      (instrument x atr_bp x phase x vol_state x side)
build    6,968s (116 min), 19 months x 2 sides, 207,984 legs
out      analysis/reach_table.csv -- 10,368 rows, 144 cells
```

---

## 1. The verdict

**116 of 144 cells clear the 400-leg floor — 81%.** 8,256 of 10,368 rows are served; the other
2,112 return `None`.

**That is not the shape §10 predicted, and the miss is in the optimistic direction.** The
prediction was a third to a half of the cells, and "honest and mostly empty at the edges". The
table is mostly *full*. §5 scores it.

**Nothing here is an edge, and the table does not claim to be one.** `ev_sym` is positive on 4.4%
of served rows against a median of −0.0421 ATR — which is the cost floor, and which is
[`M1_SURFACE.md`](M1_SURFACE.md)'s "random walk minus cost" arriving again on the same archive.
The pass line fires on 4.0% of rows against M1's 4.6%, already called noise there. **Stage 7
tabulates. It does not choose, and it was never going to produce a finding of its own.**

---

## 2. The finding: `phase` and `vol_state` are correlated, and the bucket key assumes they are not

All 28 dead cells, by where they fall:

```
                  CONTRACTING  EXPANDING  STABLE
Asia-London                 8          0       2
London-NY                   8          2       2
NY                          0          4       0
NY-Asia                     0          2       0
```

**Both transition phases lose their entire CONTRACTING state — 8 of 8 each, 16 of the 28.**

That is not thin sampling. It is a near-empty joint, and it is measurable rather than inferred.
`vol_state`'s share of each phase's legs:

```
              CONTRACTING  EXPANDING  STABLE
Asia                0.282      0.275   0.443
Asia-London         0.100      0.427   0.473
London              0.201      0.198   0.601
London-NY           0.047      0.594   0.359      <- CONTRACTING is 4.7%, EXPANDING is 59.4%
NY                  0.360      0.191   0.449
NY-Asia             0.322      0.132   0.546
```

A 1-hour and a 1.5-hour handoff window is **by construction** a place where volatility is rising.
`London-NY` is 08:00–09:30 ET — it contains the 08:30 release. CONTRACTING runs at 4.7% of its
legs against 28–36% in the three phases that are not handoffs, a six- to sevenfold depletion, and
`Asia-London` at 10.0% is the same effect one notch weaker.

**The two axes are depleting each other where they cross, and the table's key treats them as
independent.** Combined with those two phases being the smallest by leg count anyway — 9,768 and
14,652 against `Asia`'s 64,774 — the joint cell is empty twice over, for two different reasons
that compound.

**This is the third route to the same artefact.** `M1_SURFACE.md` §3 found `London-NY` carrying 73%
of its passing cells off 17% of its surface; `M3_CLOCK.md` §2 found its reach lift not converting
to EV. Both traced it to `atr_bp`'s trailing window sizing the bracket off the quiet hour *before*
the release. This is the same fact seen from the volatility axis instead of the clock: the hour
before a release is quiet, so the hour of the release is EXPANDING almost by definition.

**What it does not license.** It is not a reason to drop an axis or to merge the transition phases.
`strategy-precommit.md`'s standing rule is that a number changes only in a commit naming the
measurement that moved it, and never after the surface it governs has been looked at. This surface
has now been looked at. **Any change to the phase boundaries or the `rv_slope` cut from here is a
fit**, and the honest handling of a dead cell is the `None` the table already returns.

---

## 3. The tie band reproduces M1 independently

```
p_target_max - p_target    mean 0.0062   p50 0.0019   p90 0.0179   max 0.1065
wider than 0.05            1.0% of served rows
`undecided` set on         8.2% of served rows
```

M1 measured 10.2% of cells undecided. **8.2% here, on a different cell partition, from a separate
build.** Rule 2 — every cell carries the band, never a midpoint — costs almost nothing across the
bulk of the table and earns its place entirely at the tight corner, where the max of 0.107 sits.

`p_target` across served rows: p10 0.022, p50 0.203, p90 0.483.

---

## 4. The three rules, as built

1. **Below `MIN_SAMPLES` the answer is `None`, never a coarser bucket.** `lookup` returns `None`
   both when the cell is thin and when the archive has no row at all, and the caller must not
   distinguish them — both are "we do not know". The thinnest cell that clears holds 428 legs; the
   fattest that does not holds 375. Nothing bridges that gap.
2. **Every served row carries `p_target` and `p_target_max`.** §3.
3. **The table is a lookup, not a chooser.** `SERVED` is deliberately `n, p_target, p_target_max,
   p_stop, p_neither` — not `ev_sym`, `ev_lo` or the pass line, which are M1's tools for reading a
   surface and not numbers a trader audits a forecast with.

**The warm-up is ~120 minutes, not 60**, and stage 9 has to budget for it: `vol_state` reads
`rv_slope`, two chained 60-minute windows. A feed that has just connected serves `forecast: null`
for its first two hours. Correct, not broken — and worth saying out loud, because it is otherwise
discovered as "the product does not work at the open".

---

## 5. The prediction, scored

§10, written before the build:

> **I expect between a third and a half of the 144 cells to clear the 400-leg floor**, and the thin
> ones to concentrate where two thin axes cross — `Asia-London` (the shortest phase, one hour)
> against the extreme `atr_bp` buckets, in the CONTRACTING and EXPANDING states rather than STABLE.
> **I expect the table to be honest and mostly empty at the edges.**

| Clause | Result |
| :--- | :--- |
| a third to a half clear | ❌ **81%** — 116 of 144 |
| mostly empty at the edges | ❌ mostly full — 8,256 of 10,368 rows served |
| `Asia-London` among the thinnest | ✅ 10 of 28 dead cells |
| extreme `atr_bp` buckets | ◐ 18 of 28 at the extremes — but the *low* end `(0, 7]` dominates at 12, not the high |
| CONTRACTING and EXPANDING, not STABLE | ◐ CONTRACTING right (16 of 28), STABLE right (4), **EXPANDING wrong** (8) |
| — | ❌ **`London-NY` is the single largest contributor at 12 cells and the prediction never names it** |

**Two things I got wrong, and they are the same mistake.** I predicted density from leg count
alone — shortest phase, thinnest buckets — and the archive is much larger than that reasoning
assumed, so the floor is easy nearly everywhere. What actually kills a cell is not being small; it
is **the two axes interacting**, which the prediction did not consider at all. `London-NY` is 50%
larger than `Asia-London` and loses *more* cells.

---

## 6. What this licenses

- **Stage 9 can be built against this table.** The GC half of `PipForecast.bucket` is served, with
  a `None` path that is exercised on 19% of the grid rather than theoretical.
- **The two S7 seam mismatches stand and are for the room**, not for this file: `PipForecast.bucket`
  carries `regime`, which is `regimes.py` and parked, and has no field for `phase`, `vol_state` or
  `instrument`; and `reach` is `{target, stop, p}[]`, which cannot express the band §3 makes
  mandatory. `strategy-precommit.md` §10 flagged both before the build; the build changed neither.
- **The `instrument` axis carries one value and is present.** A spot table appends without touching
  a line of `reach.py`, which is what step 1's seam was for.
- **It does not license a kill call on the track.** §2's rule: the surface has been looked at, so
  the thresholds are frozen from here.

---

## 7. One engineering note, measured not guessed

The build took 116 minutes, and `backtest.first_touch` is effectively all of it:

```
5,536 legs x 72 grid points x 2 tie modes = 797,184 leg iterations per (month, side)
6,968s / 38 month-sides / 797,184         = ~188 us per iteration
```

188 µs is pandas-per-row overhead, not arithmetic. Each pass rebuilds a `bars.loc[t:mark]` slice, a
session mask, and two `.to_numpy()` calls — and `session_ends(bars)` is recomputed on every one of
the 8,208 calls per month-side rather than once. **The window depends only on `(t, side, horizon)`,
not on `target` or `stop`**, so with 3 horizons and 144 calls per cell it is rebuilt 48 times to
answer 48 questions that read the same two arrays.

Fixable by hoisting the window out of the grid loop. **Deliberately not done in this commit**:
`first_touch` is shared machinery, and `bd675f5` is on the record that a second first-touch
convention is how two files quietly disagree about what a leg is worth. `reach_table.csv` as
committed here is the reference any faster version has to reproduce byte for byte.
