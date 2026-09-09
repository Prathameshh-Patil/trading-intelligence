# Live signal pipeline — design

**Date:** 2026-09-05 · **Owner:** Varad · **Status:** design only. **Nothing in this file is built, and two of its seven stages are blocked on things that do not exist yet.**
**Scope:** the product's core loop — what happens between a trader asking "buy or sell?" in the overlay and a number appearing on their screen.

---

## 0. The goal, in the owner's words

> When someone uses our extension — a Tauri floating window beside an MT5-like platform — and asks
> "is it buy or sell at that moment", the frontend reads the screen via OCR and passes it to the
> backend analysis, which identifies regime, ATR, CVD, order book, footprint. That goes to a bot
> model we train. The bot returns a signal with reasoning. The signal travels to a decision file
> where filters decide how many pips this trade will move. A feedback loop structures the JSON into
> human-readable form and the signal ships.
>
> **The goal: accurate trade signals with exactly how many pips it will travel, so that anyone can
> trust that many pips and place an order with huge lots to make profits.**

This document takes that as the brief. It changes two things in it and nothing else. Both changes
are forced by measurements already in this repo, both are named in §2, and **neither costs the
product anything the brief actually wanted.**

---

## 1. The one-sentence restatement this design builds

> **For the instrument and moment the trader is looking at, emit a side, a calibrated probability
> that it is right, and a distribution of how far it travels before it goes against them — with the
> historical base rate that distribution came from, and a standing measurement of whether that base
> rate holds up.**

"Exactly how many pips, guaranteed" and the sentence above differ in exactly one way: the second is
falsifiable. That is the whole difference, and it is the reason the second one is sellable and the
first one is not.

---

## 2. The two corrections, and the evidence forcing them

### 2.1 OCR cannot produce CVD, order book, or footprint

This is the product's own founding fact, pointed backwards. From
[`apps/desktop/src/lib/engine/types.ts`](../../../apps/desktop/src/lib/engine/types.ts):

> `delta` and `cvd` are the numbers a screenshot can never contain — they need the aggressor side of
> every individual trade, and a rendered candle threw that away when it was drawn.

So did the screenshot of that candle. **A vision model cannot recover a quantity the chart never
drew.** Delta, CVD, footprint and the order book are all per-trade or per-level aggressor data. MT5's
chart displays none of it; MT5's `real_volume` for spot gold is empty, which is the finding that cut
A2 on 25 Aug — spot gold has no centralised volume, so there is nothing to sign.

[`contracts.md`](../../../plans/team/contracts.md) S6 froze this boundary and names this exact
request as the predicted failure:

> **Capture produces context. Capture never produces a number that appears in a signal.** […] adding
> one is a contract change needing all three in standup, because this is exactly the mistake that
> becomes tempting in Week 8 when a vision model returns something that looks like volume and it
> would be so convenient.

**The correction:** OCR and the feed are two independent inputs that merge at the feature step. OCR
supplies *context* — which instrument, which timeframe, which levels the trader drew, what they are
asking about. The engine supplies *numbers*. The user experience is unchanged: they still get an
answer about the chart in front of them. The numbers simply do not come from pixels.

**If the trader's chart is an instrument we have no feed for, the honest output is "no signal — no
feed for XAUUSD."** That is a UI state to render, not an error, and S6's `symbol` is a free string
rather than a `'GC'` literal precisely so that case is representable.

### 2.2 "Exactly N pips, guaranteed" is not a thing this data supports

Measured twice in this repo, on two instruments, through two code paths that were not fitted to each
other:

| Source | Instrument | Result |
| :--- | :--- | :--- |
| [`horizon.py`](../../../services/signal-data/horizon.py) | GC futures, Databento | Random walk at 5/15/30m |
| [`alltick/packages/edge/ohlcv_edge.py`](../../../alltick/packages/edge/ohlcv_edge.py) | Spot gold, AllTick | Random walk at 5/15/30m, **to within 0.4%** |

A random walk has no predictable magnitude. And a point forecast of *how far* is strictly harder than
one of *which way*: it requires getting direction right and then the size on top of it, so its error
bar is never smaller than the direction call's.

