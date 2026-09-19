# Project map — every block of code, the pipeline as built, and the pipeline as intended

**Written 2026-09-18.** A single orientation document for someone who needs the whole picture: what
this product is, what a user will actually experience, every directory and module on disk, which
parts are real and which are typed fakes, and the two architecture diagrams that matter — **what
exists today** and **what it must look like on the last day**.

> **Precedence.** [`plans/current.md`](../plans/current.md) is the live status and
> [`plans/team/`](../plans/team/README.md) is the plan. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) is
> the product architecture and [`docs/strategy/ARCHITECTURE.md`](strategy/ARCHITECTURE.md) the
> research one. **If this file disagrees with any of those, they win and this one is stale.** This
> is a map, not a source of truth.

---

## 1. What the product is

**A retail order-flow tool for gold futures, sold to ten paying subscribers by the Week 12 gate.**

The whole thesis is one paragraph, and it lives in `apps/desktop/src/lib/engine/types.ts`:

> `delta` and `cvd` are the numbers a screenshot can never contain — they need the aggressor side of
> every individual trade, and a rendered candle threw that away when it was drawn. Two sessions with
> identical OHLC can have opposite CVD.

A trader on MT5 or TradingView is looking at a **lossy projection**. OHLC survives; *who initiated
each trade* does not. Recover the raw tape and you can compute what the chart structurally cannot —
signed delta, session-reset CVD, absorption, trapped participants, size clusters.

So the product is:

- a **floating overlay** on top of whatever chart platform the trader already uses,
- fed by a **live tick feed on the trader's own machine, under their own vendor entitlement**
  (which is also the licensing position — the app never redistributes market data),
- showing order-flow state the chart underneath cannot,
- wrapped in **discipline features** — rules, journal, strategy review — so it has a reason to be
  open when the market is quiet.

### 1.1 The honest caveat at the top

`docs/ARCHITECTURE.md` §1 states the thesis as order flow — *"that is the whole wedge"*. The
**order-flow track is parked**: `FAMILIES.md` put both arms on their own matched null at −0.0058 and
−0.0003, at power that would have caught a 30% relative lift. An information advantage that produces
no edge is not yet a product. **Whether this is still an order-flow product is logged as open
question #1 and is a product decision, not an architecture one.**

---

## 2. What the user experiences, end to end

This is the part no diagram shows. Ordered as a real person meets it.

### 2.1 Discover → sign up → approved (the website, `apps/site`, Next.js App Router)

**Updated 2026-09-18 for `feat/vision-hub` (unmerged).** The product is Vision Hub; the site has a
left rail rather than a top nav; there is no checkout on the path to a key.

| Route | File | What the visitor does |
| :--- | :--- | :--- |
| `/` | `app/page.tsx` | Landing — the claim, in one screen, then the price and the questions |
| `/features`, `/use-cases`, `/services` | `app/*/page.tsx` | The chapters that used to follow the fold, each under its own header |
| `/pricing` | `app/pricing/page.tsx` | **One currency at a time, toggled, never side by side.** A visitor who can see both prices is being shown a decision they did not ask to make |
| `/signup`, `/login` | `app/*/page.tsx` | Account creation and return; both land on `/account` |
| `/account` | `app/account/page.tsx` | **Signed up → Awaiting approval → Approved → Activated in the app.** The licence key, once a person has approved the account; rotate; optional payment proof; tickets; sessions. Live over SSE. `/key` and `/checkout` redirect here |
| `/support`, `/contact`, `/policy` | `app/*/page.tsx` | Tickets; *"There are three of us."*; terms, privacy, refunds |

The admin queue is no longer a page on this site: it is **`apps/admin`**, a separate static export
on its own origin (Approvals, Users, Keys, Tickets, Waitlist, Audit, Settings), refusing any
non-admin token with one sentence. Both sites draw on `packages/ui` and speak through
`packages/contracts`, whose client owns the token lifecycle so no page ever sees a JWT.

**The website only ever sees the exit door.** Per S5 as amended, it reads `GET /api/v1/keys/mine`
(404 with a `reason` until approved) and `GET /api/v1/keys/mine/activation`. Approval is of the
*account*, by an admin; payment proof is an attachment the admin can see and is not a gate.

### 2.2 Install → activate

