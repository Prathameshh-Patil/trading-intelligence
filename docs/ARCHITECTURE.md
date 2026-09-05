# Architecture — what this is, and how the pieces hold each other up

**Written 2026-09-05.** A map for someone who has the repo open for the first time, or for one of
us in Week 8 having forgotten why a seam is shaped the way it is.

This file describes **what exists on disk today**, and says plainly where the thing described is a
type with no implementation behind it. It is not a plan — [`plans/team/`](../plans/team/README.md)
is the plan and [`plans/current.md`](../plans/current.md) is the live status. If this file and
those disagree, those win and this one is stale.

---

> **Two tracks since 2026-09-06.** This file describes the system as a whole and states the product
> thesis as order flow (§1). That thesis's core measurement came back flat — `FAMILIES.md` put both
> arms on their own matched null at −0.0058 and −0.0003, at power that would have caught a 30%
> relative lift — so the **order-flow track is parked** and an **L1-only strategy track** is active
> beside it. Its architecture, its `has_flow` boundary, and the rules that keep the two separable are
> in [`docs/strategy/ARCHITECTURE.md`](strategy/ARCHITECTURE.md). **Parked means nothing is deleted
> and no Track A module is modified.** Whether the *product* is still an order-flow product is open,
> and that file does not answer it either.

## 1. What the project is trying to achieve

**A retail order-flow tool for gold futures, sold to ten paying subscribers by 27 Nov 2026.**

The entire product thesis is one paragraph, and it is already written down in
[`apps/desktop/src/lib/engine/types.ts`](../apps/desktop/src/lib/engine/types.ts):

> `delta` and `cvd` are the numbers a screenshot can never contain — they need the aggressor side
> of every individual trade, and a rendered candle threw that away when it was drawn. Two sessions
> with identical OHLC can have opposite CVD.

That is the whole wedge. A trader looking at an MT5 or TradingView chart is looking at a lossy
projection: OHLC survives, *who initiated each trade* does not. Recovering the aggressor side needs
the raw tape, and once you have the tape you can compute things the chart structurally cannot show
— signed delta, session-reset CVD, absorption, trapped participants, size clusters.

So the product is:

- a **floating overlay** that sits on top of whatever chart platform the trader already uses,
- fed by a **live tick feed running on the trader's own machine under their own entitlement**
  (which is also the licensing position — see §7),
- showing order-flow state the chart underneath cannot,
- wrapped in discipline features — rules, journal, strategy review — that give it a reason to be
  open when the market is quiet.

### Two questions, deliberately answered in parallel

| | Question | Where it is answered | If the answer is no |
| :--- | :--- | :--- | :--- |
| **1** | Does a tradeable edge exist in GC order flow at all? | `services/signal-data` | The product has no core. [`phase-1-kill-week.md`](../plans/team/phase-1-kill-week.md) exists to find out in one week instead of six months |
| **2** | Can we ship something people pay for? | `apps/*`, `services/api`, `services/engine` | Different problem, still worth having built the shell |

These are run at the same time by different people on purpose. Question 1 is Varad's; question 2 is
mostly Prathamesh's; Shreyas grades both from the outside. §3 is the machinery that lets them
proceed without ever blocking each other.

---

## 2. The shape of the system

