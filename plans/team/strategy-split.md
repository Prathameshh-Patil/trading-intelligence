# Strategy track — the two-lane split

**Written 2026-09-06.** Scope: the **Track B strategy programme only**, as specified by
[`docs/strategy/ARCHITECTURE.md`](../../docs/strategy/ARCHITECTURE.md) §6. This file answers one
question: *how do Varad and Prathamesh both work on it from today without either waiting on the
other.*

It follows the technique in [`contracts.md`](contracts.md) — freeze the type, ship the fake, never
wait — applied to research instead of to product code.

**This file does not schedule anything.** ARCHITECTURE §6 declares the track unscheduled on purpose,
so unfunded research does not quietly eat a product week. Everything below is ordered by
**dependency, not by date.**

---

## 1. Why the obvious split does not work

ARCHITECTURE §6 lists seven steps. Handing out "you take 2 and 4, I'll take 3 and 6" fails on the
first morning, for two reasons.

**The steps are a chain, not a list.**

```
1 ──▶ 2 ──▶ 4 ──▶ 7          the serial spine: seam → M1 → M2 → reach
│
├──▶ 3                        M3 — needs atr_bp from step 1, nothing else
├──▶ 5                        tick replay — needs only trades on disk
└──▶ 6                        spot feed — needs Instrument from step 1
```

Steps 2, 4 and 7 are one person's work by construction: M2 is quoted against **M1's corrected
null**, and `reach.py` is a table over both. Splitting that chain across two people means a handoff
every few days.

**And everything is blocked on step 1.** `s1.py` hardcodes `TICK = 0.10` / `TICK_VALUE = 10.0`, and
`backtest.py`, `strategies.py`, `horizon.py`, `features/expansion.py`, `features/orderflow.py` and
two test modules all import it. Until `TICK` is injected, every tick-denominated number in the repo
silently assumes GC futures. Nobody can measure anything on a second instrument until that is done,
once, by one person.

## 2. The split that does work — one bucket axis each

`reach.py`'s bucket key (ARCHITECTURE §3, stage 7) is:

```
(instrument × atr_bp × phase × vol_state × side)
```

**Four axes. Two of them are volatility and geometry; two are clock and breadth.** Split the axes
and each lane owns a complete vertical — its own features, its own strategy function, its own
measurement — importing nothing from the other lane.

| | **Varad — the vol axis** (teal) | **Prathamesh — the clock axis** (blue) |
| :--- | :--- | :--- |
| Owns in the bucket | `atr_bp`, `vol_state` | `phase`, `instrument` |
| Question | *What geometry, at what volatility, has positive EV?* | *Does the clock condition the outcome, and does it survive on a second instrument?* |
| Steps (§6) | **1, 2, 4, 7** | **3, 5, 6** |
| Strategy fn | `m1_geometry`, `m2_vol_momentum` | `m3_session_event` |
| Features owned | `range_bp`, `rv_parkinson`, `rv_slope`, `efficiency_ratio` (+ `atr_bp`, shipped at the seam) | `session_phase`, `event_proximity`, `anchors`, `mid`, `spread_bp`, `quote_rate_z` |
| Data | 46M GC trades, on disk | The same bars for M3; then a free spot feed |
| Kills the lane if | No cell on M1's surface clears **EV − cost > 0** at n ≥ 400 **and** M2's magnitude claim lands inside its own MDE | No phase or event cut clears **EV − cost > 0** **and** spot spread shows no structure |
| Cost | $0 | $0 |

**⚠️ Both kill rows were amended 2026-09-06, after M3 ran, and the reason is a finding rather than
a preference.** They originally read *"M1 returns no positive-EV cell"* and *"M3's profile does not
survive the 2025/2026 split"* — one stated in EV, one stated in profile survival.
[`M3_CLOCK.md`](../../services/signal-data/analysis/M3_CLOCK.md) showed the second is the wrong
test: **the profile survived — `London-NY` clears its own `mde_rate` in 14 of 16 cells — and was
worth nothing.** `London-NY` has the highest `p_target` on both sides *and the worst long EV on the
board*, because `p_stop` rises with it; the bracket simply resolves faster and nothing favours a
direction.