1. Download the desktop app (Tauri bundle, macOS today; Windows and Linux untested).
2. Launch. A **380 × 820 transparent, borderless, always-on-top panel** appears.
3. Paste the licence key on the app's **Licence screen** — the only screen an unactivated app
   shows. The desktop calls `POST /api/v1/keys/validate` (S3) and re-checks every six hours.
   **`valid: false` is a `200`, not a `401`** — the app must distinguish "your key is bad" (the
   licence screen, locked) from "we could not reach the server" (keep working for seven days from
   the last good check, pill reads *Offline*), because those demand opposite responses from the
   user. The key goes to the OS keychain (`licence.rs`), the same path as the feed credentials.
4. Enter **feed credentials** — vendor username/password/server. These go
   **webview → Rust → OS keychain** and nowhere else (`creds.rs`, `creds.ts`). JavaScript never
   writes the secret to anything that persists; `localStorage` holds only the *vendor name*, so the
   shell knows which keychain entry to open next launch.

### 2.3 The daily loop

The trader has MT5 or TradingView open. The panel floats above it.

- **Position memory** — the panel reopens exactly where they left it, **keyed by monitor
  arrangement**, so a desk with two screens and a laptop on a train each keep their own spot, and
  unplugging a monitor never strands the window off-screen (`placement.rs`).
- **Click-through** — armed from the toolbar crosshair, the panel passes clicks to the chart
  underneath. It is **whole-window**: Tauri's `setIgnoreCursorEvents` has no per-pixel `forward`
  option, which is a real limitation and is recorded rather than hidden.
- **`Cmd/Ctrl+Shift+K`** — an OS-level global hotkey that disarms click-through **even when the
  chart app holds focus.** This exists because the original `Escape` handler needed the webview to
  hold keyboard focus, and Cmd-Tab did not reliably return it — leaving the window armed,
  unclickable, and unrecoverable short of killing the process.

The nine views (`apps/desktop/src/views/`):

| View | What the trader sees |
| :--- | :--- |
| `HomeView` | Active strategy, today's count, win rate, expectancy, and the tiles |
| `FlowView` | **Order flow** — live delta, session CVD, ask/bid volume, close, flagged outliers, and unsigned-volume disclosure |
| `ForecastView` | **The reach table** — what this bucket did at each bracket over 19 months, *or nothing, honestly* |
| `AnalyzeView` | Screen capture → directional read with confidence and signals |
| `RulesView` | Guardrails and live breaches |
| `JournalView` | Log and review trades |
| `StrategyReviewView` | How the plan is performing |
| `StrategyChangeView` | Edit thesis and criteria |
| `FeedCredsCard` | Vendor credentials, keychain-backed |

### 2.4 Two rules the UI enforces, not merely documents

1. **Every probability renders as a band, never a midpoint.** `p` and `pMax` both, always. One
   number where the bars tie is a precision the data does not have.
2. **Rows render in grid order, never value order.** Sorting by `p` would quietly make the UI the
   chooser that `reach.py` refuses to be — *whatever lands on top of a list reads as the
   recommendation*, whether or not anything called it one.

And the operational fact nobody should discover in production: **the warm-up is ~120 minutes, not
60.** `volState` reads `rv_slope`, two chained 60-minute windows, so a freshly connected feed serves
`forecast: null` for two hours. That is correct rather than broken, and the UI renders it as a
**countdown to a real clock time — never a spinner, never an error.**

### 2.5 The browser extension (`apps/extension`)

**Rebuilt 2026-09-19 as the desktop overlay in browser form.** A Manifest V3 extension for
Chrome and Firefox: a popup for the licence key (the same `@vision-hub/core` state machine the
desktop runs, over `chrome.storage`), a service worker that holds the key and the alerts
WebSocket (`WS /api/v1/ws`, authenticated by the key in its first frame), and a content script
on four hosts only -- `*.tradingview.com`, `*.ctrader.com`, `trade.mql5.com`,
`web.metatrader.app` -- that mounts a draggable, collapsible panel in a shadow root. **Sync
chart** reads symbol / timeframe / last price from the page on the trader's click and keeps it
in the page; alerts render by tier (breaking → banner, signal → badge, analysis → list). The
side panel and its `/analyze` call are gone. `docs/ARCHITECTURE.md` §6.3 records the amended
permission principle; `apps/extension/README.md` the build and the harness.

---

## 3. The one idea holding the codebase together

[`plans/team/contracts.md`](../plans/team/contracts.md) is the most load-bearing file in the repo:

> **Whoever owns a seam ships the type and a fake on the first day the seam exists. The consumer
> builds against the fake. The producer swaps in the real implementation later, behind the same
> type. Neither side ever waits.**

A fake is **not** a stub returning `null`. A fake returns realistic, shaped, varying data — enough
that the consumer discovers *today* that their layout breaks on a 7-digit CVD, rather than in Week 3
against a real feed.

**Proven once already.** `/api/v1/analyze` was frozen on Day 1 (`sentiment` lowercase, `confidence`
0–100). On Day 3 the entire implementation was replaced — hand-written lexicon out, Claude in —
**with zero changes to the extension.**

### 3.1 The seams

| Seam | Between | State |
| :--- | :--- | :--- |
| **S1 · Tick record** | Varad → everyone | ✅ Frozen. Fixture `gc_ticks_1session.parquet`, 2026-07-16 GCQ6, 77,532 rows, in git. ⚠️ **One pending amendment, unvoted since 26 Aug** — §3.2 |
| **S2 · Engine IPC** | Varad's Rust engine ← Prathamesh's UI | ✅ Type frozen W1D1. Mock exists. **Real implementation does not** |
| **S3 · API key** | Backend ← desktop + web | ✅ Frozen. `keys_fake.py`, all six branches. Real route is W5D3 |
| **S4 · Journal sync** | Local-first, Prathamesh from W6 | Type defined. **The app never blocks on sync.** Last-write-wins by `updated_at`, *and the loser is kept* |
| **S5 · Payment → key issuance** | Web ← backend | Type defined. Webhooks arrive twice |
| **S6 · Capture context** | Capture → engine | ✅ Frozen. Narrowest seam, deliberately |
| **S7 · Pip forecast** | Varad's table → Prathamesh's UI | ✅ Frozen 3 of 3, 10 Sep. **Route exists; real implementation does not** |
| **S8 · `Instrument`** | Varad → both lanes | ✅ Frozen 3 of 3, 11 Sep |
| **S9 · The bars frame** | Either loader → both lanes | ✅ Frozen 3 of 3, 11 Sep, **on the amended text** |
| **S13 · `ExpansionFeatures`** | Both lanes → the scorer | ✅ Frozen 18 Sep, before any feature code |

### 3.2 The one contract defect still open

**S1 declares `aggressor_side` as `'B' | 'A'`. The real data carries a third value, `'N'`** — no
aggressor disseminated (auction, implied, off-book). The contract's own row count of 77,532 already
includes them, **so the count and the type as written cannot both be true.**

Queued for 26 Aug, routed to the 28 Aug gate, drafted in full in
`plans/team/varad/2026-08-28-gate-note.md` with the replacement wording ready. **It has never been
put to a vote.**

It matters more than the percentage suggests: unsigned rows contribute nothing to delta or CVD, so
**delta is least complete exactly when the active contract underneath it is switching** — roll
months run ~3.75% against ~1.92% mid-cycle. And there is a live trap: the month parquets spell it
`unknown`, not `'N'`, so anyone checking by filtering `aggressor_side == 'N'` **gets zero rows and
concludes it is not real.** That already happened once, on 3 Sep.

---

## 4. Repository map — every directory

```
trading-intelligence/
├── apps/
│   ├── desktop/          Tauri v2 + React overlay — the product
│   ├── extension/        Chrome / Firefox side panel — capture + analyze
│   ├── site/             Next.js marketing, pricing, checkout, key, admin
│   └── web/              older build, superseded by site/
├── services/
│   ├── api/              FastAPI — analyze, health, forecast
│   ├── signal-data/      the entire research stack (~9,100 lines)
│   └── market-worker/    EMPTY — a directory and nothing else
├── packages/contracts/   shared types (currently empty on disk)
├── docs/
│   ├── ARCHITECTURE.md           the product
│   ├── strategy/ARCHITECTURE.md  the research track
│   ├── strategy/                 four-l1-strategies, strategy-architecture,
│   │                             strategy-reconciliation, xauusd-regimes
│   ├── decisions/                gate documents
│   ├── research/                 background
│   └── superpowers/specs/        design specs, newest is magnitude-expansion
├── plans/
│   ├── current.md        LIVE STATUS — the single most-read file
│   └── team/             contracts.md, gates.md, roles.md, strategy-split.md,
│                         strategy-precommit.md, week-00/01, phase-1..4,
│                         prathamesh/, varad/, shreyas/
├── daily_updates/        one file per working day, the narrative record
├── alltick/              AllTick vendor evaluation — kept as the record of why not
├── infra/                docker-compose: Postgres 17
└── tests/                cross-cutting
```