```
┌─ RESEARCH ─────────────────────────────────────────── services/signal-data ──┐
│  offline, Python 3.12, no server, no user                                    │
│                                                                              │
│  pull_futures_trades.py ──► Databento GLBX.MDP3 trades ──► parquet           │
│  pull_tbbo_validate.py  ──► quote-rule cross-check of the aggressor field    │
│                                                                              │
│  s1.py            load_ticks → add_delta → minute_bars → session_cvd         │
│      │                                                                       │
│      ├─ features/regime_filter.py    L1+L2 · which bars are worth signalling │
│      ├─ features/orderflow.py        cvd_persistence, vwap, vwap_distance    │
│      ├─ features/expansion.py        atr, bar_range, body_ratio              │
│      ├─ signals/engine.py            L3 · the 3-of-4 checker                 │
│      ├─ strategies.py                4 entry-only Stage-1 candidates         │
│      ├─ regimes.py                   unsupervised regime labelling (786 L)   │
│      ├─ backtest.py                  evaluate / summarize / report / null    │
│      ├─ stage1.py                    every candidate + null + perturbation   │
│      └─ horizon.py                   POWER — what could even be proven       │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                       six frozen seams · plans/team/contracts.md
                                    │
┌─ RUNTIME ──────────────────────────────────────────────── services/engine ──┐
│  Rust · DOES NOT EXIST YET · Week 3                                          │
│  live feed (Ironbeam) ──► DeltaBar / Outlier / FeedStatus over Tauri IPC     │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                    S2 · engine/types.ts  (frozen W1D1)
                    engine/mock.ts ✅   engine/real.ts ❌
                                    │
┌─ SHELLS ─────────────────────────────────────────────────────────── apps/ ──┐
│  desktop/     Tauri + React + TS, 460×820 — THE PRODUCT                      │
│  extension/   Chrome + Firefox MV3, activeTab only, dist committed           │
│  web/         landing page                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                        HTTP · S3 / S4 / S5
                                    │
┌─ BACKEND ────────────────────────────────────────────────── services/api ──┐
│  FastAPI + SQLAlchemy + Alembic + Postgres 17 (docker-compose)               │
│  GET  /health              liveness, declared on the app                     │
│  GET  /api/v1/health/db    readiness, SELECT 1                               │
│  POST /api/v1/analyze      selected text → Claude haiku-4-5 → 4 keys         │
└──────────────────────────────────────────────────────────────────────────────┘
```

Not in that stack, and deliberately so:

| Path | What it is |
| :--- | :--- |
| [`alltick/`](../alltick/README.md) | A **closed vendor evaluation**, kept as the record of why the answer was no. Not a dependency of anything. [`alltick/GOLD.md`](../alltick/GOLD.md) is the one file to read if AllTick comes back up |
| [`plans/`](../plans/current.md) | What we are doing, who owns it, what is left |
| [`daily_updates/`](../daily_updates/) | What happened on a day, and what proves it |
| [`docs/research/`](research/) | Literature triage |
| [`docs/superpowers/specs/`](superpowers/specs/) | Design specs written before implementation |

---

## 3. The idea that makes the whole thing work: contract-first parallelism

[`plans/team/contracts.md`](../plans/team/contracts.md) is the most load-bearing file in the repo.
Its rule:

> **Whoever owns a seam ships the type and a fake on the first day the seam exists. The consumer
> builds against the fake. The producer swaps in the real implementation later, behind the same
> type. Neither side ever waits.**

A fake is not a stub returning `null`. A fake returns **realistic, shaped, varying data** — enough
that the consumer discovers today that their layout breaks on a 7-digit CVD, rather than in Week 3
with a real feed.

This has already been proven once in this repo. The `/api/v1/analyze` contract was frozen on Day 1
(`sentiment` lowercase, `confidence` 0–100). On Day 3 the entire analysis implementation was
replaced — hand-written lexicon out, Claude in — **with zero changes to the extension.** Same four
keys, so nothing downstream noticed.

### The six seams

| Seam | Between | Status |
| :--- | :--- | :--- |
| **S1 · Tick record** | Varad → everyone | ✅ Frozen. Fixture landed 25 Aug (`14f5547`): `data/fixtures/gc_ticks_1session.parquet`, the 2026-07-16 GCQ6 session, 77,532 rows, in git. ⚠️ One pending amendment — see §5 |
| **S2 · Engine IPC** | Varad's Rust engine ← Prathamesh's UI | ✅ Type frozen W1D1 (`engine/types.ts`). Mock exists. **Real implementation does not.** One hole: `FeedCreds` is deliberately undefined until the vendor settles |
| **S3 · API key** | Backend ← desktop + web | ✅ Frozen W0D3, fixture landed early 25 Aug (`tests/fixtures/keys_fake.py`, all six branches on port 8001). Real route is W5D3 |
| **S4 · Journal sync** | Local-first, Prathamesh owns from W6 | Type defined. **Load-bearing property: the app never blocks on sync.** Conflict rule is last-write-wins by `updated_at`, *and the loser is kept* |
| **S5 · Payment → key issuance** | Web ← backend | Type defined. Website only sees the exit door (`GET /api/v1/keys/mine`); webhook verification and idempotency are invisible to it. **Webhooks arrive twice** |
| **S6 · Capture context** | Prathamesh's capture → Varad's engine | ✅ Frozen. The narrowest seam, narrow on purpose — see §4 |

