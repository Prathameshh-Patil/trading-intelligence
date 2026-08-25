# Varad — your twelve weeks

**Engineer 2 · Signal + backend · everything that turns ticks into a number, and everything on a server.**

You own: feed adapters · the delta/CVD/footprint engine · the outlier rules from `strategy.md` ·
the backtest harness · **the honest measurement of whether any of it predicts anything** · FastAPI,
Postgres, auth, keys, metering, webhooks.

**Directories:** `services/engine/` (new, Rust), `services/signal-data/`, `services/api/` — minus
`journal.py` from Week 6 and `entitlements.py` from Week 9, which transfer to Prathamesh.

**Read before you write any code:** [`../contracts.md`](../contracts.md).

**Your failure mode:** falling in love with a signal and never running the null test. The mechanical
guard is [`thresholds.md`](thresholds.md) — **you commit the threshold on Thursday morning of Week 1,
before you look at any results.** A threshold chosen after seeing the distribution is not a
threshold, it's a story.

---

## Week 0 · Aug 26–28 — clear the debt

| Day | Work |
| :--- | :--- |
| **Wed 26** | ⚠️ **First: revoke the Anthropic key.** `DELTA_CVD_FINDINGS.md` §5 — a real key sat in the tracked `.env.example` (uncommitted, absent from branch history, one `git add -A` from being pushed) **and was pasted into a chat transcript.** Repo is clean; the key should not still be live. **A revoke, not a rotate** — as of 25 Aug nothing depends on it, and the suite stays green on a placeholder because the tests only need `anthropic_api_key` to be *present*, not valid. Ten minutes. Then: ~~settle the analysis-backend decision~~ — **settled 25 Aug: we build our own model.** No hosted backend, no credit, the `$5 Anthropic` recommendation is withdrawn. Claude stays in as the interim and the four-key contract stays frozen, so your model drops in behind the same `analyze()` later. ~~Use the freed time to scope it~~ — **scoped 25 Aug, and it needs no week here.** It was never a replacement for `analyze()`: it is a **GC strategy selector**, and a *personal research tool*, not a product feature — so it takes nothing from this schedule. Design: `docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md`. **Use the freed time for the feed-vendor question instead** (`current.md` C1, Databento → quantfeed) — it is time-critical because Shreyas's three licence emails go out Monday and the vendor list may be wrong. Then `pull_futures_trades.py --estimate-only`, one month GC — **GC only, NQ was dropped 25 Aug**; skip if quantfeed replaces it. *(closes #1 outright, and #4's secrets half)* |
| **Thu 27** | ~~Run the Databento pull~~ — **done 24 Aug by Prathamesh (`8aece67`), and done well.** 1,616,772 GC trades, July 2026, $2.52. Aggressor convention confirmed three independent ways. **Read [`DELTA_CVD_FINDINGS.md`](../../../services/signal-data/analysis/DELTA_CVD_FINDINGS.md) end to end before you touch anything** — it will save you a day. Then: **(1)** cut `data/fixtures/gc_ticks_1session.parquet` from `data/gc_trades.parquet` — the 2026-07-16 GCQ6 session, 77,532 trades; `data/` is gitignored so it needs an explicit exception. **That's S1.** ⚠️ **Blocked — checked 25 Aug: `services/signal-data/data/` does not exist on your machine.** `8aece67` gitignored `data/` and `*.parquet`, so the pull lives only on Prathamesh's disk and there is nothing here to cut from. **Ask him for the parquet at Wednesday's standup**, not Thursday morning. Fallback is re-pulling (~$2.52 + a Databento key) to recreate a file that already exists on a teammate's laptop. **(2)** Own the reference-validation blocker with Shreyas — see [`../week-00.md`](../week-00.md). **(3)** ~~Decide NQ~~ — **dropped 25 Aug. GC is the launch instrument**, the ~$11.42 stays unspent, and Week 1 Friday no longer has an instrument decision in it. |
| **Fri 28** | ~~**Freeze S3.** Write `services/api/tests/fixtures/keys_fake.py`~~ — **done 25 Aug, ahead of schedule.** All six branches driven live on port 8001; `ruff`/`mypy` clean; the 17-test suite unaffected. `contracts.md` S3 updated and frozen. **Left for Friday:** freeze S1's *column contract* in `contracts.md` — that is separable from the blocked S1 fixture and should land regardless. |

