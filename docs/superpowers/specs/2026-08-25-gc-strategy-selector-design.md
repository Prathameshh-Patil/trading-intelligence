# GC strategy selector — design

**Date:** 2026-08-25 · **Owner:** Varad · **Status:** §7's `s1.py` and `backtest.py` built and tested (25 Aug, night); **no strategy defined and no backtest run**
**Scope:** personal research tool. **Not a product feature.** See §1.

---

## 1. What this is, and what it is deliberately not

Given the trader's own defined GC strategies, the live order-flow state, and journal history —
decide which strategy fits the current moment, and say how many ticks it expects to be right by.

**It is a research tool for Varad's own GC trading.** It does not ship to subscribers, it is not in
`plans/team/`, and it takes no week from the twelve-week schedule.

That boundary is load-bearing for two reasons and it must not erode quietly:

- **Regulatory.** Flagging an outlier delta print is information. Telling a trader which strategy to
  use is a recommendation. Shreyas's Week 1 Tuesday CA call asks whether the product as described
  triggers SEBI Research Analyst registration — and the answer depends on which product is
  described. As a personal tool this asks nothing of that call. **The day anyone proposes shipping
  it, that question gets re-asked before a line of UI is written.**
- **Validation.** A product feature would need a gate as hard as the Week 3 one. A research tool
  needs to convince exactly one person, who is also the person with every incentive to be
  convinced — which is what §6 exists for.

This resolves `plans/current.md` #1 by making the own-model row **not a schedule item**, rather than
by finding it a week.

---

## 2. Two stages, and the first one can kill the second

### Stage 1 — define the candidates and prove they are worth anything

3–4 GC strategies, hand-defined as plain functions over a bar frame. Entry condition, exit
condition, nothing else. Drawn from what the engine can actually compute: delta outliers, CVD
divergence, absorption, footprint imbalance.

Each is backtested **standalone** across the available month(s): direction accuracy, magnitude
distribution (§4), sample count, against a random-entry null with matched count and holding period.

> **This is a kill gate.** If no strategy has a standalone edge, stop. There is nothing to select
> between and Stage 2 is moot. That outcome is worth days, not weeks, and finding it out cheaply is
> the main reason Stage 1 goes first.

### Stage 2 — learn which regime favours which strategy

Cluster into **2–3 regimes, not more**, on state features only, then measure per-strategy
performance per regime.

Stage 2 exists because the alternative is worse. In a pure rules design each strategy would declare
its own regime preconditions — "this one works in trending flow" — and **that assertion is itself an
unvalidated story.** Learning it from data is more honest. It is also more dangerous, which is what
§6 is for.

**Regime features — all derived from minute bars, all _state_, never _outcome_:**

| Feature | Definition |
| :--- | :--- |
| Realized volatility | stdev of 1-min returns over a trailing window |
| CVD slope and persistence | is flow one-directional or churning |
| Directional efficiency | `abs(CVD) / price range` — the findings already use this (2026-07-16 was selected at 0.90) |
| Session phase | Asia / London / NY, from the ET timestamp |

**No clustering input may be derived from forward returns.** If one is, the design leaks and every
number after it is fiction. This is the single easiest way to destroy the whole exercise and it will
not announce itself.

---

## 3. The decision filter — a seam, left empty on purpose

A later `decision_filter.py` holds **Varad's own trading rules** applied on top
of the selector's output: what not to take, when not to trade, position sizing, session
restrictions, "never during NFP".

**It is authored by the trader, not learned, and not written by Claude.** The spec's job is to leave
the seam clean and not pre-empt its contents.

**Contract:** the filter is a pure function over the selector's output plus the current context.
It can veto and it can size. It cannot change the strategy choice, and it cannot invent a signal
that the selector did not produce.

```
select() -> Decision{strategy, side, expected_ticks, confidence, regime, n_samples}
                                |
                       decision_filter(Decision, Context) -> Decision | None
```

