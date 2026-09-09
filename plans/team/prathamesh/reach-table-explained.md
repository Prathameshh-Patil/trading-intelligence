# The reach table, explained — for Prathamesh

Varad, 2026-09-10. The full result is
[`analysis/REACH.md`](../../../services/signal-data/analysis/REACH.md). This file is the plain
version with code you can run. **Your `phase` column is half of this table**, and the one real
finding is about what happens where your axis crosses mine — so §4 is the part that is actually
yours.

---

## 1. What the thing is, in one paragraph

The table answers exactly one question, and it is a *lookup*, like a phone book:

> "Right now it is 10:15 in New York, gold is moving about 8 bp an hour, and volatility is flat.
> If I put a target 1 ATR away and a stop 0.75 ATR away and give it 30 minutes — **how often did
> the target come first, historically, in this exact situation?**"

It does **not** tell you to trade. It does not pick the target, the stop, or the side. It reports
what happened on 207,984 legs over 19 months, sliced into 144 situations.

Run this — it is the whole product in six lines:

```python
import pandas as pd, reach

table = pd.read_csv("analysis/reach_table.csv")
cell  = reach.Cell("GC", "(7.0, 10.0]", "NY", "STABLE", 1)   # <- the situation
print(reach.lookup(table, cell, target_atr=1.0, stop_atr=0.75, horizon=30))
```

```python
{'n': 1526.0,               # 1,526 real legs are behind this answer
 'p_target': 0.364,         # target came first 36.4% of the time
 'p_target_max': 0.370,     # ...37.0% if you resolve same-bar ties the kind way
 'p_stop': 0.523,           # stop came first 52.3%
 'p_neither': 0.113}        # neither, ran out of clock 11.3%
```

That is it. Five numbers and the count they came from.

---

## 2. The five parts of a `Cell`

```python
reach.Cell("GC", "(7.0, 10.0]", "NY", "STABLE", 1)
#           |     |              |     |         |
#           |     |              |     |         +-- side: +1 long, -1 short
#           |     |              |     +------------ vol_state: mine (rv_slope)
#           |     |              +------------------ phase: YOURS
#           |     +--------------------------------- atr_bp bucket: mine
#           +--------------------------------------- instrument (only "GC" today)
```

4 buckets × 6 phases × 3 states × 2 sides = **144 cells**. Each cell holds 72 brackets
(6 targets × 4 stops × 3 horizons), so 10,368 rows.

You never build a `Cell` by hand in the live path. `cell_of` does it from bars, using the same
feature code the build used:

```python
keys = reach.cell_of(bars, GC)     # one Cell (or None) per bar
keys.iloc[-1]                      # -> Cell(instrument='GC', bucket='(7.0, 10.0]', ...)
```

**Why the same code matters:** if the live path spelled the phase `"london-ny"` and the build spelled
it `"London-NY"`, every lookup would miss and the product would return `null` on every bar — which
looks identical to an honest empty table. There is a round-trip test asserting they spell it the
same.

---

## 3. `None` is a real answer, and it happens 19% of the time

```python
dead = reach.Cell("GC", "(0.0, 7.0]", "Asia-London", "CONTRACTING", 1)
reach.lookup(table, dead, target_atr=1.0, stop_atr=0.75, horizon=30)   # -> None
reach.reach(table, dead, horizon=30)                                   # -> []
```

Fewer than 400 legs live in that cell, so **the table refuses to answer**. It does *not* quietly
widen the bucket and answer from a bigger population.

This is the rule most worth internalising, because breaking it is invisible:

```python
# WHAT WE DO NOT DO -- and this is the whole point
def lookup_bad(table, cell, **kw):
    hit = lookup(table, cell, **kw)
    if hit is None:
        hit = lookup(table, drop_phase(cell), **kw)   # "close enough"
    return hit
```

`lookup_bad` never returns `None`. It always has a number, the number always looks plausible, and
**it is computed from a different population than the label says.** A trader auditing "why 36%?"
gets an answer that cannot be checked. Same failure class as `has_flow` returning a default instead
of raising — you cannot see it in the output.

`forecast: null` is normal, common, and correct.

---

## 4. The finding — and it is about your axis meeting mine

**116 of 144 cells clear the 400-leg floor (81%).** The 28 that do not are not scattered:

```
                  CONTRACTING  EXPANDING  STABLE
Asia-London                 8          0       2
London-NY                   8          2       2
NY                          0          4       0
NY-Asia                     0          2       0
```

**Your two transition phases lose their entire CONTRACTING state — 8 of 8 each.**

The instinct is "those are the short phases, of course they are thin". **That is not the reason,
and you can check it in four lines:**

