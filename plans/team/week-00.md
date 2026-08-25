# Week 0 · Wed 26 – Fri 28 Aug — clear the debt

Week 1 Day 1 assumes a clean start. It is not clean yet. `plans/current.md` carries eight open
items and four unchecked boxes, and **three of the four are the same shape: code that type-checks
and tests green but has never once been run for real.** Week 1 has no room for that — Day 1 assumes
a month of tick data is already on disk and a Tauri window already renders.

Three working days. Weekend is buffer, not schedule. If Friday is clean, don't work Saturday.

> **Revised 25 Aug after reading `8aece67`.** Prathamesh ran the Databento pull for real on 24 Aug
> and shipped `services/signal-data/compute_delta_cvd.py` plus
> [`analysis/DELTA_CVD_FINDINGS.md`](../../services/signal-data/analysis/DELTA_CVD_FINDINGS.md).
> **1,616,772 GC outright trades for July 2026, $2.52 spent, and the aggressor convention confirmed
> three independent ways** — docs, a 48.32/47.79 split, an 83% tick-rule agreement, and a +0.50
> delta↔return correlation that would read −0.50 if the sign were flipped. Items #6 and most of A1
> are **done**, well beyond the bar this file set for them.
>
> Two things changed as a result, both below: **reference-chart validation is blocked on tooling**
> and is the open hard gate, and **an API key needs rotating.**
>
> **NQ is dropped** (25 Aug). It was never pulled, ~$11.42 unspent, and it stays unspent. **GC is
> the launch instrument** — decided now rather than deferred to Week 1 Friday, because only GC has
> data and pretending otherwise would make Friday's "decision" theatre.

---

#### W0D1 · Wed Aug 26