### Freeze discipline

A frozen contract changes only by all three agreeing in standup, and the change lands as **one
commit that updates the type, the fake, the real implementation and both consumers together.**
Never half.

---

## 4. Four design decisions worth understanding before touching anything

### 4.1 The mock refuses to impersonate the real engine

[`apps/desktop/src/lib/engine/index.ts`](../apps/desktop/src/lib/engine/index.ts) picks an
implementation off `VITE_ENGINE=mock|real`. Asking for `real` before `real.ts` exists **throws at
startup** rather than falling back:

> Refusing to fall back to the mock: replayed 2026-07-16 ticks must never be mistaken for a live
> feed.

A UI quietly running on replayed July ticks while someone believes they are watching a live market
is the worst failure this seam can produce, so it is made structurally impossible rather than
documented as a caution.

The same instinct shows up in `FeedState`: `disconnected | connecting | live | **stale**`. `stale`
is connected-but-not-receiving, it looks identical to a quiet market, and the type comment requires
the four to be *"distinct enough to tell apart from three feet away."*

### 4.2 Capture produces context, never a number

S6's `CaptureContext` carries `symbol`, `timeframe`, `levels`, `confidence`, `capturedAt` — and
nothing else numeric. That absence **is** the enforcement, and the type says why:

> Adding one is a contract change needing all three in standup, because this is exactly the mistake
> that becomes tempting in Week 8 when a vision model returns something that looks like volume and
> it would be so convenient.

Screenshots give context. Delta comes from the feed. The two never mix, or the product's one honest
claim stops being true.

### 4.3 No threshold in the research stack has a default

`strategies.py`, `regime_filter.py` and `signals/engine.py` all take their numbers as
**required keyword arguments**. Not defaults, not module constants. The reason is written into each
docstring:

> A number chosen while looking at the answer is not a filter, it is a fit.

A signature that raises `TypeError` — and fails `mypy` — is the only enforcement that cannot be
forgotten. It means the code physically will not run until [`thresholds_selector.md`](../services/signal-data/thresholds_selector.md)
§6.1's numbers are committed by the person who carries the bias for them. Part B was filled
2026-09-04. **Part C is still empty, so nothing may be clustered.**

### 4.4 A claim and its evidence travel together

This is the repo's cultural rule and it shows up everywhere:

> "Endpoint works" is worth nothing; "15 tests pass, `ruff`/`mypy` clean, live curl returns the
> documented shape" is worth something. If it was not run, say so explicitly rather than implying
> it was.

Consequences you will notice while reading: the Tauri window is recorded as *"a window opens at the
right size — proven; the UI renders correctly in it — not proven"* until a screenshot existed; two
"done" extension checks are marked **closed on Prathamesh's account rather than on a logged
artefact**; the AllTick closure states that the repo measured a smoke sample and stopped, and that
*"AllTick has no OHLCV edge" is not something this repo measured.*

---

## 5. The research stack in detail

This is where question 1 gets answered, and it is the part of the repo with the most substance
behind it.

### 5.1 Data provenance

| | |
| :--- | :--- |
| Vendor | **Databento**, `GLBX.MDP3`, `trades` schema, parent symbology |
| Instrument | **GC** (COMEX gold futures) outright trades — NQ was pulled into scope and then dropped |
| Archive | 19 months, Jan 2025 – Jul 2026, **46,034,813 trades** (`analysis/gc_data_manifest.md`) |
| The July pull | 1,616,772 trades, **$2.52**, `8aece67` |
| Session | CME trading day **18:00 → 17:00 ET**, verified against the data: every gap >2h lands exactly on a Friday close or Sunday reopen. **EDT-specific** — a month crossing DST needs a real exchange calendar |