```python
cells = table.groupby(reach.KEY)["n"].max().reset_index()
p = cells.pivot_table(index="phase", columns="vol_state", values="n", aggfunc="sum")
print((p.div(p.sum(axis=1), axis=0)).round(3))    # each phase's mix of vol states
```

```
              CONTRACTING  EXPANDING  STABLE
Asia                0.282      0.275   0.443
Asia-London         0.100      0.427   0.473
London              0.201      0.198   0.601
London-NY           0.047      0.594   0.359     <-- look at this row
NY                  0.360      0.191   0.449
NY-Asia             0.322      0.132   0.546
```

In `NY`, `NY-Asia` and `Asia`, CONTRACTING is 28–36% of the legs. In `London-NY` it is **4.7%**.

**Why: your `London-NY` is 08:00–09:30 ET, so it contains the 08:30 release.** The hour *before* a
release is quiet, so the hour *of* it is EXPANDING almost by definition. A handoff window is a
place where volatility is rising by construction. The axes are not independent — they deplete each
other exactly where they cross, and the bucket key assumes they don't.

`Asia-London` is the same effect one notch weaker (10.0%). And note `London-NY` carries **50% more
legs** than `Asia-London` yet loses *more* cells — which is how you know size is not the mechanism.

**This is your artefact, found a third time.** `M1_SURFACE.md` §3 saw `London-NY` take 73% of the
passing cells off 17% of the surface. Your `M3_CLOCK.md` §2 saw its reach lift not convert to EV.
Both traced it to `atr_bp` sizing the bracket off the quiet hour before the release. This is the
same fact seen from the volatility axis instead of the clock.

**What we are NOT doing about it:** not moving your phase boundaries, not moving the `rv_slope` cut,
not merging the transition phases. The surface has been looked at now, so a threshold moved from
here is a fit, not a fix. `strategy-precommit.md`'s standing rule, and it applies to me as much as
to you. The dead cells stay dead and return `None`.

---

## 5. What the table does *not* say

`ev_sym` is positive on 4.4% of served rows; the median is **−0.0421 ATR**, which is the cost floor.
The pass line fires on 4.0% against M1's 4.6% that we already called noise.

**There is still no edge in this track, and stage 7 was never going to find one** — it tabulates,
it does not select. What it gives us is a served surface with an honest `None` path, which is what
stage 9 needs to be built against.

---

## 6. Two things to know before you wire anything to it

**The warm-up is two hours, not one.**

```python
reach.cell_of(bars, GC).iloc[:24]    # all None on a freshly-connected feed
```

`vol_state` reads `rv_slope`, which compares this hour's Parkinson volatility to the *previous*
hour's — two chained 60-minute windows. A feed that just connected serves `forecast: null` for
~120 minutes. Correct, not broken. Worth knowing now rather than discovering it as "the product
does not work at the open".

**Every answer carries a band, never a midpoint.**

`p_target` resolves a same-bar tie (one bar's high clears the target *and* its low clears the stop)
to the stop; `p_target_max` resolves it to the target. The truth is between them and bar data
cannot say where. It is usually tiny — median 0.0019, so 36.4% vs 37.0% above — but it reaches
0.107 at the tight corner of the grid. Quote both or quote neither.

---

## 7. The seam mismatch that needs all three of us

`PipForecast` in the S7 draft does not fit this table, in two places. Flagged before the build,
unchanged by it, and **not resolved by me** — S7 is frozen-by-agreement:

- `PipForecast.bucket` is `{regime, atrBucket, horizonBars, n}`. There is no `regime` here — that is
  `regimes.py`, which is parked and does not port to spot — and there is no field for `phase`,
  `vol_state` or `instrument`. **The bucket a trader audits has to be the bucket the number came
  from.**
- `reach` is `{target, stop, p}[]` — one `p` per bracket, which cannot carry `p_target_max`.

Both need a room decision, not a patch.

---

## 8. Try it yourself

```bash
cd services/signal-data
PYTHONPATH=. uv run python -c "
import pandas as pd, reach
t = pd.read_csv('analysis/reach_table.csv')
c = reach.Cell('GC', '(7.0, 10.0]', 'London', 'STABLE', -1)   # short, London, calm
for r in reach.reach(t, c, horizon=30)[:5]:
    print(r)
"
```

`reach()` returns every bracket that cell can answer at one horizon and silently omits the thin
ones — so an empty list means the cell is dead, not that the call failed.

Rebuilding the table from scratch is `PYTHONPATH=. uv run python reach.py`, about 116 minutes. It
checkpoints per `(month, side)` into `analysis/.reach_cache/`, so an interrupted run resumes in
seconds, and the cache is stamped with the six parameters it was built under and refuses to load
against a changed grid or changed bucket edges.