Returning `None` is a veto and is a first-class outcome, not an error. **The filter is applied and
measured separately** — every backtest reports pre-filter and post-filter numbers side by side, so
it is always visible whether the filter helped or merely reduced sample size until the numbers
looked better.

---

## 4. Magnitude — how many ticks, not just which way

Direction alone is not the deliverable. For a strategy that says *long*, the question is **how far**,
and it is answerable only as a distribution.

### Units, pinned

GC is COMEX gold, **100 troy oz**, minimum tick **0.10 = $10.00 per contract**; a *point* is
1.00 = 10 ticks = $100. **"Pips" is FX/MT5 terminology and does not apply to GC futures** — the spec
uses ticks throughout, with dollars per contract alongside. This is pinned here because the project
has already lost a work item to spot-vs-futures confusion (A2), and an unstated unit is how the
second one happens.

### What every backtest reports, per strategy and per regime

| Metric | Why |
| :--- | :--- |
| Realized move at 5 / 15 / 30 min, in ticks | the horizon-dependent answer |
| **MFE** — max favourable excursion, ticks | how far it went your way at best |
| **MAE** — max adverse excursion, ticks | how far against before it worked; this is what sizing keys off |
| Median, IQR, p10, p90 | **distribution, never a point estimate** — these are fat-tailed and a mean is a lie |
| Hit rate, direction | share correct |
| Expectancy, ticks and $/contract | the number that matters |
| **N** | sample count, always, next to every figure above |

**The honest form of the answer is "median +X ticks, IQR [a, b], N=n" — never "it predicts X ticks."**
With ~22 sessions the interval will be wide, and reporting it wide is the deliverable.

### The error bar that is inherited, not introduced

`DELTA_CVD_FINDINGS.md` §3: **session-total delta is method-dependent at ~15–20%** (side field
+1,842 vs quote rule +2,216). Direction and shape are robust; magnitude is not.

**Any strategy whose entry threshold is a delta magnitude inherits that ~15–20% directly.** A rule
that fires at "delta > 200" is a rule that fires somewhere between roughly 170 and 240 depending on
classification method. Every magnitude figure this project produces carries it, and it must appear
in the results output rather than in a footnote nobody reads. If a strategy's edge disappears when
the threshold is perturbed by 20%, the edge was never there.

---

## 5. Feed migration — Databento → quantfeed

**Everything in this section is unconfirmed.** Claude has no reliable knowledge of a vendor named
"quantfeed" — pricing, coverage, symbology, API shape, or licensing. Nothing here is asserted about
it; the items below are what must be confirmed before any code is written against it.

### What the swap costs — less than it looks

Databento appears in exactly **two files**, both pull scripts (`pull_futures_trades.py`,
`pull_tbbo_validate.py`). `compute_delta_cvd.py` reads the parquet through the **S1 column
contract** and does not know or care who produced it.

So the migration is: **rewrite the pull layer to emit the same six S1 columns.** Everything
downstream is untouched. This is the S1 contract doing precisely the job `contracts.md` designed it
for — the same move that let the entire analysis implementation be swapped on Day 3, lexicon out and
Claude in, with **zero changes to the extension**, because the four keys never moved.

### What does NOT transfer, and it is the load-bearing one

**The aggressor-side validation is vendor-specific.** The 99.65% quote-rule agreement validated
*Databento's* `side` semantics — specifically that `A`/"Ask" means **seller-initiated**, which reads
backwards in plain English and is exactly the trap `DELTA_CVD_FINDINGS.md` §1 warns about.

quantfeed will have its own convention. **It must be re-validated from scratch or every delta sign
in the project is a coin flip**, and a flipped CVD looks entirely plausible — that is the whole
reason §1 exists.

- `pull_tbbo_validate.py` is already the harness for this and is reusable given L1 quotes.
- **With L3 the quote rule is unnecessary** — order-by-order data determines the aggressor exactly,
  which is *strictly stronger* than what closed the Week 3 gate. If L3 is real and affordable, the
  validation gets better, not merely re-done.