**Reach is a property of the bracket; EV is the property of the trade.** A lane dies on EV net of
cost or it does not die, and a `p_target` lift against a null is not evidence that anything is
tradeable. Prathamesh's correction, adopted here for both lanes. **Changing a kill line after a run
is exactly the move this project distrusts** — it is recorded rather than quietly applied, and it
survives the test it is meant to survive: **the amended line is harder to pass than the one it
replaces**, on both lanes, so it cannot have been loosened to rescue a result.

**The reason to split it this way, stated plainly:** ARCHITECTURE §6 says three kill conditions can
fire on data already paid for. Run serially, finding that out takes as long as all three take. Run
in two lanes, **the track can die in half the time** — and dying fast on free data is the single
most valuable outcome available here.

### What each lane must not touch

| Module | Owner | Rule |
| :--- | :--- | :--- |
| `s1.py`, `backtest.py`, `horizon.py`, `base_rates.py`, `calibration.py`, `features/expansion.py` | Varad | **Shared spine.** Additive changes only, Track A's 103 tests as the regression gate. Prathamesh opens an issue; he does not open a PR against these |
| `features/orderflow.py`, `signals/engine.py`, `families.py`, `compute_delta_cvd.py`, `regimes.py`, `features/regime_filter.py` | Track A — **parked** | Neither lane edits these. ARCHITECTURE §2 |
| `features/portable.py`, `strategies.py` | **Both**, by function name — §4 | Fill in your own function bodies. Never reorder, never rename, never add a function without standup |
| `instruments.py`, `reach.py` | Varad | Frozen at the seam (§3); `reach.py` is written at the rejoin (§6) |
| `replay.py` | Prathamesh | New, standalone. Does **not** modify `backtest.first_touch` — see §5 |
| `calendars.py`, `reference/us_releases.csv` | Prathamesh | New, standalone, added 6 Sep. The BLS/FOMC schedule `event_proximity` reads. **Transcribed, never generated** — see §11 |
| `tests/test_clock.py` | Prathamesh | New. The clock lane's tests live in their own module so neither lane rebases the other's test file |

This keeps [`roles.md`](roles.md) intact: the signal system is still Varad's, and Prathamesh gets a
real vertical inside it rather than a task queue.

---

## 3. The one wait, and it is half a day — ✅ SHIPPED 2026-09-06

**Everything in this plan waits on step 1 exactly once.** Varad ships it before either lane starts:

1. `instruments.py` — the frozen `Instrument` dataclass (ARCHITECTURE §4.2), `has_flow: False`
   **raising**, not degrading.
2. `TICK` injected through `s1.py` → `backtest.py` → `strategies.py` → `horizon.py` →
   `features/expansion.py`. One commit. Track A's tests green before and after, or it is not done.
3. `atr_bp` in `features/portable.py` — because M3 needs it and M3 is the other lane.
4. **The signature stubs** for §4's function tables, committed raising `NotImplementedError`.

Point 4 is the part that buys the independence and it is worth ten minutes' care. Committing every
function signature on day one means two people fill in disjoint bodies in the same two files
**without ever conflicting** — nobody is appending to a moving target. It is the same move as
freezing `engine/types.ts` on W1D1, which `contracts.md` calls the most valuable half hour of the
week.

**Freeze it together, in one sitting, both present.** After that the lanes do not meet again until
§6.

### What landed — 2026-09-06

All four points, one commit, **165 tests green** (155 before, 10 new on the seam), `ruff` and
`mypy` clean. **The clock lane is unblocked and can start on `session_phase` today.**

| Point | Where |
| :--- | :--- |
| 1 · `Instrument`, `has_flow: False` raising | `services/signal-data/instruments.py` — `GC` defined, **`XAUUSD` deliberately not** |
| 2 · `TICK` injected | `s1.py` no longer exports it; `backtest.py`, `strategies.py`, `horizon.py`, `features/expansion.py`, `features/orderflow.py` all take an `Instrument`. **A sixth importer neither §1 nor ARCHITECTURE §4.2 listed:** `alltick/packages/edge/ohlcv_edge.py`, the spot cross-check, which borrows GC's tick on purpose and now takes it from the seam |
| 3 · `atr_bp` | `features/portable.py`, wrapping `expansion.atr` rather than re-deriving it |
| 4 · Signature stubs | 10 in `features/portable.py` (12 names; `to_bp` and `atr_bp` ship with bodies) and `m1_geometry` / `m2_vol_momentum` / `m3_session_event` in `strategies.py`, all raising `NotImplementedError`; the names and their frozen order are asserted by `tests/test_instruments.py` |