`data/` is gitignored with **one** carved-out exception, verified with `git check-ignore` rather
than by reading patterns: `data/fixtures/gc_ticks_1session.parquet`. Every billed `get_range()`
writes its raw DBN to `data/raw/` before pandas touches it, so a processing failure never costs a
second download.

> ⚠️ `services/signal-data/data/gc_trades.parquet` is **the only copy on any machine** of the July
> pull. Never `git clean -xdf` in this working copy — `-x` deletes exactly that, plus both `.venv`s
> and every `.env`. For a fresh-clone check, `git clone` into `/tmp`.

### 5.2 The aggressor field, and why it gets three paragraphs

Everything downstream is a signed sum, so the sign convention is the single point of failure.
Databento's `side` is the **initiating** side — `A`/"Ask" does **not** mean "printed at the ask".
Reading it the natural-language way inverts the sign and produces a mirror-image CVD that looks
entirely plausible.

Confirmed four independent ways:

| Check | Result |
| :--- | :--- |
| Buy/sell split | 48.32 / 47.79 |
| Tick-rule agreement | 83% both directions (an inverted mapping reads ~17%) |
| Delta ↔ return Pearson | **+0.50**, stable at 1/5/15-min (would read −0.50 if flipped) |
| Quote-rule reclassification (`pull_tbbo_validate.py`) | **99.65%** agreement across 75,578 comparable trades; 0 of 23 hours disagreeing in sign; footprint cross-check at 980/980 price levels, volume r=1.0000, delta r=0.9870 |

**The residual, which must be carried downstream:** session-total delta is method-dependent at the
**~15–20%** level (side field +1,842 vs quote rule +2,216). **Direction and shape are robust;
absolute magnitude needs an error bar.** `stage1.py`'s perturbation exists precisely to propagate
that error into any threshold denominated in contracts.

### 5.3 The known data traps

Each of these cost someone real time and is written into the code that hit it:

| Trap | What happens |
| :--- | :--- |
| Double `symbol` column | `to_df()` runs `map_symbols=True` and already attaches `symbol`; a definitions merge adds a second, so `df["symbol"]` returns a 2-D frame and `groupby` fails. **A synthetic dry-run could never have caught this** — hand-built frames don't carry that column |
| `uint32` negation | `size` is `uint32`, so `-df["size"]` wraps to ~4.29e9 instead of going negative. Cast to `int64` first |
| `'N'` aggressor | S1 declares `'B' \| 'A'`; the real data carries a third value where no aggressor was disseminated. **1.15%–5.23% of trades** across 19 months, ~double in roll months. Volume share tracks trade share within 0.2pp, so they are ordinary-sized, not blocks. **Pending contract amendment** |
| 421 duplicate rows | Genuine duplicates in the fixture where `drop_duplicates()` would shift session delta by **8%** |
| DST | The +2h session shift is EDT-specific and will be wrong across a DST boundary |

### 5.4 The layered signal stack

```
L1 + L2   features/regime_filter.py     is this bar worth signalling on at all?
              four gates, ANDed: regime kappa · CVD persistence · ATR floor
              · session interior · trend alignment
L3        features/{orderflow,expansion}.py    the features
          signals/engine.py                    the 3-of-4 checker over eligible bars
L4        backtest.py → stage1.py              measurement, null, perturbation
          horizon.py                           what could even be proven
```

Two things about this deserve to be read directly rather than summarised, because both are
corrections the code records against its own design:

**The regime gate is kappa, not raw survival.** The spec said `survival >= 0.92`. Reviewed against
the plot on 2026-09-04, raw survival turned out to select on *prevalence* — a regime holding 63% of
bars scores 0.63 by shuffling alone — so the threshold kept the one regime with no directional flow
and dropped both that had it. Normalised for base rate, the ranking **inverts**. The 0.92 number is
retired.

