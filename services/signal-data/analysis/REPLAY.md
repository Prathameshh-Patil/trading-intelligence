# Step 5 — tick replay. The nearer barrier wins, and the tie rule only knows that when the stop is nearer.

`replay.py`, 19 months, both sides, all 72 brackets. Step 5 of
[`ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6 and
[`strategy-split.md`](../../../plans/team/strategy-split.md) §5, whose constraints are the shape of
this module: **it ships standalone, it produces an intrabar ordering table, and it does not change
`backtest.first_touch`.** Time budget set in that file before the first line was written: 3 days.

```
population  the legs first_touch_from resolves BY RULE -- both barriers first
            cleared in the same 5-minute bar, where the bar carries no order
build       127s, 19 months, checkpointed per month
out         analysis/replay_ties.csv -- per month x cell x bracket
```

---

## 1. The verdict

**89,646 ties over 14,736,048 leg-brackets — 0.61%. The tape ordered every one of them. The rule
sends all 89,646 to the stop; the tape sends 37,301, or 41.6%, to the target.**

That headline is true and it is the least useful number in this file, for two reasons that §3 and
§4 give. Read those before quoting it.

**What it licenses is narrow.** Every `p_target` in this repo is a stated lower bound because ties
resolve to the stop; this measures how much is under that bound and where. It is **not** a claim
that any `p_target` should move. Moving one is a change to `backtest.first_touch`, which is a
shared-spine change with Track A's tests as the gate, it is Varad's, and §5 says it happens *only if
the number here says it is worth making*.

---

## 2. It reconciles with `reach_table.csv` to the unit, and the target was fixed first

`reach.py` pools counts across months and serves `p_target` beside `p_target_max`, so the legs the
rule flips are `(p_target_max − p_target) × n`, summed over all 10,368 rows:

```
reach_table.csv   89,646        largest distance from an integer: 6e-13
replay.py         89,646
```

Two completely different paths — one flips the rule and counts the difference, the other walks the
tape and finds the legs the rule is applied to. **The expected number was computed and written down
while the run was still on month 12**, which is the only version of this check worth anything.

---

## 3. The finding: the nearer barrier is touched first

Ties are not a coin flip and they are not a constant. `P(target first)` is **monotone in the
stop/target ratio**, over three and a half orders of magnitude of tie count:

```
stop/target   ties    P(target first)
  0.125        269         0.178
  0.167        653         0.219
  0.250      2,775         0.241
  0.333      4,923         0.277
  0.500     16,958         0.337
  0.667     25,668         0.391
  0.750      7,535         0.430
  1.000     17,592         0.500        <- forced, see §4
  1.333      6,862         0.574
  1.500      1,834         0.571
  2.000      2,766         0.649
```

**The tape says what geometry predicts: whichever barrier is closer to the entry is usually the one
touched first.** That is the sensible null and it is satisfying rather than surprising — it is what
this measurement *should* find if the walk is sound, and it is evidence the walk is sound.

**The consequence for the rule is the point.** `ties="stop"` is a blanket answer to a question whose
answer depends on the bracket. It is roughly right where the stop is nearer, exactly a coin flip at
symmetry, and **wrong more often than right wherever the target is nearer** — 10 of the 72 brackets,
holding 11,593 ties, 12.9% of the archive's.

**It remains the correct conservative choice** and nothing here argues otherwise. `p_target` as a
lower bound is a property nobody has to remember; a per-bracket correction is a number somebody has
to keep true. That trade is the room's, not this file's.

---

## 4. ⚠️ The symmetric brackets carry no information, and they look like they do

**At `target == stop` the pooled split is exactly `0.500000`. Every time, at all three symmetric
brackets, on 17,592 ties — 19.6% of the archive's.**

It is forced by construction, not measured:

```
0.75/0.75, horizon 30       ties   target_first   stop_first
  short (-1)                2117           1088         1029
  long  (+1)                2117           1029         1088
```

A long and a short entered on the same bar with equidistant barriers are the *same two price
levels*. Whichever prints first is the target for one side and the stop for the other, so pooling
the two sides can produce nothing but 0.5. The mirror is exact at all three: 0.75/0.75, 1.0/1.0 and
1.5/1.5.

**This was nearly written up as "ties are a coin flip".** It is arithmetic, not tape, and it is the
same class of error `M3_CLOCK.md` §4 records twice — every component right in isolation, wrong in
composition. **Any per-bracket number from this table must be read per side, or at a bracket where
the two sides are not mirrors.**

Per side, pooled over everything:

```
short (-1)   45,950 ties   42.4% to target
long  (+1)   43,696 ties   40.8% to target
```

Close, and not identical — so the pooled 41.6% is not *purely* an artefact. Only the symmetric
brackets are.

---

## 5. Where the ties are

**They concentrate hard.** The tie rate spans **0.014% to 3.97%** across the 72 brackets, a 276×
range, and the single tightest bracket carries more than a quarter of everything:

```
0.75 / 0.50, all three horizons   23,834 ties   26.6% of the archive's
the four tightest brackets                      31.4%
```

This is `M1_SURFACE.md`'s tie observation arriving from the archive rather than from one month: a
tie needs one bar to span both barriers, which needs the bracket to be narrow relative to the bar.
Nothing here is new — it is the same fact measured at tick resolution instead of asserted.

**Ties are not photo-finishes.** The median gap between the two touches is **153 seconds**, inside a
300-second bar. The bar's inability to order them is not a precision problem; the two events are
genuinely minutes apart and the bar simply does not record when.

---

## 6. `unresolved` is zero, and that is explained rather than assumed

Three ways the tape can decline to order a tie are implemented and unit-tested: two prints sharing a
nanosecond, a barrier the bar clears but the window's own prints never reach, and a print outside
the tied bar. **None fired, across 14,736,048 leg-brackets.**

That is not a dead branch. 201,703 of 2026-07's 1,616,772 prints share a nanosecond with another —
12.5% — so the first path is reachable in principle. It needs a move of a full bracket width inside
one nanosecond, which does not happen on this tape. The branch stays, and it stays tested, because
the day it does fire is the day something is wrong upstream.

---

## 7. What this does not settle

- **No `p_target` moves.** §1. The change to `first_touch` is Varad's and only if this earns it.
- **M4b is still open.** The Path-Dependent Exit needs the intrabar ordering of MFE against
  retracement, which `strategy-reconciliation.md` §415 and `strategy-precommit.md` both say is
  blocked on this module. **The tape walk that answers it is now written**; the pass over the same
  window is small. It was left out deliberately rather than absorbed, because the budget is three
  days and §4's correction is worth more than the extra scope.
- **Spot is untouched.** This is GC tape. Whether the ratio relationship in §3 holds on a spot feed
  is step 6's question, and step 6 is blocked on data (`plans/current.md` R7).