`horizon.py` also bounds the ceiling from the other side. It computes the **minimum detectable
effect** at α = 0.05 / 80% power per horizon — how much edge each horizon could even *prove* on a
given sample. A model claiming an edge below its horizon's MDE is making a claim the data cannot
adjudicate, no matter how it was trained.

**The correction:** the output is a conditional distribution, not a scalar. And **this repo has
already written the honest version once.** From
[`features/regime_filter.py`](../../../services/signal-data/features/regime_filter.py):

> The ATR threshold is 40 ticks: the volatility floor at which the 70-tick target becomes reachable
> inside D4's 6-bar (30-minute) forward window. […] P(move >= 70) is 45.8% in the 35-40 bucket,
> 55.3% in 40-45.

That is a pip forecast. It says: *in this volatility bucket, over this horizon, the target is reached
this often.* A trader can size on that, because it is a base rate that repeats. Nobody can size on
"70 pips guaranteed" — they can only find out once, and the finding-out is the whole loss.

[`backtest.py`](../../../services/signal-data/backtest.py) already records **MFE and MAE per trade,
signed in the trade's own favour direction**, which is exactly the raw material this distribution is
built from. The measurement exists. What does not exist is anything that conditions it and serves it.

### 2.3 On "huge lots"

Out of scope for this design, and named here so it does not arrive later as a surprise:

- **Position sizing is the user's, never ours.** The output carries a probability and a distribution;
  it does not carry a lot size, and no field in §6's contract may become one.
- A performance guarantee attached to a paid signal changes the answer to the SEBI Research Analyst
  question that `plans/current.md` records as **open and unanswered**, pending Shreyas's CA call.
  Ship the calibration, not the guarantee, and that question keeps the answer it was drafted to get.
- The 2026-08-25 selector spec drew the same line for the same reason: *"flagging an outlier delta
  print is information; telling a trader which strategy to use is a recommendation."* A guaranteed
  pip count is further past that line than either.

---

## 3. The pipeline

```
 ┌──────────────┐                      ┌──────────────────┐
 │ OCR /capture │  CaptureContext      │  Ironbeam feed   │  ticks
 │  (frontend)  │  ── context only ──┐ │  engine (Rust)   │  ── every number ──┐
 └──────────────┘  S6, FROZEN        │ └──────────────────┘  S2, FROZEN        │
                                     │                                         │
                                     ▼                                         ▼
                            ┌────────────────────────────────────────────────────┐
                     A + B  │  features/  regime · atr · cvd_persistence          │
                            │             vwap_distance · footprint · outliers    │
                            └────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
                            ┌────────────────────────────────────────────────────┐
                       C    │  model — "the bot"                                  │
                            │  → side, P(direction), reasoning trace              │
                            └────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
                            ┌────────────────────────────────────────────────────┐
                       D    │  decision — the filters                             │
                            │  → conditional pip DISTRIBUTION + tradeable gate    │
                            └────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
                            ┌────────────────────────────────────────────────────┐
                       E    │  explain — JSON → prose the trader reads            │
                            └────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
                            ┌────────────────────────────────────────────────────┐
                       F    │  outcome log → CALIBRATION                          │
                            │  the loop that decides whether any of it is true    │
                            └────────────────────────────────────────────────────┘
```

Six stages. **The order of building them is F, B, A, C, D, E** — see §9.

---

## 4. Stage A · Capture — what OCR actually supplies

Owner: Prathamesh. Contract: **S6, already frozen.** No change proposed.

```ts
export type CaptureContext = {
  symbol: string          // 'GC' | free text if unrecognised
  timeframe: string       // '1m' | '5m' | '15m' | ...
  levels: number[]        // price levels the trader has drawn
  confidence: number      // 0-100, how sure the extraction is
  capturedAt: number
}
```

**Permitted extensions**, each of which is still context and none of which is a signal input on its
own:

| Field | Why it is context and not a number |
| :--- | :--- |
| `question` | The trader's actual words. Routes the answer, does not compute it |
| `visibleRange` | `{ priceLow, priceHigh, timeFrom, timeTo }` — what is on screen. Frames the answer's scope |
| `drawnObjects` | Trendlines, boxes, fibs. **The trader's own thesis**, which is worth restating back to them |
| `platform` | `'mt5' \| 'tradingview' \| ...`. Needed for the unit question in §6.4 |