---

## 5. The research stack — `services/signal-data`

~9,100 lines. **518 tests passing.** `ruff` and `mypy` clean.

### 5.1 Data acquisition and validation

| Module | Lines | Purpose |
| :--- | ---: | :--- |
| `pull_futures_trades.py` | 445 | Databento GC pulls, with a cost-estimate flow that returns a number **without spending anything** |
| `pull_tbbo_validate.py` | 462 | Quote-rule reclassification — **99.65% agreement** with `SIDE_MAP` across 75,578 trades, which closed the delta-validation gate by an independent *method* rather than an independent platform |
| `verify_settlement_close.py` | 221 | Resolved a 12.2-point gap against TradingView as settlement-window-vs-last-trade |
| `cut_s1_fixture.py` | 211 | Cuts the committed S1 fixture; where `'N'` was found |
| `dukascopy.py` | 155 | Spot XAUUSD tick decoder (`.bi5`) |
| `spot.py` | 175 | Spot bars from the **mid**, `spread_bp` in its own column, resume by hour |
| `spot_s3.py` | 119 | **S3 transport** — the route that replaced the throttled HTTP path |
| `export_fixture_json.py` | 83 | Fixture export for the app |
| `s1.py` | 102 | Tick load, minute bars, session CVD |
| `calendars.py` | 103 | Session and news calendars |
| `windows.py` | 42 | Trailing-window helpers, shared so two files cannot disagree |

### 5.2 Features

| Module | Lines | Lane |
| :--- | ---: | :--- |
| `features/portable.py` | 469 | **The Track B surface.** Both instruments or it does not belong here |
| `features/volatility.py` | 279 | Yang-Zhang σ, GARCH(1,1)-t |
| `features/structure.py` | 173 | Session windows, news lockout, sweep and reclaim |
| `features/regime_filter.py` | 176 | Named the intrabar-ordering problem replay later answered |
| `features/hurst.py` | 108 | DFA and variance-time |
| `features/orderflow.py` | 104 | **Track A, parked.** GC only |
| `features/expansion.py` | 74 | ATR and expansion primitives |
| `features/frame.py` | 90 | **S13** — `FEATURES` is the exact column set; `require()` rejects **missing and extra** |

### 5.3 Measurement and strategy

| Module | Lines | Purpose |
| :--- | ---: | :--- |
| `backtest.py` | 307 | `evaluate`, `excursions`, `first_touch`, `first_touch_from`. **One first-touch convention, and it lives here** |
| `m1_sweep.py` | 315 | M1 geometry sweep — the EV surface everything is quoted against |
| `m2_magnitude.py` | 198 | Vol momentum, `vol_state` |
| `m3_profile.py` | 347 | Session + event conditioning |
| `m3b_drift.py` | 135 | Directional intraday drift |
| `reach.py` | 261 | **Stage 7** — the served table. *A lookup, not a chooser* |
| `replay.py` | 644 | **Step 5 + M4b** — tick replay and path ordering |
| `strategies.py` | 320 | `m1_geometry`, `m2_vol_momentum`, `m3_session_event` |
| `horizon.py` | 220 | `mde_rate`, sigma/power tables |
| `base_rates.py` | 157 | The null |
| `calibration.py` | 152 | Append-only; `settle` cannot invent history |
| `families.py` | 181 | Track A's four families — the measurement that parked the track |
| `regimes.py` | 786 | **Track A, parked.** Clusters on `cvd_slope` / `cvd_persistence` |
| `fsm.py` | 194 | §15 state machine |
| `classifier.py` | 99 | §8 calibrated logistic → `p_E` |
| `tuning.py` | 214 | Purged walk-forward, unresettable trial counter, the haircut |
| `e3_cost.py` | 95 | E3's cost model |
| `pipeline.py` | 123 | S13 frame assembly, end to end |

### 5.4 Published results (`analysis/`)