### Confirm before writing any code against it

- [ ] Aggressor/side field: does it exist, and what exactly does its convention mean
- [ ] L1 / L2 / L3 coverage for **GC on COMEX** specifically, not "futures" generally
- [ ] History depth — how far back, and at what price. §6 needs months, not one
- [ ] Symbology: contract-level (`GCQ6`) vs continuous, and how rolls are represented
- [ ] Timestamps: exchange time vs receipt time, and timezone
- [ ] **Distribution licensing** — the bring-your-own-feed architecture exists because Databento's
      external distribution rights start at $1,750/mo. A cheaper vendor may be cheap because it does
      not grant them
- [ ] Cost of one GC month, for comparison against Databento's measured **$2.52**

> ⚠️ **Time-sensitive.** Shreyas sends three identically-worded distribution-licence emails on
> **Monday 31 Aug** — Databento, Rithmic, Tradovate. If the feed vendor is changing, that list is
> wrong before it is sent. Raise it at Wednesday's standup, not after.

### Do not delete the Databento path yet

Keep both pull scripts until quantfeed has produced a month of GC that reconciles against the
existing `gc_trades.parquet` — same session, same trade count within tolerance, same aggressor
split, same hourly delta signs. **The existing validated month is the reference for validating the
new vendor**, and deleting it removes the only ground truth available. Same reasoning that kept
`NQ` in `INSTRUMENTS` after the drop.

---

## 6. Guardrails — without these this is overfitting with a nice diagram

The project's documented failure mode (`plans/team/varad/thresholds.md`) is *falling in love with a
signal and never running the null test*, and the stated defence is a git commit timestamped earlier
than the results. **A selector choosing between four strategies has four times the researcher
degrees of freedom of a single rule.** Every one is a chance to tell yourself a story about a
threshold, and it will be a convincing story told by someone with every reason to believe it.

1. **Pre-commit `thresholds_selector.md` before the first backtest runs.** Same mechanism and same
   rules as `varad/thresholds.md` — including the line that file calls the most important one:
   *what result would make me say no.* If that line cannot be written, nothing is being tested.
2. **Pre-commit the regime definitions.** Clustering fitted, labelled, committed — **before** anyone
   looks at per-strategy performance inside those regimes.
3. **Two nulls, and the second is the one that matters.**
   - *Stage 1 null:* random entry, matched count and holding period.
   - *Stage 2 null:* **does learned regime selection beat random regime assignment with the same
     regime proportions?** This is what catches fitting noise, and Stage 2 lives or dies by it.
     Beating "always use the single best strategy" is table stakes, not a result.
4. **Walk-forward, never in-sample.** Fit regimes on the first half, test selection on the second.
5. **N next to every number.** Any cell under ~30 signals is reported and **not acted on**.
6. **Threshold perturbation.** Re-run every headline result with delta thresholds moved ±20% (§4).
   An edge that does not survive its own known error bar is not an edge.

### The predicted outcome, recorded now

With ~22 sessions split walk-forward into ~11 and ~11, **the most likely honest result is
_inconclusive_** — too few signals per regime-strategy cell to distinguish skill from noise.

That is a real result, not a failure, and it is written here **before** the work so it cannot be
quietly reinterpreted afterwards.

**The cheapest fix is more data, not more modelling.** One GC month cost **$2.52**; six months is
roughly **$15** on Databento's measured rate. That single spend is worth more to Stage 2 than any
modelling choice in this document. It is a decision for Varad and Prathamesh — and it interacts with
§5, since the vendor may change what a month costs.

---

## 7. Files

All under `services/signal-data/`, offline against the parquet. No new service, no new dependency
beyond what the analysis scripts already use.