**Float:** ~~Thursday — run the first live Claude analysis~~ **gone, 25 Aug.** No credit is being
bought, so the 5 `LIVE_API_TESTS=1` tests stay skipped and PR #3's one unverified claim stays
unverified until your own model lands. Float goes to **scoping that model** instead.

---

## Week 1 · Aug 31 – Sep 4 — kill week

Every line of code this week is throwaway. Notebooks, not crates. Week 2 rewrites it once, properly,
and goes faster if there's nothing tempting to salvage.

| Day | Work |
| :--- | :--- |
| **Mon 31** | ~~The research spike~~ — **`compute_delta_cvd.py` already does this** (439 lines, on `main`): per-trade delta, session-reset CVD, 1-minute bars, price-level footprint. Read it, run it, and spend the day on **what it doesn't do — the outlier rules from `strategy.md`**, which was Wednesday's task and is now Monday's. You are a day ahead; don't spend it re-deriving CVD. **Then freeze S2 with Prathamesh** — 30 minutes, one file, `apps/desktop/src/lib/engine/types.ts`. The most valuable half hour of the week. |
| **Tue 01** | **Validate delta against a real footprint chart — the open hard gate.** Your own findings doc calls this correctly: three internal checks make a sign inversion unlikely but **structurally cannot** catch a wrong contract, a timezone offset, a differing session boundary, or a systematic magnitude error. ATAS and Sierra are Windows-only and the machine is an ARM Mac, so Shreyas picks the path by Week 0 Friday — TradingView web today, a real footprint platform before the Week 3 gate. **If it doesn't match, check in this order: timezone, then contract (GCQ6→GCZ6 rolls 29 Jul), then the mapping** — the mapping is now the *least* likely, which inverts the usual advice. Then show Shreyas and let him grade it independently. |
| **Wed 02** | *(Pulled forward to Monday — use this day for the second half.)* Outlier detection from `strategy.md`, **GC only** — with NQ dropped, the ≥60 NQ and ≥200 ES figures in that document are the **derivation source you scale from**, not thresholds you implement. **Write down *how* you scaled to GC**, because that number gets argued about in Week 4 and "it looked right" will not survive it. Output for one session: timestamped outlier prints with price levels and cluster boundaries. Still a notebook. |
| **Thu 03** | ⚠️ **Morning, before anything else: [commit the threshold](thresholds.md).** Then the edge test. Apply the location-and-reaction rule to your outliers — absorption into structure lows, trapped buyers into highs — and measure forward returns over 5, 15 and 30 minutes across the full month. **Produce a distribution, not an anecdote:** histogram, median, spread, **and the null** — what does a random entry at a random time in the same month return? If your signal doesn't beat the null, you don't have one. |
| **Fri 04** | Present the distribution against **Thursday morning's committed threshold** — not the best-looking cut of it, the one you committed to. Shreyas asks the uncomfortable questions; that's his job. Then: feed vendor, and the decision record naming **what would change your mind**. *(No instrument decision — GC was settled when NQ was dropped on 25 Aug.)* |

**If the edge test comes back flat:** Week 2 is testing a **second formulation from `strategy.md`**,
not building. Say it out loud on Friday, because on Monday it will feel like giving up and it isn't.

---

## Week 2 · Sep 7–11 — engine becomes real code

| Day | Work |
| :--- | :--- |
| **Mon 07** | Scaffold `services/engine/` as a real Rust crate. Port the delta and CVD arithmetic out of the notebook. **First test on day one:** `cargo test` asserting our CVD against `docs/qa/reference-session.md` at every 15-minute mark, reading `gc_ticks_1session.parquet`. **That test is the project's spine** — the only thing between you and a plausible wrong number. Make it red before you make it green, so you know it can fail. |
| **Tue 08** | Ring buffer for the live tick stream, **fixed memory**. This decides whether the app is still healthy at hour six. Size it from the **measured** tick rate of the busiest hour in your month of data — a number you can point at, not a guess. Document what happens on overflow: drop oldest, and surface it in `FeedStatus.gapCount` so it's **visible rather than silent**. |
| **Wed 10** | CVD and footprint aggregation at **configurable bar sizes**. Configurable is the requirement: Shreyas wants 1-minute for Week 3 grading, beta traders want 5-minute, and hardcoding it now means an engine change in Week 8. **Test each bar size against the reference session independently** — an aggregation bug that only appears at 15m is exactly the kind that hides. |
| **Thu 11** | **90 minutes with Prathamesh** defining the Rust↔JS command layer. Then implement those `invoke` handlers over the real engine, **reading the fixture parquet rather than a live feed.** By end of day `VITE_ENGINE=real` renders the fixture session in the real window through the real Rust engine. This is the S2 integration done a week early against a file instead of a network — which is why it takes an afternoon instead of three days. |
| **Fri 11** | Harden: `cargo clippy` clean · fixture test green at every bar size · a **property test** on the arithmetic — delta always equals `askVol − bidVol`, CVD always equals the running sum, for any input including empty bars and single-tick bars. |