**Forbidden, permanently:** any OCR-derived price, volume, delta, CVD, bid/ask size, or footprint
number. Not as a fallback when the feed is down, not as a cross-check, not behind a flag. **If the
feed is down the answer is "no signal — feed stale", and `FeedState` already has a `stale` value
specifically so that state is representable rather than silently guessed at.**

`confidence` gates the *context*, not the numbers: a low-confidence symbol read means ask the trader
which instrument they mean, not degrade the signal.

---

## 5. Stage B · The engine — where every number comes from

Owner: Varad. Contract: **S2, already frozen.** **`services/engine` does not exist.** This is the
single largest missing piece in the whole pipeline.

Already in the type: `DeltaBar` (o/h/l/c, volume, delta, cvd, bidVol, askVol), `Outlier`
(absorption | trapped | cluster, with score), `FeedStatus`.

**Two things §0 asks for that S2 does not currently carry**, both needing a contract amendment
through the standup rule — type, fake, real implementation and every consumer in one commit:

| Missing | Proposed shape | Note |
| :--- | :--- | :--- |
| **Footprint ladder** | `FootprintLevel { price, bidVol, askVol, delta }[]` per bar | `compute_delta_cvd.py` already builds this offline. This is the same object, live |
| **Order book** | `BookLevel { price, size }[]` per side, depth N | **Blocked on a vendor fact.** Ironbeam advertises free L1/L2 for non-pro accounts; nobody has held that connection yet, and `plans/current.md` #9 records that no account or credentials exist |

**Ironbeam's aggressor field is unvalidated.** Its trade stream has an `as` field whose value
semantics are undocumented (`0` in their example). It gets the same treatment Databento's `side` got
before it was trusted: a `pull_tbbo_validate.py`-equivalent quote-rule cross-check against real data
before a single number derived from it reaches a user. **Databento's field needed that check and
turned out to mean the opposite of its natural-language reading.** Assume nothing.

---

## 6. Stages C and D · The bot, and the decision file

### 6.1 What the model may and may not be given

**Inputs** — all state, all trailing, all computed by `features/`, never re-derived here:

regime label and kappa · ATR · CVD persistence · CVD slope · VWAP distance · bar range and body
ratio · delta z-score · footprint imbalance and stacking · session phase · outliers in the window ·
distance to the trader's drawn levels (from Stage A).

**Never given, at any point, under any framing:**

- Any quantity derived from a forward return. This is the single easiest way to destroy the exercise
  and **it will not announce itself** — the 2026-08-25 spec says the same thing about clustering, for
  the same reason.
- The held-out half. Everything to date is the training half (≤ 2026-07-19, 13 sessions, 3,516 bars),
  and that is the one asset that cannot be bought back once spent.

### 6.2 The model's output

```
side          'long' | 'short' | 'none'
p_direction   float 0-1, CALIBRATED — see §7
reasoning     which features fired, with their values. Not prose.
```

`reasoning` is a structured trace, not a sentence. Prose is Stage E's job, generated *from* the
trace. A model that writes its own English explanation is a model that can write a persuasive one for
a wrong answer, and there is no way to tell those apart downstream.

`'none'` must be a frequent, unembarrassing output. **A tool that answers every time is a tool that
is guessing most of the time.**

### 6.3 The decision file's output — the contract that carries the whole product

This is the shape the trader's trust rests on. Proposed as **S7**; not frozen until all three agree.