| File | Purpose |
| :--- | :--- |
| `s1.py` | ✅ **landed 25 Aug.** The S1 contract read once — load, delta, minute bars. Not in this table when it was written; the traps have to live somewhere and every file below reads through it. `compute_delta_cvd.py` was folded onto it, which is how it was found that that script read the S1 fixture as zero delta, silently |
| `strategies/gc.py` | the candidates as data — entry, exit, nothing else |
| `backtest.py` | ✅ **landed 25 Aug.** One strategy over the month → §4's full metric set. Clock-based horizons, session-bounded windows, `n` and a sub-30 `thin` flag on every summary, and §6.3's side-matched null. **Never yet run on a real strategy** — §6.1 comes first |
| `regimes.py` | features, clustering, labels |
| `select.py` | regime→strategy map, plus both nulls |
| `decision_filter.py` | **§3's seam. Varad authors it. Empty stub until then** |
| `thresholds_selector.md` | pre-committed, before the first backtest runs |

`backtest.py` is **Week 4's harness arriving early and scoped down.** If it earns its keep here, it
*is* the Week 4 harness rather than a second one — the only place this research tool is allowed to
touch the twelve-week schedule, and it touches it by saving work.

Style follows the repo: plain functions over frames, no class hierarchy, no framework.

---

## 8. Blocked on

- ~~`services/signal-data/data/` does not exist on this machine.~~ **Partly unblocked the same
  evening.** Prathamesh pushed the **S1 fixture** in `14f5547` — the 2026-07-16 GCQ6 session, 77,532
  trades, verified against the contract. So there is now one real session on disk.

  **That is enough to build and test Stage 1's machinery, and not enough to run it.** One session
  cannot produce a backtest — §6 needs months. The full month (1.6M trades) is still only on
  Prathamesh's disk, correctly gitignored, and remains an ask.

  **Two data facts from that fixture bind any strategy code written here** (both now in
  `contracts.md` S1): `aggressor_side` carries a real `'N'` value on 2.34% of trades, so
  `map({"B": 1, "A": -1})` silently yields NaN; and 421 duplicate rows are genuine multi-fills,
  where a reflexive `drop_duplicates()` moves session delta by **8%**.
- **quantfeed's §5 checklist** — unanswered, and it determines whether Stage 1 runs against the
  existing Databento month or waits.

---

## 9. Open questions

1. **Which 3–4 strategies?** Not decided. Stage 1 cannot start without them, and they should be
   written by the person who trades them, not derived from the data (that is Stage 2's job, and
   doing it in Stage 1 leaks).
2. **Bar size for regime features** — 1-minute exists; 5- or 15-minute may be the right regime
   granularity. Cheap to test, so test rather than assume.
3. **Session-level or window-level regimes?** A session is one label per day (~22 labels, very
   thin). A rolling window gives more labels but they are autocorrelated, which inflates apparent
   sample size. **This choice materially changes how much the walk-forward split can support** and
   it should be decided explicitly rather than fallen into.
4. **Does the journal feed Stage 2?** `JournalEntry` carries `rMultiple` and `outcome`, but there is
   no journal data yet. Deferred until there is.

---

## 10. Not verified

**Updated 25 Aug (night): §7's `s1.py` and `backtest.py` are built, tested and clean.** Nothing
else here has been. In particular **no backtest has been run on any strategy**, so every
expectation in §2, §4 and §6 — including §6's recorded prediction of *inconclusive* — remains
exactly as unverified as when it was written.

Originally, and true of everything not listed above: nothing in this document has been built or run. What is verified is the repo state it was fitted to:
the Databento coupling surface (two files, checked by grep), the S1 column contract, what
`compute_delta_cvd.py` actually computes (delta, session CVD, minute bars, footprint — read from its
signatures), the ~15–20% magnitude residual, the existence and emptiness of the `Strategy` type, and
the absence of `data/` on this machine.

**Everything about quantfeed is unconfirmed and explicitly marked so in §5.**