**Float:** Wednesday, if aggregation lands early — define the Rust↔JS command layer with hardcoded
returns. Makes Thursday trivial.

---

## Week 3 · Sep 14–18 — live numbers on screen

The milestone that matters most in the quarter.

| Day | Work |
| :--- | :--- |
| **Mon 14** | Feed adapter for the vendor chosen 4 Sep. Connect, authenticate, subscribe, decode. Ticks flowing into the ring buffer. **Today is the happy path, end to end** — reconnect is tomorrow. |
| **Tue 15** | **Reconnect and gap detection.** Connections drop mid-session: a WiFi blip, a vendor restart, a laptop sleeping. Detect the gap, reconnect, backfill if the vendor allows — and **mark the CVD discontinuous if you couldn't backfill.** A CVD with a silent hole in it is a wrong number that looks right, which is the exact failure mode this whole project exists to avoid. |
| **Wed 16** | 🔴 **INTEGRATION DAY.** All day with Prathamesh. Live delta streaming at sub-second latency, then your outlier detector against the live stream. **Measure the latency, don't assert it:** tick received → number on screen, in milliseconds, **at p99 during the busiest hour**, not the median during lunch. |
| **Thu 17** | **Tune against Shreyas's disagreement log — read it before you touch a threshold.** If he called five flagged prints wrong, the question is not "how do I filter those five", it's "what did those five have in common", and sometimes the honest answer is "nothing, the rule is wrong." **Re-run the backtest after every change** — a threshold that improves live grading and destroys the backtest is overfitting to one session. |
| **Fri 18** | Third grading session's tuning. Write down where the thresholds landed for the launch instrument **and why** — Week 4's harness re-derives them and you need something to compare against. |

**Float:** Tuesday, if reconnect lands early — start the outlier detector on the live stream.
Wednesday is the heaviest day of the quarter.

---

## Week 4 · Sep 21–25 — rules, journal, dogfood

| Day | Work |
| :--- | :--- |
| **Mon 21** | **Backtest harness, day one.** The requirement is a rule change replayed over a month **in minutes**, and "minutes" is hard, not aspirational: if it takes an hour you'll run it once a week instead of ten times a day, and threshold tuning stops being empirical. Parallelise over days, cache the parsed parquet, **measure the wall clock.** |
| **Tue 22** | Harness day two: wire the outlier rules in and **reproduce Week 3's live results from the recorded ticks.** If the backtest and the live run disagree on the same session, **one of them is lying and you need to know which before you tune anything.** This reconciliation is the harness's real acceptance test. |
| **Wed 23** | Tune thresholds per instrument against Shreyas's full log — three Week 3 sessions plus two dogfood. Every candidate through the harness. Final numbers and reasoning into `docs/decisions/`. |
| **Thu 24** | Harness performance and correctness: full month in minutes, Week 3 reproduced exactly, **and commit the reproduction as a regression test.** From here on, a threshold change that breaks it is a bug, not a tuning decision. |
| **Fri 25** | Month-one internal accuracy note: what the signal did across four weeks of live grading and one month of backtest. **Honest version, including the sessions where it was wrong.** |

---

## Week 5 · Sep 28 – Oct 2 — backend

Small on purpose. **Keys, auth, metering. Nothing else.** Every feature added here is one you
maintain for twelve weeks and that ten subscribers will not notice.

⛔ **What this backend is not:** no market data ever passes through it. That's the entire licensing
argument. If anyone proposes a route that accepts a tick, the answer is no — $1,750/mo plus a
five-figure CME derived-data licence.