> ## ✅ AMENDMENT — proposed 2026-09-10 by Prathamesh. **AGREED 3 of 3. S7 is frozen.**
>
> | | |
> | :--- | :--- |
> | Prathamesh | ✅ proposed, and implemented in `forecast.ts` |
> | Varad | ✅ **approved 2026-09-10** — he owns `reach.py` and flagged the mismatch three times |
> | Shreyas | ✅ **approved 2026-09-10** — the presentation call, which is his to make |
>
> **How the last two approvals were obtained, stated rather than implied:** both were given
> verbally on the day. Varad's went directly to Prathamesh and Shreyas's was relayed by
> Varad, so **neither is a logged artefact from the moment** — the same basis rows #2 and #8
> of `plans/current.md` are closed on. Recorded here because that is where a contract's
> provenance belongs, and recorded honestly because a signature nobody can point at later is
> worse than an unsigned contract.
>
> **Shreyas's sign-off was the load-bearing one, not a formality.** This amendment is
> entirely about how a probability is *presented* to a trader — a band rather than a
> midpoint, `pNeither` shown so a low `p(target)` is not misread as a high `p(stop)`,
> no suggested bracket. `plans/current.md`'s ownership table puts domain validation with
> him: *"if Shreyas says the signal looks wrong, that stops the sprint."* A contract about
> not misleading a trader is exactly the thing he is the reviewer for.
>
> **What freezing does and does not mean here.** §6.3's rule was "not frozen until all three
> agree"; all three agree, so the shape is settled and
> [`apps/desktop/src/lib/engine/forecast.ts`](../../../apps/desktop/src/lib/engine/forecast.ts)
> is now the contract rather than a proposal. **`contracts.md`'s freeze discipline binds from
> here**: any further change needs all three again, in one commit carrying the type, the fake,
> the real implementation and every consumer together. Never half.
>
> **It is small now and will not stay small.** Today the type, the fake and one consumer live
> in `apps/desktop`; there is **no real implementation and no `services/api` route**. Writing
> those is not a contract change — it is filling slots this contract already specifies — but
> the first change to the *shape* after they exist is a four-file commit, not a one-file one.
>
> **The draft below was written 5 Sep against Track A and does not fit the table that now
> exists.** `reach.py` shipped 10 Sep (`analysis/REACH.md`) and serves a different shape.
> Varad flagged the mismatch three times without resolving it — `strategy-precommit.md` §10,
> `REACH.md` §6, and `prathamesh/reach-table-explained.md` §7 — each time saying the same
> thing: *"Both need a room decision, not a patch."* This is that decision, proposed by the
> side that has to render the numbers.
>
> **The resolution is implemented and running** in
> [`apps/desktop/src/lib/engine/forecast.ts`](../../../apps/desktop/src/lib/engine/forecast.ts),
> with a fake and a UI consuming it. Four changes, each one something the draft cannot express:
>
> | Draft | Proposed | Why |
> | :--- | :--- | :--- |
> | `bucket.regime` | `phase` + `volState` + `instrument` | `regimes.py` clusters on `cvd_slope`/`cvd_persistence`, is parked, and **does not port to spot at all**. The real key is `instrument × atr_bp × phase × vol_state × side`. The bucket a trader audits has to be the bucket the number came from. |
> | `reach[].p` | `p` **and** `pMax` | The tie band. `p_target` resolves a same-bar tie to the stop, `p_target_max` to the target, and bar data cannot say where between them the truth is. `REACH.md` §3 measured it: median 0.0019, **max 0.107** at the tight corner, 8.2% of served rows undecided. One number there is a precision the data does not have. |
> | `horizonBars: 6` | `horizonMinutes: 15 \| 30 \| 60` | `m1_sweep.HORIZONS` is **minutes**, against 5-minute bars. Two units that look alike and differ by 2× — the same class of error as `DELTA_CVD_FINDINGS.md`'s inverted side. |
> | `mfe` / `mae` required | nullable, **null today** | `reach.SERVED` is `n, p_target, p_target_max, p_stop, p_neither` — stage 7 serves no excursion quantiles at all. Kept rather than deleted, because deleting them is a scope call for the room; typed `| null` so nothing can render an invented quantile. |
>
> **Also added**, because the table serves them and a trader needs them: `pStop` and `pNeither`
> per bracket. `p_neither` is frequently the largest of the three, and without it a low
> `p(target)` reads as a high `p(stop)` when it is usually "nothing happened in time".
>
> **Nothing about the draft's rules changes** — no `guaranteedPips`, no lot size, `forecast: null`
> valid and common, `suggested` derived from `reach` or null. Those are why the contract exists.
>
> The original draft is preserved below for the record.