| Document | The finding |
| :--- | :--- |
| `DELTA_CVD_FINDINGS.md` | Delta validated by quote rule. **Session-total delta is method-dependent at ~15–20%** — direction and shape robust, magnitude needs an error bar |
| `BASE_RATES.md` | The null |
| `FAMILIES.md` | Both Track A arms flat on their own null → **the track is parked** |
| `M1_SURFACE.md` | GC bracket geometry is **a random walk minus cost** |
| `M1_EXPANDING.md` | M1 conditioned on EXPANDING |
| `M2_MAGNITUDE.md` | Vol momentum |
| `M3_CLOCK.md` | The clock conditions volatility but **produces no edge** |
| `M3B_DRIFT.md` | Directional intraday drift |
| `REACH.md` | 116 of 144 cells clear the floor — 81%. **`phase` and `vol_state` are not independent** |
| `REPLAY.md` | The nearer barrier is touched first; the tie rule is a blanket answer to a per-bracket question |
| `M4_PATH.md` | Bars carry the MFE/MAE sequence 95.8% of the time — **the PDE's blocker was never there** |
| `SPOT_FEED_CHECK.md` | Dukascopy over HTTP is finished as a bulk source from this address; MT5 is a 3-month source, not 19 |
| `E0_TRANSPORT.md` | **S3 transport verified — XAUUSD ticks reachable back to 1997** |

---

## 6. The research pipeline

### 6.1 Track B's nine stages

```
sources → normalise → portable features → strategies → legs → null + power
       → reach table → calibration → product surface
```

### 6.2 Build order and state

| | Step | Owner | State |
| :--- | :--- | :--- | :--- |
| 1 | `instruments.py`, inject `TICK`, `atr_bp` — the portability seam | Varad | ✅ 6 Sep |
| 2 | **M1** geometry sweep, 19 months | Varad | ✅ 7 Sep |
| 3 | **M3** session + event | Prathamesh | ✅ 6–7 Sep |
| 4 | **M2** vol momentum | Varad | ✅ 7 Sep |
| 5 | **Tick replay** | Prathamesh | ✅ 11 Sep |
| 5b | **M4b** path ordering | Prathamesh | ✅ 12 Sep |
| 6 | Route-2 spot feed, portable refit | both | ⛔ **the last prerequisite** |
| 7 | `reach.py` — the served table | Varad | ✅ 10 Sep |

**What it has found is consistently negative, and that is the result.** No cell clears the cost
floor. `ev_sym` is positive on 4.4% of served rows with a median at the cost floor. Stage 7
tabulates; it does not select.

### 6.3 The new block — spot XAUUSD magnitude expansion (18 Sep →)

Spec: `docs/superpowers/specs/2026-09-18-magnitude-expansion-design.md`. A different question on a
different instrument, with a **new seam frozen before any feature code**.

```
bars(5m) ─► §2 Yang-Zhang σ @ 12/48/288 ─┐
           §2 GARCH(1,1)-t, m-step var  ─┴─► R̂₆₀ ─► filter R̂₆₀ > $15/oz
                                                      quality R̂₆₀/median > 1.20
           §6 Hurst: DFA + variance-time ──► H₁₅ₘ, agreement
           §7 3-state HMM {Chop, Build, Expansion} ──► P(B_t), P(E_{t+1})
           §9 sweep of Asian extreme → reclaim ≤ 30s ──► event
                                                          │
           §8 logistic on survivors ──► p_E ───────────────┤
           §13 deterministic score ─────────────────────────┤
                                                            ▼
           §15 FSM ─► limit @ 50% of reclaim wick, 20s expiry ─► §10 stop/target ─► §11 size
```

⚠️ **§7's observation vector lost `OFI_z`, `CVD_z` and `λ_t` with the tape** — five of eight remain,
and **E4 tests whether a 3-state HMM is identifiable on five observations before it is wired in.**

**The experiment programme**, each with a prediction committed *before* its code exists:

| | Question | Owner | State |
| :--- | :--- | :--- | :--- |
| **E0** | The transport — S3 coverage, earliest date, cost | Prathamesh | ✅ ticks back to **1997**, cross-check exact |
| **E1** | Is the spec's own $15/oz filter ever satisfied? | Varad | ⛔ prediction unwritten |
| **E2** | Does the 16-condition funnel produce ≥100 events? | Varad *(delegated from Prathamesh)* | ⛔ prediction unwritten |
| **E3** | The cost floor, and where §10's stop range starts | Varad | ◐ arithmetic half built; empirical half blocked |
| **E4** | Is a 3-state HMM identifiable on 5 observations? | Varad | ⛔ Day 3 |
| **E5** | Does order flow add anything? (GC control) | either | optional — *prices what the spot decision costs* |

---

## 7. The product pipeline

### 7.1 `apps/desktop` — Tauri v2 + React

