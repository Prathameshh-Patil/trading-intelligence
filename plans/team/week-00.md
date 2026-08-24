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

**V** — Settle the analysis-backend decision, then run the Databento estimate. Decision first:
the artifact's budget line is *"LLM extraction — vision calls for chart context, ~10 users —
$20–50/mo"*, which is a hosted API, and under bring-your-own-feed the model never sees market data
— only a screenshot's symbol and timeframe. Ollama was the privacy answer to a privacy problem that
the architecture has now deleted, and it cannot back a deployed API anyway. **Recommendation: add
$5 Anthropic credit and stop deferring this.** ~3,000 analyses, zero code change, and the change is
already verified end to end except for this. Then: `pull_futures_trades.py --estimate-only` for one
month of GC. *(closes #1's decision half, and #4's secrets half)*

**V — first, before anything else: rotate the Anthropic key.** `DELTA_CVD_FINDINGS.md` §5 reports a
real key was sitting in the git-tracked `.env.example` — uncommitted, confirmed absent from all
branch history, one `git add -A` from being pushed — **and that it was also pasted into a chat
transcript.** The placeholder is restored, so the repo is clean, but a key that has been in a
transcript is a key that should not still be live. Ten minutes at console.anthropic.com. Do it
before you spend money on the account.

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

1. **Cut `data/fixtures/gc_ticks_1session.parquet`** from the existing `data/gc_trades.parquet` —
   the 2026-07-16 GCQ6 session already chosen as the validation session, 77,532 trades. `data/` is
   gitignored, so the fixture needs an explicit exception. **This is S1 and it unblocks every test
   in the next twelve weeks.**
2. **Solve the reference-validation blocker** — see the box below. It is Week 1 Tuesday's whole
   task and it currently has no working path on your hardware.
3. ~~Decide NQ~~ — **dropped.** GC is the launch instrument. One instrument, one set of thresholds,
   one reference session to validate. Everything downstream gets simpler and the ~$11.42 stays
   unspent.

**S** — **Own the reference-chart problem** (see the box below) — it is a tooling and access
question, not an engineering one, which makes it yours. Then draft the vendor licensing email. One precise question, identically worded to Databento,
Rithmic and Tradovate: *"Our software runs on the end user's machine and connects using the user's
own data entitlement. Market data does not pass through our servers. Do we need a distribution
licence?"* Do not soften it, do not add context, do not ask three questions. Get all three drafts
reviewed at standup Friday and send Monday morning. Also: book the CA call for Week 1 Tuesday —
book it now, CAs are not available on two days' notice.

*Float:* if V's pull finishes early, run the first live Claude analysis (`LIVE_API_TESTS=1 uv run
pytest`, 5 tests) — that is the last unverified thing in PR #3 and it takes ten minutes once there
is credit on the account.

*Why nobody is blocked:* P is in Tauri, V is in Databento, S is in a text editor and a calendar.

---

#### W0D3 · Fri Aug 28

**P** — Merge PR #3 if review is clean. Then branch `feat/tauri-overlay` off `main` and confirm the
workspace builds from a fresh clone — `git clean -xdf` in a scratch copy, `pnpm install`,
`pnpm build`, `cargo build`. A fresh-clone check now is worth an hour; in Week 6 it is worth a day.

**V** — Freeze **S3** — write `services/api/tests/fixtures/keys_fake.py`, the 30-line FastAPI app
returning all six branches of the key-validate contract on port 8001. It is not needed until Week 5.
Write it now anyway, while there is slack, because Week 5 has none. Commit `contracts.md`'s S1 and
S3 sections as the frozen record.

**S** — Start beta trader recruitment. Target three, from the communities where this strategy
actually lives — futures order-flow forums, Discord servers, the ATAS and Jigsaw communities. **Not
friends.** A friend will tell you it's great, and a friend's "yes" cannot pass the Week 8 gate. You
need a soft commitment to test in Week 7, which is seven weeks out, so start warm now.

**ABC · 16:00 — Week 0 gate.** Every open checkbox in `current.md` is closed or explicitly killed.
Then, in the same sitting, five minutes on `contracts.md` — all three read S1 through S6 out loud
and agree they are frozen. That five minutes is what buys the next eleven weeks of independence.

*Float:* update `plans/current.md` to reflect the reassignment and the killed A2 — whoever is free.

---

## The open hard gate: reference-chart validation

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
- [ ] `data/fixtures/gc_ticks_1session.parquet` committed (2026-07-16 GCQ6), with a `.gitignore` exception
- [ ] A reference-chart path chosen, and option 1 actually run
- [ ] **The Anthropic key rotated** — it was in a chat transcript
- [ ] A real Tauri window, seen with human eyes, screenshotted
- [ ] The extension confirmed working in Chrome **and** Firefox
- [ ] The analysis backend decided and one live analysis actually returned
- [ ] S1 and S3 frozen; `keys_fake.py` committed
- [ ] Three vendor emails drafted, ready to send Monday 08:00
- [ ] A CA call booked for Tuesday
- [ ] Shreyas able to explain absorption in his own words