```ts
export type PipForecast = {
  /** How the bucket was defined. The trader can audit this. */
  bucket: {
    regime: string          // 'trending-flow' | ...
    atrBucket: string       // '40-45'
    horizonBars: number     // 6
    n: number               // historical signals matching. If below MIN_SAMPLES → no forecast
  }
  /** Distribution of maximum favourable excursion, in TICKS. See §6.4. */
  mfe: { p25: number; median: number; p75: number }
  /** Maximum adverse excursion. Negative only when the trade actually went adverse. */
  mae: { median: number; p75: number }
  /** P(reach target before hitting stop), per candidate target. */
  reach: { target: number; stop: number; p: number }[]
  /** Derived from `reach`, not chosen freely. */
  suggested: { target: number; stop: number } | null
}

export type Signal = {
  side: 'long' | 'short' | 'none'
  pDirection: number
  forecast: PipForecast | null      // null when n < MIN_SAMPLES or side is 'none'
  reasoning: ReasoningTrace
  tradeable: boolean
  notTradeableReason: string | null // 'feed stale' | 'no feed for symbol' | 'n too small' | ...
  asOf: number
  feed: FeedStatus                  // never omit. A stale feed invalidates everything above
}
```

**Rules that make this contract mean something:**

1. **No `guaranteedPips` field, ever.** Its absence is the enforcement, the same way S6 enforces
   itself by having no numeric field.
2. **No lot size, no risk amount, no account-relative anything.** Sizing is the trader's.
3. **`forecast: null` is a valid, common answer.** Below `MIN_SAMPLES` the honest output is no
   forecast, not a wide one.
4. **`suggested` is derived from `reach`, never picked.** If no `(target, stop)` pair clears the
   committed pass line, `suggested` is `null` — a signal with no tradeable target is a signal not to
   take.
5. **No threshold in this stage has a default.** Same rule as `strategies.py`, `regime_filter.py` and
   `signals/engine.py`, for the same reason: *a number chosen while looking at the answer is not a
   filter, it is a fit.* The pass line is `thresholds_selector.md` §6.1's call and Varad's.

### 6.4 The unit trap — pips are not ticks

**"70 pips" and "70 ticks" are different numbers, and this pipeline spans both worlds.**

| | |
| :--- | :--- |
| GC (COMEX futures, our data) | 1 tick = **0.10** = $10 per contract |
| MT5 XAUUSD (what the trader is looking at) | broker-dependent — commonly 0.01 or 0.10 to a "pip" |

Every internal number is **ticks**, matching `backtest.py`, `horizon.py` and `regime_filter.py`.
Conversion to whatever the trader's platform calls a pip happens **once, in Stage E, at the display
boundary**, using `platform` from Stage A — and the displayed unit is labelled. A forecast computed
on GC ticks and rendered as MT5 pips without conversion is off by up to 10×, in the direction that
looks better.

---

## 7. Stage F · The calibration loop — the part that decides whether any of this is true

The brief describes the feedback loop as JSON formatting. **Formatting is Stage E.** The loop's real
job is the one measurement the entire product's trustworthiness reduces to:

> **When the model says 61%, does it happen 61% of the time?**

Every emitted signal is logged with its inputs, its forecast and its bucket. Every logged signal's
realised outcome is recorded when its horizon closes. The standing report is a **reliability
diagram**: predicted probability on one axis, realised frequency on the other, bucketed.

Why this and not hit rate:

- **It is falsifiable weekly**, on live data, without a backtest.
- **It is the one claim a subscriber can verify themselves**, which is what makes it worth paying
  for.
- **It degrades gracefully.** A model that is 55% accurate but *says* 55% is a useful tool. A model
  that is 70% accurate but says 90% is a liability, and hit rate alone cannot tell them apart.
- It catches regime drift, vendor changes and silent feature bugs that a frozen backtest cannot.

**The loop reports. It does not retrain automatically.** An auto-retraining loop on live outcomes
means the model chases the last week, and nobody can say afterwards which version produced which
number. Retraining is a decision with a date and an owner.

**Non-negotiable:** the log records what was shown to the trader **at the moment it was shown**,
including `feed`, `bucket.n` and the exact thresholds in force. A calibration measurement against
retrospectively-adjusted forecasts measures nothing.

---

## 8. What is blocked today, and by what