```
src-tauri/src/
  lib.rs        global hotkey, webview logging, placement wiring
  placement.rs  position memory, keyed by monitor-arrangement signature
  creds.rs      feed credentials → OS keychain, and nowhere else
  main.rs       entry
src/
  SidePanel.tsx    shell, routing, drag regions
  lib/engine/      types.ts · mock.ts · forecast.ts · forecastMock.ts · index.ts
  lib/             feed.ts · creds.ts · capture.ts · clickThrough.ts ·
                   context.ts · rules.ts · storage.ts · webviewLog.ts
  views/           nine views (§2.3)
  ui/              Icons · components · motion · theme.css
```

**`VITE_ENGINE=mock|real`** selects the engine. Asking for `real` before `real.ts` exists is a
**startup error, not a silent fallback** — *"a UI quietly running on replayed July ticks while
someone believes they are watching a live feed is the worst failure this seam can produce."*

**15 Rust tests.** `cargo clippy` clean.

### 7.2 `services/api` — FastAPI

```
app/main.py                     app + CORS (extension ids, localhost, tauri://)
app/api/routes/health.py        /health, /api/v1/health/db
app/api/routes/analyze.py       POST /api/v1/analyze        → Claude
app/api/routes/forecast.py      GET  /api/v1/forecast/table → the reach table
app/api/routes/alerts.py        GET  /api/v1/alerts?since=  (licence key) · POST/GET /api/v1/admin/alerts
app/api/routes/ws.py            WS   /api/v1/ws             the licence-key socket: alerts + key events
app/forecast.py                 loads + validates the served table
app/analysis.py                 the Claude call
app/db/, app/models/user.py     SQLAlchemy + Alembic, Postgres 17
```

**37 tests pass, 1 fails** (`test_database_health`, Postgres not running locally), 5 skipped
(live API tests, run only with `LIVE_API_TESTS=1`).

### 7.3 What is real and what is a fake, stated plainly

| Piece | State |
| :--- | :--- |
| Overlay window, transparency, always-on-top, click-through, hotkey, position memory | **Real**, macOS only |
| Nine views | **Real**, rendering |
| Engine (delta/CVD) | **Fake** — `mock.ts` replays the committed July session at 10× |
| Forecast table | **Real numbers**, served over HTTP; the *cell the moment is in* is still derived from a timestamp |
| `/analyze` | **Real** (Claude) |
| Key validation | **Fake** — `keys_fake.py` |
| Payments, webhooks, key issuance | **Not built** |
| Live tick feed | **Not built, and no vendor account exists** |
| `services/market-worker` | **Empty** |
| `packages/contracts` | **Empty** |

---

## 8. Architecture as built today

```
                          ┌───────────────────────────────────────────┐
                          │  RESEARCH  (services/signal-data)         │
                          │                                           │
  Databento GC ──19 mo──► │  s1 ─► portable features ─► strategies    │
  46M trades, on disk     │         │                      │          │
                          │         └─► backtest ─► m1/m2/m3 ─► reach │
  Dukascopy S3 ──────────►│  spot_s3 ─► spot ─► features/frame (S13)  │
  XAUUSD, to 1997         │                         │                 │
                          │  volatility · hurst · structure · fsm     │
                          │  classifier · tuning · e3_cost            │
                          └──────────────────┬────────────────────────┘
                                             │  reach_table.csv (10,368 rows)
                                             │  + 13 analysis papers
                                             ▼
                          ┌───────────────────────────────────────────┐
                          │  services/api   (FastAPI)                 │
                          │    GET /api/v1/forecast/table      ✅     │
                          │    POST /api/v1/analyze            ✅     │
                          │    /health, /health/db             ✅     │
                          │    keys/validate                   FAKE   │
                          └──────────────────┬────────────────────────┘
                                             │ HTTP
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
        ┌───────────────────┐   ┌────────────────────┐   ┌──────────────────┐
        │ apps/desktop      │   │ apps/extension     │   │ apps/site        │
        │ Tauri + React     │   │ Chrome / Firefox   │   │ Next.js          │
        │                   │   │                    │   │                  │
        │ overlay    ✅     │   │ capture    ✅      │   │ 10 routes  ✅    │
        │ 9 views    ✅     │   │ analyze    ✅      │   │ checkout   ❌    │
        │ forecast   ✅     │   │                    │   │ key issue  ❌    │
        │ engine     MOCK   │   │                    │   │ admin      ❌    │
        │ keychain   ✅     │   └────────────────────┘   └──────────────────┘
        │ feed       ❌     │
        └───────────────────┘
                    ▲
                    │  ✗ NOT CONNECTED — no vendor account, no engine/real.ts
        ┌───────────┴───────────┐
        │  LIVE TICK FEED       │   Ironbeam unfunded · Databento live unpriced
        │  (does not exist)     │   MT5 desktop not installed
        └───────────────────────┘

  services/market-worker : empty        packages/contracts : empty
  infra : Postgres 17 via docker-compose
```