| Day | Work |
| :--- | :--- |
| **Mon 28** | Postgres schema and Alembic migrations: users, keys, entitlements, usage. Then Clerk auth into FastAPI. You already own `services/api`, migrations are at head, and the analyze route's `503` shape is the house style — match it. |
| **Tue 29** | API key issue and revoke, plus usage metering. Then the dev-only `POST /api/v1/dev/issue-key` (**S5's fixture**), gated on a config flag, **with a test asserting the flag is `false` in production config.** That route is what lets Prathamesh build the entire Week 6 purchase flow with no payment processor in existence. |
| **Wed 30** | Rate limiting on Upstash. Then harden: Clerk down, Postgres down, a key validated 10,000×/min. Each is a `503` in the house shape, not a traceback. The analyze route already does this correctly — copy it. |
| **Thu 01** | Metering finished. The end-to-end unlock as an **automated test**: issue a key via API → validate → confirm tier. Then start the payment webhook handler — Week 6 is short and the webhook has the sharp edges. |
| **Fri 02** | Deploy to Railway or Fly. **A backend that only runs locally has not been tested.** Confirm the Postgres connection from the deployed environment and the `503` when it drops — `/api/v1/health/db` already proves this locally, so prove it in production. |

---

## Week 6 · Oct 5–9 — webhooks, and your first review of Prathamesh's code

| Day | Work |
| :--- | :--- |
| **Mon 05** | Payment webhook handler with **idempotency on `event_id`.** Webhooks arrive twice. They arrive out of order. They arrive months late. **The handler is idempotent or it issues two keys and bills once** — and you find out from a confused subscriber, not from a log. |
| **Tue 06** | Key issuance behind the webhook, plus replay handling. Then a test that **fires the same webhook five times and asserts one key exists.** |
| **Wed 07** | **Threshold tuning becomes your background task from here to Week 12** — an hour a day, not a sprint. Signal quality is the product; it doesn't get a week, it gets a habit. |
| **Thu 08** | 🔵 **Review Prathamesh's journal route. Review, not rewrite.** Comment on the migration, the idempotency, the index on `(user_id, updated_at)` — **and let him fix them.** If you rewrite it, he doesn't become a backend engineer and you own two more route modules for the rest of the year. Then: end-to-end payment test against the processor sandbox. |
| **Fri 09** | Gate: someone buys it with a real card, then processes a real refund. Confirm the key is revoked and the app degrades to **lapsed**, not offline. |

---

## Week 7 · Oct 12–16 — private beta

You are **not** on the trader calls. Shreyas leads, Prathamesh watches muted, you stand by and fix.

| Day | Work |
| :--- | :--- |
| **Mon 12** | **Telemetry:** which signals fire, which get acted on, which get dismissed. **Privacy line, not negotiable: no market data, no tick data, no screenshots leave the machine.** Signal IDs, timestamps, outcomes. Nothing that could reconstruct a feed. Say so on the pricing page. |
| **Tue 13** | Signal tuning. Standing by for anything that breaks on trader 1's machine. |
| **Wed 14** | **Fix whatever broke on trader 1.** It will be something you didn't anticipate: a different vendor account tier, a different Windows locale, a symbol format you've never seen, a timezone that isn't yours. **A machine that isn't yours is different in ways you cannot enumerate in advance** — which is the entire reason this week exists. |
| **Thu 15** | Same, for trader 2. |
| **Fri 16** | Read Shreyas's ranked confusion log with Prathamesh. **Today's rule: clarifying questions yes, explaining why the user was wrong no.** |

---

## Week 8 · Oct 19–23 — fix the five things

| Day | Work |
| :--- | :--- |
| **Mon 19** | Signal quality fixes **from real usage, not from your own backtest.** That distinction is the whole point of Week 7: your backtest says what the rule does on data you chose; the telemetry says what it does on trades a stranger took. **When they disagree, the stranger is right.** |
| **Tue 20** | **Performance: the overlay must not stutter a live chart.** Profile the compositing path against Prathamesh's Week 2 frame-timing baseline. |
| **Wed 21** | Signal fixes continued. Re-run the harness after every change — the Week 4 reproduction test is your regression net. |
| **Thu 22** | Week 9 prep: the journal add-on's **entitlement check on the backend.** You provide the tier in key-validate; Prathamesh takes the in-app gating. **No contract change needed** — that's what freezing S3 in Week 1 bought. |
| **Fri 23** | Decision gate: count the unprompted $39 yeses. |

---

## Week 9 · Oct 26–30 — open the doors

| Day | Work |
| :--- | :--- |
| **Mon 26** | Journal add-on gated behind its own entitlement, server side. `tier` has carried `core \| core_journal` since Week 1 — you're populating a value, not changing a contract. |
| **Tue 27** | **Second instrument, only if Week 8 was clean:** feed adapter, thresholds **re-derived through the harness**, fixture session cut and committed. **Do not ship it on Week 1's thresholds scaled by eyeball** — re-derive, or don't ship it. |
| **Wed 28** | Signal quality review against live telemetry — the first with real subscriber data. **Set up the weekly cadence now**, because from next week this is the shape of your job. |
| **Thu 29** | **Harden the feed adapter.** Reconnects will be your **top support ticket** — a trader's WiFi blips, their vendor restarts, their laptop sleeps, and every one looks to them like your software broke. Make reconnect silent, gaps visible, and neither require a restart. |
| **Fri 30** | Gate: subscriber #1 exists. |

---

## Weeks 10–11 · Nov 2–13 — distribution

| Day | Work |
| :--- | :--- |
| **Mon** | Weekly signal-quality review against live telemetry. **Write the one-paragraph verdict.** |
| **Tue** | Feed adapter hardening — whatever last week's reconnect tickets pointed at. |
| **Wed** | Threshold tuning through the harness. **The regression test must stay green.** |
| **Thu** | Support escalations that need engine knowledge. |
| **Fri** | Write the week's accuracy note. |

---

## Week 12 · Nov 16–20 — count what's true

| Day | Work |
| :--- | :--- |
| **Mon 16** | Begin the **internal accuracy report**: how the signal actually did live across Weeks 9–11, on real subscriber sessions, **compared against the Week 1 pre-written threshold.** This report is for the three of you, not for marketing — which is exactly what makes it worth writing honestly. |
| **Tue 17** | Continue. **Include the sessions where it was wrong, in detail.** A report without failures has not been written honestly, and everyone reading it knows that. |
| **Wed 18** | **Unit economics, on one line:** revenue in, run rate out, gross margin. Include payment fees (~5% + $0.50/transaction — real money at $39) and the Apple Developer amortisation. Budget said $84–126/mo; find out what it actually was and **where the estimate was wrong.** |
| **Thu 19** | Quarter-two decision, all three, from evidence. |
| **Fri 20** | Final gate and the write-up. |

---

## Your gates

| Wk | You must have |
| :--- | :--- |
| 0 | ~~Real Databento row counts and aggressor split~~ **already met by `8aece67`** · `gc_ticks_1session.parquet` committed · `keys_fake.py` committed · **Anthropic key revoked** · ~~a reference-chart path chosen~~ **closed 24 Aug by `c504e50`** · **the quantfeed decision made** (`current.md` C1) |
| 1 | ⚠️ A forward-return distribution clearing a **pre-written, committed** threshold · delta validated against a reference footprint chart, signed off by someone other than you |
| 2 | `cargo test` green against the reference session **at every bar size** · a property test on the arithmetic |
| 3 | Live delta matching a reference chart for a full session · **p99 latency measured**, not asserted · reconnect survives a real network drop |
| 4 | Harness replays a month in minutes · **backtest reproduces a live session exactly, committed as a test** |
| 5 | A key issued by the backend unlocks the app end to end · backend **deployed**, `503` shapes verified in production |
| 6 | The same webhook fired five times produces exactly one key · Prathamesh's route **reviewed, not rewritten** |
| 7 | Telemetry live, confirmed to carry **no market data** |
| 8 | Signal fixes from telemetry, not backtest · overlay doesn't stutter, measured |
| 9 | Entitlements live · feed adapter hardened |
| 12 | Accuracy report published **with failures in it** · unit economics on one line |

## The two things you own that can end the project

**The edge test (Week 1).** If the distribution is flat, the honest move is Week 2 on a second
formulation, not building. See [`thresholds.md`](thresholds.md) for why you commit the number first.

**The aggressor-side mapping (Week 0–1).** If it's inverted, every delta sign in the product is
wrong **and every chart still looks completely plausible.** Nothing downstream catches it. That's
why the reference session gets signed off by Shreyas and not by you.

**Status: three independent confirmations already exist** and they are good ones — a 48.32/47.79
split, 83% tick-rule agreement, and a +0.50 delta↔return correlation that would read −0.50 if
flipped. The 2026-07-16 session even threw up a scare worth knowing about: price fell 89 points
while CVD closed **+1,842**, which is exactly what a flipped sign looks like. It was chased and
ruled out — it is genuine absorption, buyers aggressing into heavy resting supply. **That instinct
to chase it rather than accept it is the thing to keep.** The gate is still open only because
internal consistency is not external validation.