**Three things about it that are decisions, not transcription, and that the room has to sign:**

- **`XAUUSD` is not in `instruments.py`.** Route 2 has not picked a vendor and a spot tick is
  broker-dependent — 0.01 or 0.10 — which is the exact 10x error §4.6 exists to prevent. A
  placeholder would put a guessed number in the seam. The tests use a local fixture instead.
- **The parked Track A modules were touched after all**, in one line each: `signals/engine.py`,
  `features/regime_filter.py` and `families.py` now pass `GC` explicitly to `atr` / `bar_range` /
  `body_ratio`. There is no way to make the tick a required argument without it, and the
  alternative — a GC default — reintroduces exactly the silent assumption the seam removes.
  Track A is GC-only by declaration (ARCHITECTURE §0), so the pin is now visible in the code
  rather than hidden in an import. Track A's tests are green either side.
- **`require_flow` guards three functions, not every flow function.** `absorption`,
  `bar_imbalance` and `vwap_distance` — the ones that carry an `Instrument` anyway. The rest
  read a `delta` column a flow-less frame does not have. That is not the same protection: an
  MT5 spot feed ships a `volume` column holding a **tick count**, so the missing-column error is
  luck rather than a rule. `tests/test_instruments.py` pins the three.

---

## 4. The two files both lanes write, split by function name

Ownership is **by function**, listed here so there is never a question. `features/portable.py`:

| Function | Owner | Step |
| :--- | :--- | :--- |
| `atr_bp` | Varad | 1 — ships at the seam |
| `range_bp` | Varad | 2 |
| `rv_parkinson` | Varad | 4 |
| `rv_slope` | Varad | 4 — signed; EXPANDING / CONTRACTING / STABLE |
| `efficiency_ratio` | Varad | 4 |
| `session_phase` | Prathamesh | 3 — six phases, `strategy-architecture.md` §2 — ✅ **6 Sep** |
| `event_proximity` | Prathamesh | 3 — BLS + FOMC public calendars — ✅ **6 Sep** |
| `anchors` | Prathamesh | 3 — session open, prior close, session H/L, opening range, TWAP — ✅ **6 Sep** |
| `mid`, `spread_bp` | Prathamesh | 6 — spot native; GC has no quote data |
| `quote_rate_z` | Prathamesh | 6 — trailing z within instrument **and vendor** |

`strategies.py` gains three functions, `(bars, *, thresholds) -> Series`, matching the existing
shape so `backtest.evaluate` consumes them unchanged:

| Function | Owner |
| :--- | :--- |
| `m1_geometry` | Varad |
| `m2_vol_momentum` | Varad |
| `m3_session_event` | Prathamesh — ✅ **6 Sep** |

`m4_*` is contested (ARCHITECTURE §7) and is not stubbed. It gets a name when something decides it.

**`atr` is imported from `features/expansion.py`, never re-derived** — `regime_filter.py`'s rule:
*"Re-solving session-grouped trailing windows in a second file is how the two quietly disagree."*
That applies across lanes with double force now that two people are writing windows.

---

## 5. Step 5 — tick replay, and why it is Prathamesh's but does not touch `backtest.py`

Tick replay is the largest work item in the track and it is free in money (ARCHITECTURE §5). It
needs only `timestamp, price, size`, which every month on disk carries. It goes in the clock lane
because Varad's lane is a three-step serial chain and this one is not on anybody's critical path.

**It ships as `replay.py`, standalone, producing an intrabar ordering table. It does not change
`backtest.first_touch`.** That function currently resolves same-bar ties to the stop, which is why
every `p_target` in `BASE_RATES.md` is a stated lower bound. Changing it is a shared-spine change
with Track A's tests as the gate — so the replay *measures* how often the tie mattered, and the
change to `first_touch` is Varad's, later, and only if the number says it is worth making.

**Budget it before starting.** ARCHITECTURE §9 open question 5 asks for a time budget set now rather
than halfway through. Write the number in this file before the first line of `replay.py`.

**Time budget: ______ days.** *(unset — Prathamesh writes it here before starting)*

---

## 6. The rejoin — one day, at the end

The lanes meet twice and only twice.