**Read the diagram this way: the research half is nearly complete and has produced no edge; the
product half is a well-built shell with a fake at its centre.** The one wire that has never been
connected is the live feed, and it is the second of the plan's two named fatal-risk items.

---

## 9. Architecture at the end of the project

```
        TRADER'S MACHINE                                  OUR INFRASTRUCTURE
 ┌──────────────────────────────────┐              ┌──────────────────────────────┐
 │  Vendor feed (their entitlement) │              │  apps/site  (Cloudflare)     │
 │        │                         │              │   landing · pricing          │
 │        ▼                         │              │   signup · checkout          │
 │  services/engine  (Rust)         │              │   key · support · admin      │
 │   ring buffer, fixed memory      │              └──────────┬───────────────────┘
 │   delta · CVD · absorption       │                         │ Stripe webhook
 │   FeedStatus.gapCount            │                         ▼  (arrives twice —
 │        │  S2 IPC                 │              ┌──────────────────────────────┐
 │        ▼                         │              │  services/api   (Railway/Fly)│
 │  apps/desktop  (Tauri)           │◄─── S3 ─────►│   keys/validate     REAL     │
 │   overlay · 9 views              │   key check  │   keys/mine                  │
 │   engine/real.ts   REAL          │              │   dev/issue-key              │
 │   forecast (live cell)           │◄─── S7 ─────►│   forecast/table             │
 │   rules · journal                │   reach tbl  │   analyze                    │
 │   creds → OS keychain            │              │   journal sync      S4       │
 │        │  S4 sync, never blocks  │◄─────────────┤   Postgres + Alembic         │
 │        ▼                         │              └──────────┬───────────────────┘
 │  local-first store               │                         │
 └──────────────────────────────────┘                         │ nightly
              ▲                                               ▼
              │                                  ┌──────────────────────────────┐
              │  S6 capture context              │  services/market-worker      │
 ┌────────────┴─────────────┐                    │   rebuild reach_table        │
 │  apps/extension          │                    │   calibration.settle         │
 │  Chrome / Firefox        │                    │   (append-only, cannot       │
 └──────────────────────────┘                    │    invent history)           │
                                                 └──────────┬───────────────────┘
                                                            │ reads
                                                 ┌──────────▼───────────────────┐
                                                 │  services/signal-data        │
                                                 │   GC 19mo + XAUUSD to 1997   │
                                                 │   reach · replay · expansion │
                                                 │   E1–E5 settled              │
                                                 └──────────────────────────────┘

        THE CALIBRATION LOOP — the part that decides whether any of this is true
        live outcomes ──► calibration.py ──► does 61% happen 61% of the time?
                                   │
                                   └──► if not, the number shown to the trader is wrong
                                        and the product says so rather than hiding it
```

### 9.1 What has to become true, by week

| Week | Milestone | Today |
| :--- | :--- | :--- |
| 2–4 | App is real locally — correct live delta over a real chart | overlay ✅, delta ❌ |
| 5 | **Backend** — real `keys/validate`, `dev/issue-key`, Postgres, deployment | fakes only |
| 6 | **Website, three days then stop** — signup → approval → key in hand → activated | built on `feat/vision-hub`, driven end to end 18 Sep, unmerged |
| 7 | **Private beta, three outside traders** | nobody outside has run it |
| 8 | **Fix the five things** they report — and *"would you pay $39"*, two of three saying yes unprompted | — |
| 9 | **Open the doors** | — |
| 10–11 | Founder-led distribution | — |
| 12 | **Count what's true** — ten paying subscribers | — |

### 9.2 The three gates that can end the project

- **W1 — the edge test.** If the forward-return distribution is flat against the pre-written
  threshold, this is not a product. *(The gate document exists with its votes blank; the meeting has
  never been held.)*