| Stage | Blocked on | Where it is tracked |
| :--- | :--- | :--- |
| **B · engine** | `services/engine` does not exist (Week 3). No Ironbeam account or credentials | `plans/current.md` #9 |
| **B · order book** | Ironbeam L2 unverified; `as` field semantics undocumented | `plans/current.md` C1 |
| **C · model** | **There is no training set.** `signals/engine.py` fires **0 signals on 3,516 training bars** — A is a sanctioned stub, and B and D are structurally opposed: they co-fire on 26 bars and agree on direction on **zero** of them | `plans/current.md`, Week 1 D4 |
| **C · model** | Part C of `thresholds_selector.md` is empty, so nothing may be clustered | `plans/current.md` #1 |
| **D · decision** | Needs `backtest.evaluate` output bucketed by regime × ATR — the harness exists, the bucketing does not | — |
| **A · capture** | OCR extraction itself is unwritten; `capture.ts` on desktop is a placeholder shim | `plans/current.md` Day 2 |
| **all** | Nothing in `apps/desktop` has ever been clicked (accessibility permission ungranted), and there is no JS test runner in the workspace | `plans/current.md` Next preamble |

**This design is not scheduled.** It takes no week from `plans/team/`, and saying so here is
deliberate — the same move the 2026-08-25 spec made, so an unscheduled model does not quietly eat
Week 6.

---

## 9. Build order, and why it is not the diagram's order

**F → B → A → C → D → E.**

| | Stage | Why here |
| :--- | :--- | :--- |
| 1 | **F · logging** | Build the outcome log *before* the first signal exists. A loop retrofitted after the fact has no history, and the first weeks are exactly when calibration is most informative |
| 2 | **B · engine** | Longest lead time, hardest dependency, and every stage downstream is a fake until it lands |
| 3 | **A · capture** | Independent of B — it produces context, so it can be built and tested against a fixture with no feed at all |
| 4 | **C · model** | Cannot start until the Week 1 D4 signal-set question is resolved. Run `horizon.py`'s power table **before** training, not after: if the claimed edge is below the horizon's MDE, the training run cannot settle anything |
| 5 | **D · decision** | Pure function of C's output plus historical buckets. Testable entirely offline |
| 6 | **E · prose** | Last, and cheapest. It has no judgement in it — every number it renders was decided upstream |

Each of 2–6 ships a **fake first**, per `contracts.md`: realistic, shaped, varying data — a
7-digit CVD, a 40-character symbol, an `n` of 3, a `null` forecast, a stale feed — so the consumer
finds out today that their layout breaks, not in Week 8 with a live feed.

---

## 10. Kill gates

Three, in order. Each one can end the work below it, and finding that out cheaply is the point.

**Gate 1 — is there a signal set at all?** Week 1 D4. `3-of-4` currently produces zero signals by
construction. `plans/current.md` names three options — run on the 46 unfiltered 2-of-4 signals,
restore condition A as a bar-level absorption rule, or treat the B/D opposition as a specification
error. **None of the three is a threshold to tune**, and the choice is Varad's.

**Gate 2 — does the edge clear its own MDE?** `horizon.py`, before any training. An edge below the
minimum detectable effect at the available sample size is not a small edge; it is an unmeasurable
one.

**Gate 3 — is the forecast calibrated out of sample?** Held-out half first, then live. **This is the
gate the product's core claim lives or dies on**, and it is the only one that cannot be passed by
being clever — it can only be passed by being right.

---

## 11. Open decisions — Varad's, not this file's

1. **Gate 1's three options.** Which one, and on what evidence.
2. **`MIN_SAMPLES` for a bucket.** Below it, `forecast` is `null`. The number is a commitment about
   how little evidence is too little, and it must be set before any bucket is looked at.
3. **The `reach` pass line** — what `p` makes a `(target, stop)` pair worth suggesting.
4. **Whether S7 gets frozen**, and when. Until it is, Stage E and any UI build against a fake.
5. **What the model is.** Nothing here requires it to be learned; the `reach` table alone, computed
   over `signals/engine.py`'s output, is a complete Stage C+D with no model in it. **That version
   should be built first and beaten**, because a base-rate table that nothing outperforms is the
   correct product.
6. **Whether the pip forecast ships to subscribers at all**, or stays a personal tool the way the GC
   strategy selector did. §2.3's regulatory line depends on the answer, and the answer is
   Shreyas's CA call, not this file's.