```
        I1                                                        I2
  seam freeze                                                  reach.py
   (half a day)                                                 (one day)
        │                                                          │
Varad   ●──▶ M1 geometry sweep ──▶ M2 vol momentum ────────────────●──▶ EV surface + null
        │                                                          │
Prath.  ●──▶ M3 session+event ──▶ spot feed ──▶ portable refit ────●──▶ phase profile, ×2 instruments
                    └──▶ replay.py (float)
```

**I2 is `reach.py`.** Varad writes it, against Prathamesh's `phase` column exactly as delivered — no
renegotiation of the phase boundaries at that point, because a boundary moved after the surface is
visible is a fit. If the two lanes' cells disagree about anything, that is a finding, not a merge
problem.

Everywhere else in between, neither person is blocked on the other for a single hour.

---

## 7. What the split buys that one person working alone does not have

**Cross-review of pre-commitments.** ARCHITECTURE §9 lists two places where a number could be chosen
while looking at the answer. With two people, each pre-commits to the other, in a commit, before
running anything. That is strictly stronger than self-commitment, and it is the one genuine
methodological upgrade here.

**They live in [`strategy-precommit.md`](strategy-precommit.md).** All seven are now filled and
committed — Varad's three on 6 Sep, Prathamesh's four the same day, each before the run that reads
them.

| Pre-commitment | Owner | Reviewed by | Due | Status |
| :--- | :--- | :--- | :--- | :--- |
| M1's geometry grid — target/stop/horizon ranges | Varad | Prathamesh | Before the sweep runs | ✅ **6 Sep** — 6×4×3 = 72 points, in multiples of the bar's own ATR |
| `atr_bp` bucket edges | Varad | Prathamesh | Before the sweep runs | ✅ **6 Sep** — `(0, 7, 10, 14, ∞)` bp, the archive's pooled quartiles rounded |
| `MIN_SAMPLES` per cell in `reach.py` | Varad | Prathamesh | Before any surface is looked at | ✅ **6 Sep** — **400**, from `n_for_rate(0.1644, 0.224)` |
| The six session-phase boundaries | Prathamesh | Varad | Before M3 runs | ✅ **6 Sep** — **in ET wall clock, not UTC**; both mappings in `prathamesh/clock-lane.md` §1 |
| The event window, in minutes either side | Prathamesh | Varad | Before M3 runs | ✅ **6 Sep** — **±15**, covering §2's BLS window with margin |
| The 2025/2026 split date | Prathamesh | Varad | Before M3 runs | ✅ **6 Sep** — 2025-01…09 against 2025-10…2026-07, per ARCHITECTURE §6 |
| The opening-range length | Prathamesh | Varad | Before M3 runs | ✅ **6 Sep** — **30 minutes**; a fourth, added because `anchors` computes a range and a range has a length |
| M2's vol-momentum thresholds | Varad | Prathamesh | Before M2 runs | ✅ **7 Sep** — window 60min, `slope_min` ±0.20, `T` and `H` reused from M1's committed grid; an eighth, added because step 4 selects |
| M1 conditioned on EXPANDING | Varad | Prathamesh | Before the conditioned sweep runs | ✅ **7 Sep** — `(bucket × vol_state × side)`, phase dropped, training half only; a ninth |

"Reviewed by" means one person reads the number and says whether it looks chosen or looks fitted.
It is five minutes and it is the whole point.

**Prathamesh's four are committed — [`prathamesh/clock-lane.md`](prathamesh/clock-lane.md), 6 Sep,
ahead of any run.** They are ±15 minutes, the 2025-01–09 / 2025-10–2026-07 split, a 30-minute
opening range, and the six boundaries **in ET wall clock rather than in UTC** — which is a
departure from this table's wording and is the one of the four that needs Varad's eye rather than
his nod. The short version: the London and NY opens follow local DST, so a frozen UTC number is an
hour wrong for the five EST months of the archive (2025-11 – 2026-03) and pools London into
London-NY for all of them. That is §4.6's unit error arriving through the clock. Both UTC mappings
are tabulated there. **Varad's three are still open, and M1 cannot run until they are.**

---

## 8. Proposed seams — ⏳ 1 of 3 (Varad signed 2026-09-11; still not frozen)

[`contracts.md`](contracts.md) changes only by all three agreeing in standup, so these two are
drafted here rather than added there. **Put them to the room before either lane writes code.**

