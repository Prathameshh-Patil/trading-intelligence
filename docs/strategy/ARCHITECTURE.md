# Strategy-track architecture — the L1 pipeline, end to end

**Written 2026-09-06.** Scope: the **strategy track** only — the L1-only, two-instrument research
programme settled by [`strategy-reconciliation.md`](strategy-reconciliation.md).

**This is a second track, not a replacement.** [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) remains
the map of the whole system — the product, the seams, the vendors, the shell. Where the two
disagree about the *product*, that file wins. This file is authoritative only about **how the
strategy work is laid out and what it is allowed to touch.**

Nothing described past §6 is built. Where something exists on disk it is named with its file; where
it does not, it says so.

---

## 0. The two tracks, in one table

| | **Track A — order flow** | **Track B — strategy (this file)** |
| :--- | :--- | :--- |
| Question | Does GC order flow carry a tradeable edge? | Does *anything* computable from L1 carry one, on both instruments? |
| Core features | delta, CVD, absorption, footprint, book | price, spread, quote rate, time |
| Instruments | GC futures only | GC **and** spot XAUUSD |
| Data | Databento `trades` (46M rows, 19 months, on disk) | The same 46M rows, plus a free spot feed |
| Status | **PARKED 2026-09-06** | **ACTIVE** |
| Cost to proceed | `mbp-1` / book data, unpriced | **$0** — see §5 |
| Code | `features/orderflow.py`, `signals/engine.py`, `families.py`, `compute_delta_cvd.py` | `instruments.py`, `features/portable.py` — **6 Sep** — and `reach.py`, **served 10 Sep** |

**Both tracks share one measurement stack** — `backtest.py`, `horizon.py`, `base_rates.py`,
`calibration.py` — and that sharing is the point. It is what makes the two tracks' results
comparable when Track A restarts.

---

## 1. Why the split happened, stated from the evidence

Not a change of mind. Three measurements, in this repo, forced it.

**1. The four order-flow conditions carried no edge, at power.**
[`FAMILIES.md`](../../services/signal-data/analysis/FAMILIES.md): the exhaustion arm landed at
**−0.0058** on 393 legs and the continuation arm at **−0.0003** on 545, against a mix- and
side-matched null, where `mde_rate` says **a 30% relative lift would have been detected at 80%
power.** That is "we looked and there is nothing there", not "we could not tell".

**2. Order flow does not exist on spot gold.** No centralised tape, no aggregate volume, no
aggressor. So a strategy built on CVD is a GC-only strategy, and every cross-instrument check —
the strongest validation available here — is closed off by construction.

**3. The cross-instrument check has already caught something.** `horizon.py` measured GC as a random
walk at 5/15/30m; `ohlcv_edge.py` reproduced it on spot gold **to within 0.4%**, through different
code on a different vendor's data. That is two independent confirmations of the same fact, and it is
only possible for features that exist on both instruments.

**What this does not say.** `FAMILIES.md` §5 is explicit and it is quoted here so the parking is
not over-read:

> **Does not:** say the conditions are wrong in principle — only that these four, at these
> thresholds, on this half of this month, do not beat their null.

**Track A is parked, not killed.** Four conditions at one set of thresholds on one month's training
half is a narrow result. It is enough to stop spending the next month there; it is not enough to
conclude the tape holds nothing.

### 1.1 The tension this creates, named rather than smoothed over