**3-of-4 produces 0 signals on 3,516 training bars, and that is the design's arithmetic, not a
bug.** Condition A (absorption) is a sanctioned stub returning zeros, so 3-of-4 is in practice
3-of-3. And conditions B and D *cannot* agree: B fires long at a new closing low for its window,
D fires long only on a bar that closed up on a big body — which at a new low it is not. On the
training half they co-fire on 26 bars and agree on direction on **zero** of them.

### 5.5 The kill gate

`horizon.py` is the file that stops this from being a story. It computes, per horizon, the minimum
detectable effect at α=0.05 / 80% power — **how much edge each horizon could even prove**, before
any strategy is run. It also carries its own caveat: adjacent signals share all but five minutes of
their leg, so their outcomes are not independent draws, which is *"harmless for a rule that fires a
few times a day; NOT harmless for order-flow rules, which fire in bursts."*

Its GC result and `ohlcv_edge.py`'s independent AllTick result agree: **spot gold and GC futures are
both random walks at 5/15/30m to within 0.4%**, measured from two directions that were not fitted to
each other. Unconditional structure is not where the edge is, if there is one.

---

## 6. The product stack in detail

### 6.1 `services/api` — FastAPI

Python 3.12, `uv`, SQLAlchemy + Alembic, Postgres 17 via `docker-compose`. The contract is frozen
and documented in [`services/api/README.md`](../services/api/README.md).

`POST /api/v1/analyze` sends selected page text to Claude (`claude-haiku-4-5`) and decodes the reply
through a Pydantic schema using structured outputs. **The schema is the enforcement** — a malformed
or half-written answer raises at the boundary rather than reaching the extension as a wrong-shaped
`200`.

What the schema does and does not enforce was **verified against the generated schema, not
assumed**: field names, types, the required set and the `sentiment` enum are enforced; numeric
bounds and list maximums are stripped by the SDK and survive only as description hints. So
`confidence: 50–95` and `1–4 signals` are things the prompt *asks for*, not guarantees.

CORS is a regex, not a list, because the popup's `Origin` changes on every unpacked reload — a
32-char id on Chrome, a UUID on Firefox.

`.env` is required and has no defaults: neither `DATABASE_URL` nor `ANTHROPIC_API_KEY`, so the app
and Alembic both fail fast rather than starting half-configured.

### 6.2 `apps/desktop` — Tauri, the actual product

React + TS + Vite in a native window, 460×820. Seven views: Home, Analyze, Flow, Journal, Rules,
StrategyReview, StrategyChange. The side-panel UI was copied in from `apps/extension` byte-for-byte
(`diff -q` confirmed), with `storage.ts` shimmed to `localStorage` and `capture.ts` to a
placeholder — both marked temporary.

Target behaviour is transparent, borderless, always-on-top, with a click-through toggle, floating
over a live MT5 terminal. **None of that is built yet.**

### 6.3 `apps/extension` — Chrome + Firefox MV3

The privacy posture is the interesting part. **No content script, no standing permission on any
site.** The popup reads the selection through `activeTab` + `chrome.scripting` at the moment it is
opened. A regression that restored `content_scripts` + `<all_urls>` was caught and reverted in
`955b374` by porting the `activeTab` approach into `capture.ts` rather than restoring the deleted
file, specifically so the narrow permission set survived.

`dist` is **committed**, so a fresh clone loads the extension with no build step. That buys
convenience and costs a discipline: it can go stale. Rebuild and commit `dist` in the same commit as
any `src` change. Vite hashes asset filenames, so a clean `git status` after `pnpm build` proves
`dist` is current.

`browser_specific_settings.gecko.id` is the add-on's permanent identity in Firefox. Changing it
after release makes existing installs a different add-on rather than an update.

### 6.4 The build trap

Root `pnpm build` is `pnpm --filter extension build` — **one of four projects.** `pnpm build:all`
is the real one. A green `pnpm build` says nothing about `apps/desktop` or `apps/web`.