> ### Sign-off state
>
> | | S8 · `Instrument` | S9 · The bars frame |
> | :--- | :--- | :--- |
> | Varad | ✅ **2026-09-11** | ✅ **2026-09-11**, the amended text |
> | Prathamesh | ⬜ | ⬜ |
> | Shreyas | ⬜ | ⬜ |
>
> **Given verbally in session, and not a logged artefact from the moment** — recorded the way S7's
> approvals were, because a signature nobody can point at later is worse than an unsigned contract.
>
> **What Varad signed on S9 is the AMENDED text**, not the original: the shared core of
> `open/high/low/close/session`, instrument-specific columns permitted, and no portable feature
> reading outside the core unless `has_flow` gates it. The original "both loaders produce the same
> frame" is superseded — it was measurably violated and could not have held. Stated explicitly
> because "signed S9" is ambiguous once two versions exist.
>
> **Prathamesh was asked on 2026-09-11: [issue #6](https://github.com/Prathameshh-Patil/trading-intelligence/issues/6).**
> Deliberately an issue rather than a message — it is a durable artefact, which is the thing every
> other signature in this repo lacks. It lists what changed since he last saw each seam and, in its
> own section, the four things he might reasonably refuse.
>
> **One signature does not freeze a contract.** `contracts.md`'s own discipline is all three in
> standup, and S7 was held to exactly that on 10 Sep — 3 of 3, with each approval and how it was
> obtained written down. **Prathamesh has built against both seams for ten days**, which is
> evidence he agrees and is not the same thing as agreeing; and Shreyas has not seen either.
>
> **When the other two land, these move into `contracts.md` as S8 and S9** the way S7 was
> registered, and the freeze discipline binds from that moment: any later change needs all three
> again, in one commit carrying the type, the fake, the real implementation and every consumer.
> Until then this file remains where they live.

### S8 · `Instrument` — Varad → both lanes

```python
@dataclass(frozen=True)
class Instrument:
    name: str                 # 'GC' | 'XAUUSD'
    tick: float               # 0.10 | broker-dependent
    tick_value: float | None  # USD per tick per contract; None for spot
    session: SessionCalendar  # Globex 18:00-17:00 ET | 24x5 with a named boundary
    anchors: tuple[str, ...]  # which M4 anchors are defined here
    has_flow: bool            # may features/orderflow.py be read at all
```

**⚠️ Amendment, as built 6 Sep: `session: SessionCalendar` shipped as
`session_shift: pd.Timedelta`.** There is no calendar type in this repo and nothing yet needs one —
the only session logic that exists is the +2h shift `s1.py` applies to roll a Globex date onto the
day a trader files it under, and "24x5 with a named boundary" is the same shape. A type with one
implementation and no second consumer is the abstraction this project deletes on sight. **It earns
its own type when a second instrument needs more than an offset — which is also when the DST hole
`s1.py` already documents has to be closed.** Everything else in S8 shipped verbatim.

**`has_flow: False` raises.** It does not degrade, fall back, or substitute a proxy — the same
discipline the pipeline design applied to OCR-derived numbers, for the identical reason: a silent
degradation produces a number that looks exactly like the real one.

Every downstream function takes an `Instrument`. Nothing imports `TICK`.

**⚠️ Second amendment, 2026-09-10: `XAUUSD` now exists, and its `tick` is the feed's quantum.**
The module refused to define it on 6 Sep because a spot tick is broker-dependent — 0.01 or 0.10,
ARCHITECTURE §4.6's 10× error. That refusal was right, and measurement narrowed it: running
`m1_sweep.month_counts` over one month at tick 0.10 and at 0.01 returns **byte-identical counts**,
with only `cost_atr` moving. The tick cancels out of the geometry. So `XAUUSD.tick = 0.001` is
**Dukascopy's price resolution — a property of the file in hand, not a guess about an account
nobody has opened** — and it is safe for every `p_target`/`p_stop` comparison and forbidden for
any cost or EV claim. **The room still owns the tradeable tick**; this one is not it.

**⚠️ The seam is one field short, and this is the place that says so.** `s1.minute_bars` and
`regimes.resample_bars` both read the module-level `SESSION_SHIFT` rather than
`inst.session_shift`. Step 1 injected `TICK` through the repo and left the session boundary
behind, so a second instrument's sessions are cut by GC's constant unless its loader avoids those
functions — which is exactly what `spot.py` had to do. **Fixing it means editing `regimes.py`, a
parked Track A module §2 forbids Track B from touching**, so it is recorded rather than done. It
is the same hole `s1.SESSION_SHIFT`'s own docstring calls out for DST, arriving through
portability instead.

### S9 · The bars frame — either loader → both lanes

A GC loader and a spot loader must produce the **same frame**, or the second instrument is not a
cross-check of the first, it is a different experiment.

```
timestamp   datetime64[ns, UTC]   exchange timestamp, not receipt time
open        float64
high        float64
low         float64
close       float64
session     category              session label, per Instrument.session
```

Spot adds `bid`, `ask` — nullable, and **null on GC is the correct value, not a gap to fill.**

> ## ⚠️ AMENDED 2026-09-10 — as written this is violated, and it could not have held
>
> **Measured, both loaders, same bar size:**
>
> ```
> shared   close, high, low, open, session
> GC only  cvd, delta, trades, volume
> spot only  spread_bp, ticks          <- NOT bid, ask
> ```
>
> Two corrections. **`bid`/`ask` are tick-level quantities and do not survive bar aggregation** —
> a bar has an open, high, low and close of *something*, and `spot.minute_bars` builds them from
> the **mid**, carrying `spread_bp` as its own column instead. And **"the same frame" cannot hold
> in the direction S9 assumed**: it is GC that carries the extra columns, because it has a tape
> and spot does not. `delta`, `volume`, `trades` and `cvd` are nullable-on-spot in exactly the way
> S9 said `bid`/`ask` would be nullable on GC, and there is no arrangement in which both frames
> have the same columns.
>
> **The rule that does hold, and that the code already enforces:**
>
> 1. **The shared core is `open, high, low, close, session`, on a UTC index.** Both loaders
>    produce it and it is the contract.
> 2. **Each loader may add instrument-specific columns.** They are not gaps in the other frame;
>    they are quantities the other instrument does not have.
> 3. **No portable feature may read outside the shared core** unless `Instrument.has_flow` gates
>    it — which is what `require_flow` already does, and why `atr_bp`, `session_phase` and
>    `vol_state` run unchanged on both.
>
> That is a stronger guarantee than "the same frame", because it is checkable and because the
> original could only ever have been satisfied by inventing a `volume` for spot — the precise
> thing `has_flow` exists to prevent. **Still not frozen. This is what there is to sign.**

**One name is duplicated and should not stay that way.** `features/portable.mid` and
`features/portable.spread_bp` are committed signatures raising `NotImplementedError`, owned by
Prathamesh for step 6. `spot.minute_bars` computes both inline because it needed them before
step 6 ran. **Two definitions of the same quantity is how two files quietly disagree**, and the
fix is one line at each site once those stubs are filled — recorded here rather than resolved by
one lane implementing the other's function.

**Every feature, bucket and threshold downstream is in basis points of price** (ARCHITECTURE §4.6).
GC's tick is 0.10; an MT5 broker may call a XAUUSD pip 0.01 or 0.10. A mis-scaled *display* renders
visibly wrong; a mis-scaled *bucket* silently pools two populations and reports the average as a
base rate. Conversion to whatever the trader's platform calls a pip happens once, at stage 9,
labelled.

**The fake, if the spot feed is late:** Prathamesh runs M3 on GC bars first. They exist, and M3 is
non-directional and needs no quote data — so the entire clock lane is testable before a spot vendor
is chosen. The spot feed is a *refit*, not a prerequisite.

---

## 9. The decision this file does not make

**Whether Prathamesh's twelve-week shell schedule still stands.**

[`roles.md`](roles.md) has him owning everything the user touches, and
[`prathamesh/README.md`](prathamesh/README.md) has him in Week 1 kill-week shell work right now —
Tauri overlay, click-through over MT5, `engine/mock.ts`. The strategy track is explicitly
unscheduled and takes no week from `plans/team/`.

Those two facts do not compose. Either:

- **The clock lane is research he does alongside the shell**, in the slack his own file already
  budgets as Float — in which case his Week 1–3 gates are unaffected and the lane moves slowly; or
- **He is moving onto the strategy track**, in which case the overlay compositing measurement, the
  hotkey, position memory and the Week 3 integration day lose their owner, and
  `plans/team/prathamesh/README.md` needs rewriting rather than annotating.

**This is a scheduling decision for all three of you and it is not made here.** The split above is
correct either way — it says who owns which axis, not how many hours a week the axis gets.

---

## 10. The rules, collected

1. **One axis each.** Varad owns `atr_bp` and `vol_state`; Prathamesh owns `phase` and the second
   instrument. Nobody measures on the other's axis.
2. **Step 1 is the only wait.** Half a day, both present, then the lanes do not meet until `reach.py`.
3. **Ownership in shared files is by function name**, listed in §4. Signatures committed on day one;
   never reordered, never renamed, never added without standup.
4. **Neither lane edits a Track A module**, and only Varad edits the shared spine, additively, with
   Track A's tests as the gate.
5. **Every threshold is pre-committed to the other person, in a commit, before the run.** §7.
6. **Basis points, never ticks**, except at stage 9's labelled display conversion.
7. **Every lift is reported against a mix- and side-matched null, with `mde_rate` and N beside it** —
   in both lanes, so the two lanes' results are comparable to each other and to Track A's.

---

## 11. Clock lane — what landed, 2026-09-06

**Step 3's code is built and green; step 3's run is blocked on data.** Full detail and the four
pre-committed numbers are in [`prathamesh/clock-lane.md`](prathamesh/clock-lane.md); this is the
summary the room needs.

**197 tests green** (165 after the seam, 32 new), `ruff` and `mypy` clean. `session_phase`,
`event_proximity` and `anchors` have bodies; `m3_session_event` has a body; `calendars.py` and
`reference/us_releases.csv` are new and standalone. **Nothing in Varad's column was touched** —
`range_bp`, `rv_parkinson`, `rv_slope` and `efficiency_ratio` still raise `NotImplementedError`,
and the frozen order in §4 is unchanged. The split held: two people, two disjoint sets of function
bodies, one file, no conflict.

**Four things about it that are decisions, not transcription, and that the room has to sign:**

- **The phase boundaries are frozen in ET wall clock, not in UTC**, against §7's wording. The
  reason is §4.6's: a frozen UTC number is an hour wrong for the five EST months of the archive and
  pools London into London-NY across all of them, invisibly, with six rows in the table and an N in
  every cell. Both UTC mappings are tabulated in clock-lane.md §1.
- **The release calendar is transcribed from BLS and the Fed, not generated from a rule.** This is
  not fastidiousness — the rule is wrong on this exact archive, in both directions at once. There
  is **no October 2025 Employment Situation**; September's landed **2025-11-20**, seven weeks late,
  and September CPI landed **2025-10-24**. "First Friday, 08:30 ET" marks a quiet Friday as
  payrolls *and* leaves the highest-volatility gold bar of that quarter in the null. Three
  assertions in `test_clock.py` pin it, and extending the CSV means extending `COVERAGE` with it.
- **`opening_range` is one anchor name and two columns**, high and low. A band collapsed to a
  midpoint loses the only thing it is consulted for.
- **`m3_session_event` imports `features.portable` inside the function body.** `features/expansion`
  imports `_align` and `_window` from `strategies`, so a module-level import closes a cycle.
  Hoisting those two helpers into their own module is the real fix and it is a shared-spine change,
  which is Varad's (§2). The deferred import is the clock lane's cost of not reaching into it, and
  it is one comment long.

**A finding that is not about this lane.** `s1.SESSION_SHIFT`'s +2h rolls the session date at
22:00 UTC — 18:00 ET in summer, exactly the Asia open, but **17:00 ET in winter, an hour inside
`NY-Asia`**. For five months of the archive a bar's `session` and its `phase` disagree about which
day it belongs to. `reach.py` keys on `phase` and not on `session`, so the rejoin is unaffected —
but it is the same DST hole `s1.py` documents, and it closes in the same commit that turns
`session_shift` into the calendar S8 drafted. clock-lane.md §6.

**⛔ The blocker, and it is the only one.** Only `2026-07` is on this machine — 1,616,772 rows of
the manifest's 46,034,813, and the iCloud backup path is empty here too. **§7's split needs all 19
months, and one month cannot be split.** M3 on July alone is not a weak version of the result; the
split *is* the test. Restoring the archive is the next thing this lane needs and the only thing it
needs.