[`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) §1 states the product thesis as order flow:

> `delta` and `cvd` are the numbers a screenshot can never contain […] **That is the whole wedge.**

Track B does not use them. So the honest statement of the position today is:

- The *information* claim is still true — a chart genuinely cannot show CVD, and two sessions with
  identical OHLC genuinely can have opposite CVD.
- But **an information advantage that does not produce edge is not yet a product**, and the one
  measurement made of that edge came back flat.

**That is a product decision, not an architecture decision, and this file does not make it.** It is
Varad's and Shreyas's, it interacts with the licensing question, and §9 carries it as open. What
this file does is make sure the two tracks stay separable so the decision can be made later on
evidence rather than on sunk code.

---

## 2. What "parked" means, exactly

Precision here is what stops parking from turning into rot.

**Nothing is deleted, moved, or rewritten.** `features/orderflow.py`, `signals/engine.py`,
`families.py`, `compute_delta_cvd.py`, `regimes.py` and every test over them stay exactly as they
are, green, in place.

**No Track B work may modify a Track A module.** If Track B needs something a Track A file has, it
is *imported* if it is portable, or *reimplemented in `features/portable.py`* if it is not. The one
exception is a shared module named in §4 — `backtest.py`, `horizon.py`, `base_rates.py`,
`calibration.py`, `s1.py` — and changes to those are additive only, with Track A's tests as the
regression gate.

**`features/orderflow.py` gains one line in its docstring: `VENUE-SPECIFIC — GC only`.** That is
the whole code change parking requires.

**Track A's open threads are recorded, not resolved:** Gate 1's option (b) (restoring condition A —
the one arm whose sign was positive), Part C of `thresholds_selector.md`, and the filtered
exhaustion arm that needs ~2.5 years of tape to call either way. They are still open. They are just
not being worked.

---

## 3. The pipeline, end to end

```
                          ┌──────────────────────────────────────┐
                          │  TRACK A — PARKED                    │
                          │  features/orderflow.py  (GC only)    │
                          │  signals/engine.py · families.py     │
                          │  delta · cvd · absorption · footprint│
                          └──────────────────────────────────────┘
                                          ╎
                                          ╎  no edge at power (FAMILIES.md)
                                          ╎  + does not exist on spot
                                          ╎  ── rejoins at §8 ──
                                          ╎
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  1 · SOURCES                                                               │
  ├────────────────────────────────────────────────────────────────────────────┤
  │  GC futures — Databento `trades`          │  Spot XAUUSD — free L1          │
  │  46,034,813 rows · 19 months · ON DISK    │  Dukascopy or MT5 demo · TBD    │
  │  timestamp, price, size, aggressor_side   │  bid, ask, timestamp            │
  └────────────────────────────────────────────────────────────────────────────┘
                     │                                    │
                     ▼                                    ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  2 · NORMALISE            instruments.py  ·  NEW                           │
  │  tick size · session calendar · anchors · has_flow · bp conversion         │
  │  ── everything downstream is in BASIS POINTS, never ticks ──               │
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  3 · FEATURES             features/portable.py  ·  NEW                     │
  │  mid · spread_bp · quote_rate_z · atr_bp · rv_parkinson · rv_slope         │
  │  efficiency_ratio · session_phase · event_proximity · anchors              │
  │  ── computable on BOTH instruments, or it does not belong here ──          │
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  4 · STRATEGIES           strategies.py (extended)  ·  NEW FUNCTIONS       │
  │                                                                            │
  │   M1 geometry      M2 vol momentum    M3 session+event   M4 contested      │
  │   (non-direct.)    (magnitude)        (non-direct.)      (see §7)          │
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  5 · LEGS                 backtest.py  ·  EXISTS, UNCHANGED                │
  │  clock horizons · session-bounded · MFE/MAE signed in the trade's favour   │
  │  first_touch: same-bar ties resolve to the STOP (p_target is a lower bound)│
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  6 · NULL + POWER         base_rates.py · horizon.py  ·  EXIST             │
  │  mix- and side-matched null  ·  mde_rate(null, n) beside every lift        │
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  7 · REACH TABLE          reach.py  ·  NEW                                 │
  │  P(target before stop) per (instrument × atr_bp × phase × vol_state × side)│
  │  → this IS PipForecast.bucket. Below MIN_SAMPLES the answer is null.       │
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  8 · CALIBRATION          calibration.py  ·  EXISTS, UNCHANGED             │
  │  append-only · settle() cannot invent history · reliability diagram        │
  │  "when it says 61%, does it happen 61% of the time"                        │
  └────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  9 · PRODUCT SURFACE      services/api → apps/desktop  ·  UNCHANGED SEAM   │
  │  S7 PipForecast: side · pDirection · forecast · reasoning · tradeable      │
  │  no guaranteedPips · no lot size · forecast:null is a valid common answer  │
  └────────────────────────────────────────────────────────────────────────────┘
```

**Stages 5, 6, 8 and 9 already exist and do not change.** That is the case for this track being
cheap: the measurement stack was built instrument-agnostic, and the only genuinely new modules are
2, 3, 4 and 7.

---

## 4. Stage by stage

### 4.1 Sources

GC is on disk and paid for: **46,034,813 trades, 19 months, Jan 2025 – Jul 2026 contiguous**, hashes
in [`gc_data_manifest.md`](../../services/signal-data/analysis/gc_data_manifest.md). Every month is
the `trades` schema — **there is no quote data anywhere in this repo**, which is the finding that
set this track's budget (`strategy-reconciliation.md` §3).

Spot is not chosen yet. Route 2 (`strategy-reconciliation.md` §7.3) says take a free bid/ask feed —
Dukascopy historical ticks first, MT5 demo as fallback. ✅ **Reachability checked 7 Sep and it
passes** — `analysis/SPOT_FEED_CHECK.md`. XAUUSD tick history is free, complete and decodable:
20,654 quotes in one London–NY hour, 344/min, spread median 1.91 bp, and the price level
cross-checks against our own GC archive for the same hour at a ~+19 basis, which is cost of carry
rather than a scale error. **It was never a reachability problem — the host resets a request with no
browser `User-Agent`**, which is almost certainly what `DELTA_CVD_FINDINGS.md` §4 recorded as
"unreachable". A bulk pull is ~10,000 hourly files and is not a ten-minute job; one request in four
was reset even with the header set.

### 4.2 `instruments.py` — the one new abstraction

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

**Why it must exist before anything else.** `s1.py` hardcodes `TICK = 0.10` and `TICK_VALUE = 10.0`,
and **every tick-denominated number in the repo flows through those two lines** — `backtest.py`,
`strategies.py`, `horizon.py`, `features/expansion.py`, `features/orderflow.py` and two test
modules. Until `TICK` is injected rather than imported, the entire measurement stack silently
assumes GC.

**`has_flow` is a hard boundary, not a hint.** Reading `features/orderflow` on an instrument where
it is `False` **raises**. It does not degrade, fall back, or substitute a proxy. This is the same
discipline the pipeline design applied to OCR-derived numbers — *not as a fallback when the feed is
down, not as a cross-check, not behind a flag* — for the identical reason: a silent degradation
produces a number that looks exactly like the real one.

### 4.3 `features/portable.py` — the intersection, and nothing else

The admission rule is one sentence: **if it cannot be computed on both instruments, it does not go
in this file.**

| Feature | From | Note |
| :--- | :--- | :--- |
| `mid`, `spread_bp` | quotes | Spot native; GC needs quote data it does not have (§7) |
| `quote_rate_z` | quotes | **Trailing z-score within instrument and vendor, never a raw threshold** |
| `atr_bp`, `range_bp` | OHLC | Basis points, not ticks — §4.6 |
| `rv_parkinson`, `rv_slope` | OHLC | Signed slope gives EXPANDING / CONTRACTING / STABLE |
| `efficiency_ratio` | OHLC | Directional move over total path |
| `session_phase` | clock | Six phases, from `strategy-architecture.md` §2 |
| `event_proximity` | public calendar | BLS release schedule, Fed FOMC dates |
| `anchors` | OHLC + calendar | session open, prior close, session H/L, opening range, TWAP |

`atr` already exists in `features/expansion.py` and is imported, not re-derived — the same rule
`regime_filter.py` states: *"Re-solving session-grouped trailing windows in a second file is how the
two quietly disagree."*

### 4.4 Strategies

Four functions in `strategies.py`, not a new package. Each takes `(bars, *, thresholds)` and returns
a Series in the shape the existing conditions use, so `backtest.evaluate` consumes them unchanged.

**M1 · geometry frontier** — non-directional. Sweeps `(target, stop, horizon)` per
`(atr_bp bucket × phase × side)` over 19 months, entering every bar. Returns an EV surface.
**Runs first**, because M2's brackets are read off it rather than guessed.

**M2 · vol momentum and compression** — non-directional, predicts *magnitude*. Signed `rv_slope`
against the ATR-matched null; output is `P(|move| ≥ T within H)` feeding stage 7 as a second
conditioning dimension. Highest prior of the four: vol clustering is well-established outside this
repo, and it does not contradict `horizon.py` — a random walk in **direction** can have entirely
predictable **scale**, and only the first was tested.

**M3 · session and event conditioning** — non-directional, needs no market data. Six-phase profile
plus the event calendar, reported per `(atr_bp × phase)` cell, then **split 2025-01–09 against
2025-10–2026-07** to check the profile survives the volatility regime change — the way the 50+ ATR
bucket held **0.2000 → 0.1989** while the headline moved 2.2×. A profile that does not survive that
split is a description of 2025, not a feature.

**M4 · contested** — path-dependent exits, anchor reversion, or the adverse-selection filter. §7.

### 4.5 Stages 5, 6, 8 — unchanged, and that is the point

`backtest.py` (clock horizons, session-bounded legs, MFE/MAE, `first_touch` resolving ties to the
stop), `horizon.py` (`mde_rate`, the sigma/power table), `base_rates.py` (the null) and
`calibration.py` (append-only, `settle` cannot invent history) are **already instrument-agnostic**
once `TICK` is injected. **This track adds no requirement to any of them.**

### 4.6 The unit rule, stated once and enforced everywhere

**Every bucket, threshold and feature in this track is in basis points of price.**

GC's tick is 0.10. An MT5 broker may call a XAUUSD pip 0.01 or 0.10 — a 10× spread in what "40"
means. A 40-tick ATR bucket is a $4.00 move on GC and could be $0.40 on spot. At gold near $2,400
that $4.00 is ~16.7 bp, and **16.7 bp means the same thing on both instruments and on both sides of
a contract roll.**

This is the input-side twin of the pipeline design's §6.4 display trap, and it is the more dangerous
of the two: a mis-scaled *display* renders visibly wrong, a mis-scaled *bucket* silently pools two
different populations and reports the average as a base rate.

Conversion to whatever the trader's platform calls a pip happens **once, at stage 9**, labelled.

---

## 5. Cost, and why the whole track is $0

| Stage | Data | Cost |
| :--- | :--- | :--- |
| 1 GC source | on disk, already paid | **$0** |
| 1 spot source | free feed (Dukascopy / MT5 demo) | **$0** |
| 2–4 normalise, features, M1–M3 | derived | **$0** |
| 4 M4 · path-dependent exit | on disk — `timestamp, price, size` is enough to order MFE against retracement | **$0**, tooling unbuilt |
| 4 M4 · adverse-selection filter | needs `mbp-1` + `tbbo` on GC | **the only paid item** — routed around, §7 |
| 5–9 | existing modules | **$0** |

**Nothing in the build order at §6 is bought.** The `mbp-1` question is deferred, not answered: it
gets priced only if the free spot test (§7) says spread structure is worth having. Both
`pull_tbbo_validate.py --estimate-only` and `pull_futures_trades.py`'s cost-estimate flow return a
number **without spending anything**, so the estimate is available for free whenever it is wanted.

---

## 6. Build order and status

| | Step | Produces | Exists? |
| :--- | :--- | :--- | :--- |
| 1 | `instruments.py`; inject `TICK`; `atr_bp` | The portability seam | ✅ **6 Sep** |
| 2 | **M1** geometry sweep, 19 months | The EV surface — **the null everything else is quoted against** | ✅ **7 Sep** — `analysis/M1_SURFACE.md` |
| 3 | **M3** session + event, with the 2025/2026 split | Clock profile, or a clean negative | ✅ **6–7 Sep** — `analysis/M3_CLOCK.md` |
| 4 | **M2** vol momentum, against M1's corrected null | Second conditioning dimension for stage 7 | ✅ **7 Sep** — `analysis/M2_MAGNITUDE.md` |
| 5 | Tick replay from trades on disk | Intrabar ordering — unblocks M4b **and** the intrabar-stop question `regime_filter.py` raised | ✅ **11 Sep** — [`analysis/REPLAY.md`](../../services/signal-data/analysis/REPLAY.md). M4b still open; see §7 there |
| 6 | Route 2 spot feed; portable regime refit | Cross-instrument validation | ❌ |
| 7 | `reach.py` | `PipForecast.bucket`, served | ✅ **10 Sep** — `analysis/REACH.md` |

**Step 7 shipped 10 Sep** — `reach.py`, 19 months, both sides, 207,984 legs, 116 minutes.
**116 of 144 cells clear the 400-leg floor — 81%**, against a pre-committed prediction of a third
to a half, so the table is far fuller than expected. **The finding is that `phase` and `vol_state`
are not independent:** both transition phases lose their entire CONTRACTING state, and CONTRACTING
runs at **4.7%** of `London-NY`'s legs against 28–36% in the three non-handoff phases — a handoff
window is a place where volatility is rising by construction. That is `atr_bp`'s
quiet-hour-before-the-release artefact arriving a third time, after `M1_SURFACE.md` §3 and
`M3_CLOCK.md` §2, now from the volatility axis instead of the clock. The tie band reproduces M1
independently (8.2% of served rows undecided against 10.2%). **No edge, and none was owed** —
`ev_sym` is positive on 4.4% of rows with a median at the cost floor. `analysis/REACH.md`;
plain-language version with runnable examples in
[`prathamesh/reach-table-explained.md`](../../plans/team/prathamesh/reach-table-explained.md).
**The build then went from 116 minutes to 3.4** — `backtest.excursions` builds each leg's window
once per horizon instead of once per bracket, `first_touch` keeps its signature and its meaning, and
a cold-cache rebuild of all 19 months reproduces `reach_table.csv` byte for byte.

**M1 conditioned on EXPANDING, 7 Sep** — `M2_MAGNITUDE.md` §6 named the run and Varad decided it
rather than drifting into it (`strategy-precommit.md` §9). **Conditioning adds +0.004 ATR per leg
against a cost floor of +0.0423 — short by a factor of ten** — because EXPANDING raises `p_stop`
(+0.0162) *more* than `p_target` (+0.0103): the stop is the nearer barrier, so non-directional
extra movement lands disproportionately on it. **A magnitude edge with no directional content
cannot be harvested by a symmetric bracket.** `analysis/M1_EXPANDING.md`. That is the same
mechanism `M3_CLOCK.md` §2 found in the clock, reached from a second direction — and it confirms
§4.4's framing that M2 is a conditioning dimension for stage 7 and nothing else.

**Step 4 shipped 7 Sep** — `m2_magnitude.py`, training half only. **EXPANDING vol beats
CONTRACTING in 9 of 9 (T, H) combinations and 17 of 36 cells clear their own `mde_rate`** —
against M1's 4.6% pass rate on 3,456 cells, which was noise. The effect is **scale, not
direction**: both tails rise together, so it does not contradict `horizon.py`'s random walk,
only extends it. Small — 2 to 5 points of probability — and it **vanishes in the `14+ bp`
bucket**, which measures how much `vol_state` and `atr_bp` overlap. `analysis/M2_MAGNITUDE.md`.
**The vol lane is alive and the held-out half is unspent.**

**Step 2 shipped 7 Sep** — `m1_sweep.py`, 3,456 cells over 19 months and both sides. **Gross EV
before cost is −0.0032 ATR across the whole surface and the mean cost is +0.0423**, so gold's
bracket geometry is a random walk and the entire net result is commission. 159 cells clear the
committed pass line; the pre-committed side mirror and barrier/open split disqualify all but one,
at `ev_sym` +0.0005 ATR. `analysis/M1_SURFACE.md`. **This does not fire the lane's kill
condition** — §2 requires M1 *and* M2 to fail, and M2 is still owed.

**Step 1 shipped 6 Sep** — `instruments.py`, `TICK` injected through every module that imported
it, `atr_bp`, and every §4.3 / §4.4 signature committed raising `NotImplementedError`. Suite
165 green, `ruff` and `mypy` clean. Two named deviations from S8 as drafted, both recorded in
`plans/team/strategy-split.md` §8 and neither yet put to the room.

**Step 3's code shipped 6 Sep** — `session_phase`, `event_proximity` and `anchors` in
`features/portable.py`, `m3_session_event` in `strategies.py`, and `calendars.py` +
`reference/us_releases.csv` carrying the BLS and FOMC schedules **transcribed rather than derived**
(the 2025 shutdown moved September's payrolls to 20 Nov and deleted October's entirely, so a
first-Friday rule is wrong on this archive in both directions). Suite 197 green, `ruff` and `mypy`
clean. The four pre-committed numbers are in `plans/team/prathamesh/clock-lane.md`, ahead of any
run, and one of them — the phase boundaries frozen in **ET wall clock rather than UTC** — is a
recorded departure from `strategy-split.md` §7 that the room has to sign.

**Step 3 ran 7 Sep** — `analysis/M3_CLOCK.md`, 107,359 legs, both sides, both halves. **The clock
conditions volatility; it does not produce edge; no phase clears cost** — best is `Asia` at +0.572
ticks against a 1.40-tick round trip. `London-NY` carries a large, split-surviving reach lift (14 of
16 cells clear MDE) that does not convert, because `atr_bp`'s trailing window sizes the bracket off
the quiet hour *before* the 08:30 release. **M1 independently rediscovered the same artefact** —
`London-NY` is 17% of its surface and 73% of its passing cells (`M1_SURFACE.md` §3). So `phase`
earns its place in stage 7's bucket key twice, by two routes, and for the same reason: trailing
`atr_bp` mis-sizes the bracket in a stable, direction-free, time-of-day-dependent way.

**The archive was restored to run it.** It had gone missing from the machine and the iCloud backup
`gc_data_manifest.md` documents did not exist; all 19 months were re-pulled for $64.20 and verified
**byte-identical** against the manifest, every `sha256` and byte count. The manifest was the real
backup.

**Steps 1–5 need no new data, no feed and no vendor decision**, and steps 2–4 have now been run on
the restored archive: If M1 returns no positive-EV cell
and M2 and M3 both land inside their own MDE, **that is three kill conditions firing on data already
paid for** — worth knowing before the spot-vendor question is reopened.

**On the held-out half.** Steps 2 and 3 are population statistics — nothing selects, tunes or fits —
so by `BASE_RATES.md`'s own reasoning they cost no out-of-sample data. Step 4 selects, and runs on
the training half only. The held-out half is spent once, at the end, on whatever is still alive.

**This track is not scheduled.** It takes no week from `plans/team/`, and saying so is deliberate —
the same move `2026-09-05-live-signal-pipeline-design.md` §8 made, so unscheduled research does not
quietly eat a product week.

---

## 7. The one open experiment

**Does top-of-book spread carry enough structure to filter on?**

On GC, quote data costs money **and** the variable is probably degenerate — GC sits at exactly one
tick the overwhelming majority of the time, which would make `spread_z` a z-score of a near-constant
with unstable tails. On spot, quotes **are** the entire feed: free, and spread genuinely moves.

So the test runs on spot, for nothing. **Route 2, Varad's call, 6 Sep.**

**Update 7 Sep — the precondition this section doubted is confirmed.** `SPOT_FEED_CHECK.md`
measured one London–NY hour of XAUUSD: spread runs **1.64 bp at p10 against 2.15 at p90, max
3.77**, so it genuinely moves and a trailing z-score is not a z of a near-constant. **That is the
precondition, not the result** — one hour, one session, one broker says the variable is
non-degenerate, and says nothing about whether it predicts anything.

**The caveat that survives it:** spot spread is a **broker pricing decision, not a market outcome** —
a dealer widens on its own risk policy and its own client flow, so two brokers disagree about the
same instant. The result is a legitimate yes/no on *whether spread structure predicts anything*. It
is **not** a threshold that transfers to GC or to another broker, and it must never be read as one.

---

## 8. How the tracks rejoin

Track A restarts on one of three triggers, and the architecture is shaped so that none of them
requires a rewrite:

1. **Track B finds a conditioning structure** — a vol state, a session phase — and the question
   becomes whether order flow adds anything *inside* that bucket. This is the most likely path and
   the most informative: `families.py` measured flow against a **pooled** null, and a bucket-matched
   one is a different and fairer test.
2. **Gate 1's option (b)** — restoring condition A. Still open, and it lands in the one arm whose
   sign was positive (+0.0184 on 77 legs, needing n ≈ 3,636 to prove).
3. **Enough tape accumulates** for the filtered exhaustion arm — roughly 2.5 years at its observed
   firing rate.

**When it restarts, flow enters as a veto layer.** It may suppress a Track B signal on GC; it may
never create one and never flip a side.

**That rule is what keeps the two tracks comparable.** If flow could create signals, GC and spot
would be running different strategies under one name, every cross-instrument comparison would be
meaningless, and the first time spot underperformed nobody could say whether it was the instrument
or the missing feature. Purely subtractive flow means the **signal set is identical on both
instruments** and only the **filtering** differs — which is a difference that can actually be
measured.

---

## 9. Open questions this file does not answer

1. **Is the product still an order-flow product?** §1.1's tension. The information claim holds; the
   edge measurement came back flat. Varad's and Shreyas's, and it interacts with licensing.
2. ~~**Does M1's geometry grid get committed before the sweep, and by whom.**~~ **ANSWERED 6 Sep —
   Varad, in `plans/team/strategy-precommit.md` §1, reviewed by Prathamesh.** 72 points, in
   multiples of the bar's own ATR rather than in bp or ticks, because the archive's own
   committed 70/20 bracket ranges over 5× in ATR terms between its quietest and loudest months.
   A pass line and a written prediction went in with it.
3. ~~**Does a Dukascopy XAUUSD download complete from this machine.**~~ **ANSWERED 7 Sep — yes**,
   `analysis/SPOT_FEED_CHECK.md`. 20,654 quotes for one London-NY hour, spread median 1.91 bp, and a
   +19 basis against our own GC archive for the same hour, which is cost of carry rather than the
   10× a guessed point scale would show. **The finding is why it looked unreachable:** a request
   without a browser User-Agent is RESET — no status, no body, a ~25s hang — which is
   indistinguishable from a dead host, and is very likely what `DELTA_CVD_FINDINGS.md` §4 recorded.
   **A negative infrastructure result that was never differentially diagnosed gated a whole route of
   this track.** Confirms §7's doubted precondition: spot spread is not degenerate the way GC's is.
   *(Closed in the file 9 Sep — `9d89e42` answered it and this list was not updated with it.)*
4. ~~**`MIN_SAMPLES` per cell in `reach.py`**~~ **ANSWERED 6 Sep — 400**, `strategy-precommit.md`
   §3. Derived, not picked: `horizon.n_for_rate(0.1644, 0.224)` = 327, where 0.1644 is the pooled
   archive null and 0.224 the highest per-bucket breakeven in it, rounded up. At the existing
   floor of 30 a cell needs a **+126%** relative lift before it can say anything, so a 30-leg
   cell is noise with a number attached. Many cells will return `forecast: null` and that is the
   correct answer, not a gap.
5. ~~**How much time the tick replay (step 5) gets**~~ — **ANSWERED 2026-09-11: 3 days**, written
   into `strategy-split.md` §5 before the first line of `replay.py` and spent one day on the tape
   walk proven against a hand-checked leg, one on the archive, one on the write-up. M4b was left
   out rather than absorbed, which is the budget doing its job.

---

## 10. The rules, collected

Everything above reduces to seven lines. If only this section survives, it is the load-bearing part.

1. **Portable or it does not belong in `features/portable.py`.** Both instruments, or neither.
2. **Basis points, never ticks**, everywhere except stage 9's labelled display conversion.
3. **`has_flow: False` raises. It never degrades.**
4. **No threshold has a default** — same as `strategies.py` and `regime_filter.py`. A number chosen
   while looking at the answer is a fit, not a filter.
5. **Every lift is reported against a mix- and side-matched null, with `mde_rate` beside it**, and
   with its N.
6. **Track B never modifies a Track A module.** Shared modules change additively, with Track A's
   tests as the gate.
7. **Flow is a veto layer when it returns.** It may suppress; it may never create or flip.