- **W3 — live delta matching a reference.** *"If our CVD doesn't agree with a real footprint chart,
  we do not have a product, we have a plausible-looking number."* Partly closed by the quote-rule
  method (99.65%); the external-platform check is blocked by ATAS/Sierra being Windows-only.
- **W8 — would you pay $39.** Two of three unprompted. The difference between a product and a hobby.

---

## 10. What remains, by owner

### Prathamesh

| | Blocked on |
| :--- | :--- |
| MT5 desktop install + XAUUSD tick-depth check (`Ctrl+U`) | nothing — **2 minutes, and it opens or kills route 2** |
| Gate-line-#3 screenshot | nothing |
| `vitest` — three deferrals, untested TS shipped | nothing |
| `reach_table.json` generator | nothing — inverts the `api → apps/desktop/public/` dependency |
| `FlowView` loading state | nothing — `ForecastView` has the pattern; flow's fixture is 13× larger |
| Stale records: `current.md` 887–931 / 2072, `reach-table-explained.md` §8 | nothing |
| `quote_rate_z` | spot data |
| **Row #9 — Ironbeam credentials** | a funding decision; **gate line #2, a named fatal-risk item** |

### Varad

| | Blocked on |
| :--- | :--- |
| **Row #0 — revoke the Anthropic key** | nothing. Ten minutes. Deferred at every gate since Week 0 |
| E1, E2, E3-empirical, E4 predictions (§14–§17) | must be written **before** the code reads them |
| AWS credentials for requester-pays S3 | a spend call against the $280–300 ceiling; exposure ~$0.06 |
| `scipy` into the lockfile | a lockfile change earns its own reviewed commit |
| `first_touch` — recommendation is **no change** | recording the decision |
| `services/engine` in Rust, `engine/real.ts` | the feed |

### Shreyas

| | State |
| :--- | :--- |
| Three distribution-licence emails | **no artefact** — *"the one line neither engineer can move"* |
| `docs/qa/reference-session.md` | **the file does not exist**; unblocks *"every 'is the delta right' argument, forever"* |
| Panel redesign for a 380px floating window | due before implementation |

### All three

- **The Week 1 gate meeting.** Document written, votes blank. Recommendation: the gate does **not**
  slide — *"if a gate is not met, next week is the same gate."*
- **The S1 `'N'` amendment.** Fully drafted, sixteen days past its own deadline.
- **M4 decided** — needs route-2 spot.
- **C1, the feed vendor** — reopened 5 Sep and still open.

---

## 11. The discipline, because it explains the code

These are not style preferences. They are why files look the way they do.

1. **Portable or it does not belong in `features/portable.py`.** Both instruments, or neither.
2. **Basis points, never ticks**, everywhere except stage 9's labelled display conversion. A
   mis-scaled display renders visibly wrong; a **mis-scaled bucket silently pools two populations**
   and reports the average as a base rate.
3. **`has_flow: False` raises.** It does not degrade, fall back, or substitute a proxy — a degraded
   number looks exactly like a real one.
4. **Below `MIN_SAMPLES` the answer is `null`, and never a coarser bucket.** `forecast: null` is a
   valid and common answer.
5. **Every probability carries its band.**
6. **A prediction is committed before the run that reads it**, in its own commit, timestamped ahead.
7. **A miss is scored, not rounded.** `REACH.md` §5 and `M4_PATH.md` §2 both record their own
   predictions failing.
8. **How a signature was obtained is written down**, including when it was verbal and relayed —
   *"a signature nobody can point at later is worse than an unsigned contract."*
9. **A rule gets a test, not a promise.** The lesson is `reach_table.json`: 41,280 numbers correct
   on the day, with nothing reconciling them, until a test did.
10. **One definition per quantity.** Two copies is how two files quietly disagree.
11. **Parked means parked** — nothing deleted, and no Track B work modifies a Track A module.

---

## 12. The one-paragraph status

**The research track is nearly finished and has found no edge in GC**, which is a real and carefully
established result rather than a failure to measure. Its last prerequisite is spot data, now
reachable via S3 back to 1997, with a new magnitude-expansion programme gated on four unwritten
predictions. **The product is a well-built, well-tested shell around a fake**: the overlay, the nine
views, the keychain, the forecast table and the API are real; the engine, the feed, key validation
and payments are not. **The single most consequential gap is the live tick feed** — no vendor account
exists, it has blocked gate line #2 for over a week, and it is the one wire between a convincing demo
and a product.