**P** — Load the rebuilt extension in a real Chrome profile (`955b374` has never been checked in
one). Confirm "Capture screen" reads a real selection through the `activeTab` + `chrome.scripting`
path. Then the same in Firefox — it installs and CORS accepts it, but no Firefox profile has ever
rendered a verdict. *(closes `current.md` #2, #8)*

**V** — ~~Settle the analysis-backend decision~~ — **settled 25 Aug: we build our own model.** No
hosted backend is bought; the earlier "add $5 Anthropic credit" recommendation is **withdrawn**, and
nothing goes on any account. Claude stays in `analyze()` as the interim implementation and the
four-key contract stays frozen, so the own model drops in behind the same signature later — the same
seam that survived lexicon → Claude on Day 3 with zero extension edits. Wednesday's remaining job is
just `pull_futures_trades.py --estimate-only` for one month of GC.

> **The two consequences worth saying out loud.** First, **the analyze feature has no working
> backend now** — no live call has ever succeeded and none will before the model exists, so the
> popup's core action stays unverified end to end for as long as that takes. Second, **the own model
> has no home in this schedule.** Weeks 1–12 budget for the Rust engine, the overlay, the API and
> the harness; not one of them budgets for training or serving a model. Scope it and give it a week
> before it silently eats one. *(closes #1's decision half, and #4's secrets half — the API no
> longer needs to hold a third-party key at all, which makes the hosting question easier, not
> harder)*

**V — first, before anything else: revoke the Anthropic key.** `DELTA_CVD_FINDINGS.md` §5 reports a
real key was sitting in the git-tracked `.env.example` — uncommitted, confirmed absent from all
branch history, one `git add -A` from being pushed — **and that it was also pasted into a chat
transcript.** The placeholder is restored, so the repo is clean, but a key that has been in a
transcript is a key that should not still be live. Ten minutes at console.anthropic.com.

**Still do this — the own-model decision makes it easier, not unnecessary.** Nothing depends on that
key any more, so it is a **revoke**, not a rotate: delete it and leave the placeholder in `.env`.
`anthropic_api_key` is a required setting, but the tests only need it to be *present*, not valid, so
the suite stays green on a placeholder. A live key with no purpose is strictly worse than no key.

**S** — Two hours reading, one hour writing. Learn what a footprint chart actually shows: bid
volume and ask volume side by side at each price, delta as their difference, CVD as the running
total. Watch two order-flow teardown videos. Then write `docs/qa/glossary.md` **in your own words**
— absorption, trapped buyers, delta divergence, cluster. If you can't explain absorption without
copying a definition, you can't grade the overlay in Week 3, and grading it is your most important
job in this project. Separately: open ATAS demo and Sierra Chart trial accounts today, both take
time to approve.

*Float:* if P finishes both browsers before 16:00, take the popup UI review (`current.md` #3) —
it was written from scratch to unbreak a build and nobody has looked at it as design.

*Why nobody is blocked:* three unrelated systems. P is in the browser, V is in Python and a billing
page, S is reading.

---

#### W0D2 · Thu Aug 27

**P** — `pnpm tauri dev`, on-device, and **look at a real window**. A headless-Chromium screenshot
of the compiled bundle is not a native window and everyone knows it. Confirm all six views render,
confirm the window size is right, confirm zero console errors in the real webview. Screenshot it
and put the screenshot in `daily_updates/2026-08-27.md`. *(closes #7)*

**V** — ~~Run the Databento pull~~ — **done 24 Aug, and done well.** Read
`DELTA_CVD_FINDINGS.md` end to end before you touch anything; it is the best-documented thing in
the repo and it will save you a day. Then three real jobs:

1. ~~**Cut `data/fixtures/gc_ticks_1session.parquet`**~~ — ✅ **DONE 25 Aug, before Week 0 started.**
   Blocked in the morning and closed the same evening: the `.gitignore` exception landed in
   `fdb96c8`, and Prathamesh cut the session with `cut_s1_fixture.py` and pushed the **fixture**
   rather than the month (`14f5547`), straight onto the one path that exception re-includes.
   **Verified after pulling, against the contract rather than the filename:** 77,532 rows exactly,
   all six S1 columns with correct dtypes and no extras, `GCQ6` only, the CME session window, and
   **session delta +1,842 — matching `DELTA_CVD_FINDINGS.md` §3 to the unit.**
   > 📋 **Thursday's job is no longer the cut — it is the two things the cut surfaced.**
   > **(a)** `aggressor_side` carries a real third value, **`'N'` — 1,811 trades, 2.34%** — that S1
   > declares as `'B' | 'A'`. S1's own row count already includes them, so the count and the type
   > cannot both be true. **This is a frozen contract: the amendment is drafted in `contracts.md`
   > and NOT applied. It needs all three of you.** Take it to Wednesday's standup as a yes/no.
   > **(b)** The fixture holds **421 genuine duplicate rows** — identical timestamps, up to 6
   > copies, the signature of one aggressor sweeping several resting orders. They are not errors.
   > A `drop_duplicates()` that looks like hygiene moves session delta from **+1,842 to +1,989, an
   > 8% drift.** Both are recorded in `contracts.md` S1.
2. ~~**Solve the reference-validation blocker**~~ — **closed 24 Aug by `c504e50`**, by quote-rule
   cross-check rather than by finding a Mac footprint platform. See the box below. **Your job here
   is now the residual, not the gate:** session-total delta is method-dependent at ~15–20%, and the
   thresholds you commit on Thursday of Week 1 inherit that error bar. Decide how you carry it
   before you derive a number that pretends it isn't there.
3. ~~Decide NQ~~ — **dropped.** GC is the launch instrument. One instrument, one set of thresholds,
   one reference session to validate. Everything downstream gets simpler and the ~$11.42 stays
   unspent.

**S** — ~~Own the reference-chart problem~~ — **discharged; `c504e50` closed it on 24 Aug without a
charting platform.** Do not open ATAS or Sierra trials for this reason (a demo account is still
worth having for Week 3 grading, which is a different job). **Straight to the vendor licensing
email** — you have the whole day for it now. One precise question, One precise question, identically worded to Databento,
Rithmic and Tradovate: *"Our software runs on the end user's machine and connects using the user's
own data entitlement. Market data does not pass through our servers. Do we need a distribution
licence?"* Do not soften it, do not add context, do not ask three questions. Get all three drafts
reviewed at standup Friday and send Monday morning. Also: book the CA call for Week 1 Tuesday —
book it now, CAs are not available on two days' notice.

*Float:* ~~run the first live Claude analysis~~ — **gone, 25 Aug.** No hosted backend is being
bought, so the 5 `LIVE_API_TESTS=1` tests stay skipped and PR #3's one unverified claim stays
unverified. ~~Use the slack to scope the own model instead~~ — **scoped 25 Aug, and it needs no week
here.** The "own model" was never a replacement for `analyze()`: it is a **GC strategy selector**,
and it is a personal research tool rather than a product feature, so it takes nothing from this
schedule. Design in `docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md`.
**Use the float for the feed-vendor question instead** (`current.md` C1) — it is time-critical in a
way this was not, because Shreyas's licence emails go out Monday.

*Why nobody is blocked:* P is in Tauri, V is in Databento, S is in a text editor and a calendar.

---

#### W0D3 · Fri Aug 28

**P** — Merge PR #3 if review is clean. Then branch `feat/tauri-overlay` off `main` and confirm the
workspace builds from a fresh clone — `git clean -xdf` in a scratch copy, `pnpm install`,
`pnpm build`, `cargo build`. A fresh-clone check now is worth an hour; in Week 6 it is worth a day.

**V** — ~~Freeze **S3**~~ — **done early, 25 Aug.** `services/api/tests/fixtures/keys_fake.py` is
written and all six branches were driven against it on port 8001 (`ruff`/`mypy` clean, the 17-test
suite unaffected). `contracts.md` S3 is updated and frozen. **What is left on Friday: commit S1's
section as the frozen record** — the S1 *fixture* itself is blocked on getting the parquet from
Prathamesh, but freezing the column contract is not blocked by that and should still happen.

**S** — Start beta trader recruitment. Target three, from the communities where this strategy
actually lives — futures order-flow forums, Discord servers, the ATAS and Jigsaw communities. **Not
friends.** A friend will tell you it's great, and a friend's "yes" cannot pass the Week 8 gate. You
need a soft commitment to test in Week 7, which is seven weeks out, so start warm now.

**ABC · 16:00 — Week 0 gate.** Every open checkbox in `current.md` is closed or explicitly killed.
Then, in the same sitting, five minutes on `contracts.md` — all three read S1 through S6 out loud
and agree they are frozen. That five minutes is what buys the next eleven weeks of independence.

*Float:* update `plans/current.md` to reflect the reassignment and the killed A2 — whoever is free.

---

## ~~The open hard gate~~ — closed 24 Aug by `c504e50`, read this before acting on it

> **Status, added 25 Aug.** Prathamesh closed this on 24 Aug and it was not visible locally until
> `origin/main` was fetched today. `pull_tbbo_validate.py` reclassifies the 2026-07-16 session by
> the **quote rule** — price against the bid/ask immediately before each trade, ignoring the `side`
> field entirely — and agrees with `SIDE_MAP` on **99.65% of 75,578 comparable trades**, with **0 of
> 23 hours disagreeing in sign** and a footprint cross-check at 980/980 price levels (volume
> r=1.0000, delta r=0.9870). `verify_settlement_close.py` separately resolves the 12.2-point gap
> against TradingView's reported close as a settlement-window-vs-last-trade difference, VWAP
> matching within 0.25 — **that one is a genuinely external reference, so contract and timezone are
> covered too.**
>
> **This closes the gate by changing the method, not by finding a Mac footprint platform.** The
> ranked options below are therefore no longer blocking, and **Shreyas's Week 0 ownership of this
> problem is discharged** — do not spend Thursday on it.
>
> **What survives: session-total delta is method-dependent at ~15–20%** (side field +1,842 vs quote
> rule +2,216). Direction and shape are robust; **absolute magnitude carries that as an error bar**,
> and every threshold derived in Weeks 1 and 4 inherits it. That is the number to argue about now.
>
> `DELTA_CVD_FINDINGS.md` §3 still reads as open — `c504e50`'s own message flags it stale and defers
> the rewrite. **Someone still owes that document an update.**

The original framing is kept below as the record of why the gate existed and what it was for.

`DELTA_CVD_FINDINGS.md` §3 is explicit and correct about this, and it is the most important thing
in that document:

> Everything confirmed so far is **internal consistency** — the data agreeing with itself and with
> published schema semantics. That is meaningfully stronger than an unchecked assumption. It is
> **not** the same as our numbers matching an independent platform's rendering of the same session.

Three independent checks make a sign inversion very unlikely. They **structurally cannot** catch a
wrong contract, a timezone offset, a session-boundary definition differing from the reference, or a
systematic magnitude error. Only a second platform catches those.

**The blocker is hardware, not skill.** ATAS and Sierra Chart are both Windows-only; the machine is
an ARM MacBook Air. Neither runs natively.

**Ranked options — Shreyas owns picking one by Friday:**

| | Option | Cost | Catches |
| :--- | :--- | :--- | :--- |
| 1 | **TradingView web** — `COMEX:GC1!`, 1-min, built-in Cumulative Volume Delta, 2026-07-16. Works on macOS, free tier | free, today | Direction, swings, turning points. **Not tick-for-tick magnitude** — TradingView derives delta from lower-timeframe bars by tick rule, not true aggressor tags |
| 2 | **Screenshot hand-off** — anyone with a footprint platform sends the 2026-07-16 GC session; compare against `gc_cvd_2026-07-16.png` and the footprint CSV | free, needs a person | Everything, if the sender has real aggressor data |
| 3 | **Windows machine or Parallels** — run ATAS demo properly | a licence + a day | Everything. The real answer |

**Do option 1 this week and option 2 or 3 before the Week 3 gate.** Option 1 alone does not clear
the Week 3 gate — that gate says *matching a reference footprint chart*, and a tick-rule
approximation is not one. But it costs nothing and it would catch a timezone or contract error
today rather than in three weeks.

**If it doesn't match, check in this order:** (1) timezone — data is UTC, plots render in
America/New_York, session boundary is 18:00 ET; (2) contract — July 2026 rolls GCQ6 → GCZ6 on 29
Jul, and a reference charting a continuous front-month series may splice differently; (3) the
aggressor mapping, which is now the *least* likely given three confirmations.

---

## What Week 0 kills

**A2 — spot XAUUSD correlation, cut.** It was scoping MT5 spot gold as a launch instrument. The
artifact rules that out: spot gold has no centralised volume, which is precisely why `real_volume`
comes back empty, so there is no delta to compute and nothing to correlate against. Moves to the
Week 12 quarter-two discussion, where MT5 returns as a context-only mode.

`DELTA_CVD_FINDINGS.md` §4 has it as *blocked* rather than cut — Dukascopy is unreachable from the
sandboxes, and it notes the remaining work is straightforward once a month of XAUUSD 1-minute bars
exists locally. **That is true and it is still the wrong thing to spend a day on**, because the
blocker was never the download; it is that spot gold cannot carry the product's core number. Cut
stands. Nobody needs to go find a working Dukascopy mirror.

**The `_to_delete/` housekeeping item — already done.** The artifact flags five stale files in
`apps/extension/_to_delete/`. They are gone from disk and were never tracked (`git ls-files` finds
nothing). Nothing to do; noting it so nobody goes looking.

## Entering Week 1 you must have

- [x] **A month of GC ticks on disk with a verified aggressor split** — done 24 Aug, `8aece67`
- [x] `data/fixtures/gc_ticks_1session.parquet` committed (2026-07-16 GCQ6), with a `.gitignore` exception — **done 25 Aug (`fdb96c8` exception, `14f5547` fixture), before Week 0 started.** Verified: 77,532 rows, six columns, session delta +1,842 matching the findings. **Carries one open item for standup — `'N'` is a real third `aggressor_side` value S1 does not admit; amendment drafted in `contracts.md`, not applied**
- [x] **Reference validation closed** — `c504e50`, quote-rule cross-check, not a charting platform.
      *Residual: session-total delta is method-dependent at ~15–20%; direction and shape are robust*
- [ ] **The Anthropic key revoked** — it was in a chat transcript, and nothing depends on it now
- [ ] A real Tauri window, seen with human eyes, screenshotted
- [ ] The extension confirmed working in Chrome **and** Firefox
- [x] **The analysis backend decided** — our own model (25 Aug). *No live analysis returns; that
      moves to whenever the model lands, and the four-key contract is what makes the wait safe*
- [ ] The own model scoped, and given a week in this schedule
- [x] **S3 frozen; `keys_fake.py` committed** — done early, 25 Aug, all six branches verified live
- [ ] S1 frozen (the column contract — separable from the blocked fixture)
- [ ] Three vendor emails drafted, ready to send Monday 08:00
- [ ] A CA call booked for Tuesday
- [ ] Shreyas able to explain absorption in his own words