---

## 7. Vendors, licensing, and why the architecture is shaped around them

| Track | Vendor | Status |
| :--- | :--- | :--- |
| **Historical / backtest** | **Databento** | Settled. The 19-month archive, S1's contract and the quote-rule validation all rest on it |
| **Live feed** | **Ironbeam** | Decided 3 Sep. Free L1/L2 for non-pro accounts. Its trade stream has an `as` (aggressor side) field whose **value semantics are undocumented** — treat as unvalidated until checked against real data, exactly as Databento's `side` was. **No historical L2/tick data via their REST API**, which is why the Databento archive matters rather than backfilling |
| **AllTick** | — | Closed 5 Sep. Gold is a 1 Hz top-of-book snapshot, book 1×1 on every update, `trade_direction` hardcoded across 402 pushes in two windows three hours apart, ~2% of ticks delivered. No CME futures at all |
| **Spot XAUUSD** | — | Cut 25 Aug. **No centralised volume**, so there is no delta to compute. Returns only as a *context-only* mode where rules and journal work and delta explicitly does not |

The licensing position the architecture assumes: **the engine runs on the user's machine and uses
the user's own data entitlement.** Ironbeam being a broker rather than a data reseller likely makes
that reading stronger — if each user connects through their own funded account, it is the same model
already assumed for MT5. **This is a reasoned inference, not legal advice, and not yet a written
answer from any vendor.** Confirming it is Shreyas's, and the whole feed architecture rests on it.

---

## 8. Honest status, 2026-09-05

### Real and verified

- `services/api` — endpoints, validation, CORS, error shapes, migrations at head. 20 test functions.
- `apps/extension` — builds, loads in Chrome and Firefox, end-to-end capture → analyze → verdict.
- The research stack — delta/CVD validated four ways, regime labelling, Stage-1 candidates, backtest
  harness, power analysis. **116 test functions** across `services/signal-data/tests/`, `ruff` and
  `mypy` clean. *(Counted, not run, at the time of writing.)*
- `apps/desktop` — a real AppKit window at the configured geometry; the home view renders correctly
  under `screencapture` (3 Sep).

### Built but unproven

- **Nothing in `apps/desktop` has ever been clicked.** Accessibility permission is ungranted; every
  interaction to date was fired programmatically. Six tiles, back button, drag region and five mock
  controls are all unexercised by a human.
- Five of the seven desktop views have never been looked at.
- **There is no JS test runner in this workspace at all.** `mock.ts`'s reconciliation against `s1.py`
  was verified by compiling standalone under Node — repeatable, uncommitted, outside any CI, while
  Weeks 1–3 are entirely UI work against that fake.

### Does not exist

`services/engine` (the Rust live engine) · `engine/real.ts` · `FeedCreds`'s real shape ·
Part C of the threshold selector · an Ironbeam account or credentials · any overlay behaviour ·
S4 and S5 implementations.

### The open question that dominates everything

Week 1 — **5–11 Sep**, one week right of the original calendar — is the kill week. It decides
whether the signal track survives. Both independent measurements so far say the unconditional
series is a random walk, `3-of-4` currently fires zero signals by construction, and no strategy has
been backtested end to end on the real archive.

---

## 9. The rules that are cheap to break and expensive to notice

1. **Python 3.12 only.** `requires-python = ">=3.12,<3.13"` is load-bearing. If a package won't
   resolve, change the package, not the bound.
2. **Lockfiles are the source of truth.** `uv.lock` and `pnpm-lock.yaml`. Let the tools write them;
   dependency changes get their own reviewed commit.
3. **Never `git clean -xdf` here.** See §5.1.
4. **`pnpm build` is not the whole workspace.** Use `pnpm build:all`.
5. **The Firefox add-on id is permanent.**
6. **A frozen contract moves in one commit or not at all.**
7. **Every repo change updates `plans/current.md` and `daily_updates/YYYY-MM-DD.md`** — status in
   one, evidence in the other. This applies to Claude as much as to any of us.
