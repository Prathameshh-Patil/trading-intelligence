# Trading Intelligence — Current Plan

Live tracker: who owns what, what is done, what is next. **Last updated: 2026-08-25.**

> **The twelve-week schedule lives in [`plans/team/`](team/README.md).** This file stays the live
> status tracker — what is done, what is open, who owns it. `plans/team/` is the day-by-day
> execution path for all three of us, Week 0 (26 Aug) through Week 12 (20 Nov), derived from the
> *Twelve Weeks to Ten Subscribers* artifact. Start at [`team/README.md`](team/README.md); read
> [`team/contracts.md`](team/contracts.md) before writing any code.

## How the two folders work

| Folder | Answers | Cadence |
| :--- | :--- | :--- |
| `plans/` | *What are we doing, who owns it, what is left* | Edited as work is picked up and finished |
| `daily_updates/` | *What happened on a given day, and how it was verified* | One file per day, append-only once the day ends |

Also in this folder: [`trading_intelligence_day1_plan.md`](trading_intelligence_day1_plan.md),
the original Day 1 plan. Kept as written — it is the brief the work was measured against, so
it is a historical record, not a living document. This file supersedes it for current state.

**The rule:** any change to the repo updates both. `plans/current.md` moves the item's status;
`daily_updates/YYYY-MM-DD.md` records what was actually done and what proves it. This applies
to Claude as much as to either of us — nothing ships without both being current.

Keep a claim and its evidence together. "Endpoint works" is worth nothing; "15 tests pass,
`ruff`/`mypy` clean, live curl returns the documented shape" is worth something. If it was not
run, say so explicitly rather than implying it was.

---

## Ownership

Restated 25 Aug by system, not by task queue — see [`team/roles.md`](team/roles.md).

| Area | Owner | Notes |
| :--- | :--- | :--- |
| **Shell** — `apps/desktop`, `apps/extension`, `apps/web`, capture, packaging | [Prathamesh](team/prathamesh/README.md) | Everything the user touches. Frontend→backend ramp: takes `journal.py` in Week 6, `entitlements.py` in Week 9 |
| **Signal + backend** — `services/engine` (new, Rust), `services/signal-data`, `services/api` | [Varad](team/varad/README.md) | Everything that turns ticks into a number, plus everything on a server. Analyze contract stays frozen: `services/api/README.md` |
| **Product, QA, ops** — `docs/qa`, copy, vendor + compliance calls, AI code review | Shreyas | Domain validation is the load-bearing part: **if Shreyas says the signal looks wrong, that stops the sprint.** Manual: [`team/shreyas/`](team/shreyas/README.md) |
| Deployment, hosting | Varad, Week 5 | Railway or Fly + Supabase + Cloudflare Pages. **Not Vercel** — Hobby prohibits commercial use, and a checkout button counts |

**This reassigns two items below.** The Databento pull (#6) and the delta/CVD work (A1) move from
Prathamesh to Varad, because signal work is now one person's system. `apps/extension` moves from
Varad to Prathamesh for the same reason.

---

## Done

### Day 1 — 2026-08-21 · full detail in [`daily_updates/2026-08-21.md`](../daily_updates/2026-08-21.md)

- [x] **Backend analysis is real** — `app/analysis.py` replaced the hardcoded mock. Lexicon
      with negation handling; deliberately not an ML model, per plan §10.
- [x] **API contract frozen and documented** — `services/api/README.md`. `sentiment` is
      lowercase; `confidence` is 0–100, not 0–1.
- [x] **Validation and error handling** — empty/oversized/malformed input is a clean `422`;
      DB down is a `503`, not a traceback.
- [x] **CORS** — Chrome, Firefox and localhost origins; foreign origins refused.
- [x] **15 tests, ruff and mypy clean**; migrations at head.
- [x] **Extension build unbroken** — a shell heredoc had been pasted into `App.tsx`.
- [x] **Landing page moved to `apps/web`** — it had landed in the extension by mistake.
- [x] **Popup calls the real API** — `activeTab` injection, no content script, no standing
      permission on any site.
- [x] **Cross-browser** — same `dist` loads in Chrome and Firefox.
- [x] **Icons** — none had been declared, so the toolbar entry was a blank placeholder.
- [x] **Demo verified end to end** — loaded unpacked in Chrome, real selection, correct
      verdict. Not simulated.
- [x] **`dist` committed** — a fresh clone can load the extension with no build step.

### Day 2 — 2026-08-24 · full detail in [`daily_updates/2026-08-24.md`](../daily_updates/2026-08-24.md)

- [x] **`apps/desktop` scaffolded** — `create-tauri-app` (React + TS + Vite template), added
      to the pnpm workspace.
- [x] **Existing side-panel UI copied in unmodified** — `SidePanel.tsx`, `lib/`, `ui/`,
      `views/` byte-for-byte identical to `apps/extension` (`diff -q` confirmed). `storage.ts`
      shimmed to `localStorage`, `capture.ts` shimmed to a placeholder — both marked temporary.
- [ ] **Native Tauri window — not yet confirmed on-device.** `tsc`/`vite build` are clean and
      the compiled bundle was screenshotted in headless Chromium at the target window size
      (Home, Rules, Journal — zero console errors), but nobody has run `pnpm tauri dev` and
      looked at a real window yet. Don't check this off until that happens.
- [x] **GC/NQ pull script written, logic dry-run tested** —
      `services/signal-data/pull_futures_trades.py` against Databento's `GLBX.MDP3`, `trades`
      schema, parent symbology. Writes `gc_trades.parquet` / `nq_trades.parquet` with
      `timestamp, price, size, aggressor_side` (+ `symbol`/`instrument_id`). Cost-estimate-first
      flow; per-day active-contract cleanup verified against a synthetic 200k-row roll month
      (correctly split two contracts by day).
- [ ] **Not yet run for real.** Script is written and syntax-checked, not executed against the
      live API — no real row counts, cost, or aggressor split confirmed yet. That's the bar for
      checking this off, not writing the script.
- [x] **API key handled safely** — `.env`/`.env.example`, matching this repo's existing
      convention; never hardcoded into the tracked script.
- [x] **Extension side-panel rewrite pushed, and its build fixed** — the side-panel UI had been
      sitting locally uncommitted; committed and pushed (`b30cee9`). That surfaced two real
      problems, fixed in `955b374`: `src/content/main.ts` no longer existed on disk, and the
      manifest had regressed to `content_scripts` + `<all_urls>` — undoing `8cd4790`'s reasoning
      for dropping it. Fixed by porting `8cd4790`'s `activeTab` + `chrome.scripting` approach
      into `capture.ts` rather than restoring the lost file, so the privacy-conscious permission
      set survives. Also fixed `AnalyzeView.tsx` sending empty text on screenshot-only captures
      (guaranteed 422), and untracked `_to_delete/` in both apps.
- [ ] **Not yet verified in a real loaded extension.** `pnpm build` is clean and `dist/` is
      current, but nobody has loaded the rebuilt extension in an actual Chrome profile and
      confirmed "Capture screen" reads a real selection. Do that before marking this fully done.

### Day 2 (later) — 2026-08-24 · `8aece67`, on `main` · [`DELTA_CVD_FINDINGS.md`](../services/signal-data/analysis/DELTA_CVD_FINDINGS.md)

Landed by Prathamesh after the Day 2 entry above was written, and it closes #6 and most of A1.

- [x] **The Databento pull ran for real** — 1,616,772 GC outright trades, July 2026, **$2.52**.
      `data/` and `*.parquet`/`*.dbn` now gitignored; every billed `get_range()` writes its DBN to
      `data/raw/` before pandas touches it, so a processing failure never costs a second download.
      That paid for itself immediately — the crash below happened after GC had downloaded.
- [x] **The real pull crashed, and the fix is worth knowing.** `to_df()` runs `map_symbols=True`
      and already attaches a `symbol` column; the definitions merge added a second, so
      `df["symbol"]` returned a 2-D frame and `groupby` failed. Databento's copy is now
      `symbol_mapped`, kept as a cross-check — it agrees with the independently-resolved symbol on
      **100.0000%** of 1,769,563 rows. **A synthetic dry-run could never have caught this**, because
      hand-built frames don't carry that column. Also: `size` is `uint32`, so `-df["size"]` wraps to
      ~4.29e9 instead of going negative — cast to `int64` first.
- [x] **Aggressor convention confirmed three independent ways**, which is the thing everything else
      rests on. Databento's `side` is the *initiating* side, and `A`/"Ask" does **not** mean "printed
      at the ask" — reading it the natural-language way inverts the sign and yields a mirror-image
      CVD that looks entirely plausible. `SIDE_MAP` was already correct but unverified. Now: a
      **48.32 / 47.79** buy/sell split · **83%** tick-rule agreement in both directions (an inverted
      mapping would read ~17%) · delta↔return Pearson **+0.50**, stable at 1/5/15-min, which would
      read −0.50 if flipped.
- [x] **Delta, session-reset CVD, 31,306 one-minute bars, and a price-level footprint** —
      `compute_delta_cvd.py`, 439 lines. Session = CME trading day 18:00→17:00 ET, verified against
      the data: every gap >2h falls exactly on a Friday close / Sunday reopen. *EDT-specific — a
      month crossing DST needs a real exchange calendar.*
- [x] **Reference validation — CLOSED 24 Aug by `c504e50`**, by an independent classification method
      rather than an independent platform. See the A1 row in Next for the numbers. The paragraph
      below was written before that commit was known locally and is kept as the record of why the
      gate existed; the one thing it asks for that a quote-rule check still cannot give is an
      independent *rendering*, and the residual ~15–20% magnitude spread is the honest cost of that.
- [ ] ~~**Reference-chart validation — NOT DONE, and correctly called a hard gate.**~~ Everything above
      is *internal consistency*: the data agreeing with itself and with published schema semantics.
      That is much stronger than an unchecked assumption and it makes a sign inversion unlikely. It
      **structurally cannot** catch a wrong contract, a timezone offset, a differing session
      boundary, or a systematic magnitude error. ATAS and Sierra are Windows-only; the machine is an
      ARM Mac. Options ranked in [`team/week-00.md`](team/week-00.md) — TradingView web today (free,
      but tick-rule derived, so it does **not** clear the gate), a screenshot hand-off, or Parallels.
- [x] **NQ dropped, GC is the launch instrument** — decided 25 Aug rather than deferred to Week 1
      Friday. ~~It was never pulled and the ~$11.42 stays unspent.~~
      🔴 **FALSE — corrected 25 Aug evening. NQ was pulled. The money is already spent.**
      `services/signal-data/data/nq_trades.parquet` holds **9,091,850 NQU6 trades** for July 2026
      (73 MB), and `data/raw/NQ_trades_2026-07.dbn.zst` (178 MB) is the billed download behind it,
      timestamped 00:42 on 25 Aug — seven minutes after GC's. `run.log:31` reads
      `[NQ] CACHED trades: reusing ... no API call, no cost`, which is what the record was built
      on: that line describes the *second* run reusing a cache, not the first run that paid for it.
      A 178 MB Databento DBN does not exist without a billed `get_range()`.
      **What this does to the decision:** the two strong arguments are untouched — one instrument
      still means one set of thresholds, one reference session, one adapter to harden, and a second
      instrument in Week 9 is still a Week 2-shaped job in the month engineering should be slowing
      down. **The two stated premises are both false**, though: "only GC has data" is wrong, and
      "spend ~$11.42 to manufacture a choice" is wrong because the choice was already paid for.
      The Week 1 Friday decision would have been real, not theatre.
      **Nothing here reverses the drop** — that is a standup call, not a repo edit. But it should be
      re-taken on true premises, and it is worth ten minutes on Wednesday. *(NQ's aggressor split is
      50.07 / 49.93 with **27 unknown rows, 0.0%**, against GC's 3.89% — a materially cleaner feed.)* One instrument means one set of
      thresholds, one reference session to validate, and one feed adapter to harden. `strategy.md`'s
      ≥60 NQ / ≥200 ES figures remain the **derivation source** the GC thresholds are scaled from,
      not thresholds anyone implements. A second instrument is a quarter-two candidate — a full feed
      adapter, re-derived thresholds and its own validated reference session, not a flag flip.
- [ ] **The Anthropic key needs revoking.** A real key sat in the git-tracked `.env.example` —
      uncommitted, confirmed absent from all branch history, one `git add -A` from being pushed.
      Placeholder restored, so the repo is clean. **But it was also pasted into a chat transcript**,
      and a key that has been in a transcript should not still be live. *Revoke*, not rotate —
      the own-model decision leaves nothing depending on it.

### Day 3 — 2026-08-25 · full detail in [`daily_updates/2026-08-25.md`](../daily_updates/2026-08-25.md)

Shipped as [PR #3](https://github.com/Prathameshh-Patil/trading-intelligence/pull/3) (`feat/claude-analysis`), open for review.

- [x] **The lexicon is gone — `analyze()` calls Claude** (`claude-haiku-4-5`). `app/analysis.py`
      is now one `messages.parse` call against a Pydantic schema; structured outputs enforce
      the shape, so a malformed answer raises server-side instead of reaching the popup as a
      wrong-shaped `200`. The four keys did not change, which is what made this the drop-in
      the plan said it would be — no extension change, no contract change.
- [x] **Upstream failure is a `503`, not a `500`** — `APIError` (down, rate-limited,
      bad key) and a schema-failing answer both map to
      `{"analysis": "unavailable"}`, matching the DB health check's existing shape. The
      extension already renders any non-200 generically, so nothing there needed touching.
- [x] **`ANTHROPIC_API_KEY` is a required setting**, same as `DATABASE_URL` — missing key
      fails at startup, not at the first request. `.env.example` updated in both places.
- [x] **Tests restructured, `ruff`/`mypy` clean.** 17 tests pass without a valid key. Four
      swap the Anthropic *transport* rather than stubbing `analyze`, so the real request
      building and decoding in `analysis.py` are exercised — stubbing `analyze` left it with
      no coverage at all. The old sentiment assertions moved to 5 live tests behind
      `LIVE_API_TESTS=1`; they skip on a normal run and cost nothing.
- [x] **Verification caught a real defect, now fixed.** The first version validated the
      *prompt's style* (`confidence` 50–95, ≤4 signals) as if it were the contract. The API
      does not enforce numeric bounds or list maximums — the SDK strips them from the
      generated schema and they survive only as a description hint, confirmed by dumping the
      schema. Since `messages.parse` validates client-side, a usable answer that came back
      with `confidence: 97` became a `503`. `Analysis` now validates the contract (0–100,
      non-empty signals); the prompt still asks for 50–95 and 1–4. Regression test added.
- [x] **The failure path is verified against the real API.** A live call with an invalid key
      reached `api.anthropic.com` and returned `AuthenticationError` (401), which is an
      `APIError` subclass and maps to the `503` as designed. Free, and it proves the error
      handling works against the real service rather than against a mock of it.
- [ ] **The success path has still never run — now blocked on billing, not on code.** A real
      key was created and works: requests authenticate and get past schema validation to the
      billing check, which returns `400 "credit balance is too low"`. Correctly surfaced as a
      `503` with the reason readable in `detail.error`. Nothing was charged. So no analysis has
      ever been produced: no confirmed latency, no measured cost, and the system prompt's
      sentiment behaviour is entirely unvalidated. Everything else about the change is verified;
      this one thing is not. **And as of the own-model decision below it stays that way** — this
      is no longer a few days from being closed by a $5 top-up. Whatever sentiment quality the
      product ships is now the own model's to earn, and the four Day 1 cases (bullish, bearish,
      neutral, negation) are the bar it has to clear, exactly as they were for the lexicon.
- [x] **S3 frozen and its fake landed** — `services/api/tests/fixtures/keys_fake.py`, pulled forward
      from W0D3 because it needs nothing that is blocked. All six branches of the key-validate
      contract were driven against a real server on port 8001, not asserted from reading:
      `core` → `200 tier core`, `journal` → `200 core_journal` with an expiry, `expired`/`revoked`
      → `200 valid:false`, an unknown key → `200 reason:unknown`, and `ti_live_down…` → `503`. The
      branch is chosen by the key, so Prathamesh can reach every one on demand in Week 5 rather
      than only when the server happens to be in that state. **`valid:false` is a 200, not a 401** —
      that is the load-bearing part of S3, because the desktop app must tell "your key is bad" apart
      from "we couldn't reach the server". A missing header is a 422. `ruff`/`mypy` clean and the
      17-test suite is unaffected. `contracts.md` said W1D1 while both schedule files said W0D3;
      that contradiction is resolved to W0D3.
- [x] **Two leftovers from the NQ drop, found by re-grepping rather than assuming** —
      `team/varad/README.md` still told Varad to run the Databento estimate for "one month GC + NQ"
      on Wed 26, contradicting the drop decided the same day; and `contracts.md` carried the S3
      date contradiction above. Both fixed. `pull_futures_trades.py` still has its `NQ` entry and
      that is **deliberate** — dropping NQ was a scope decision, not a decision to delete the
      capability, and it returns as a quarter-two candidate.
- [x] **The analysis backend question is closed — we build our own model.** Decided 25 Aug.
      None of the three hosted options weighed earlier that day (Anthropic credit, Ollama,
      Gemini free tier) is taken; **no money goes on any account and the analysis work is parked
      until the model exists.** Claude stays in `analyze()` as the interim implementation — it
      is written, typechecked and tested, and ripping it out now would buy nothing but an empty
      route.
      **What this changes:** the `$5 credit` recommendation is withdrawn everywhere; the "first
      live analysis" is no longer pending-on-billing, it is *not happening* on this backend; and
      the 5 `LIVE_API_TESTS=1` tests stay skipped indefinitely rather than for a few more days.
      **What it does not change:** the four-key contract stays frozen, so the own model drops in
      behind the same `analyze()` signature with no route, contract or extension change — the
      same swap already performed once on Day 3, lexicon → Claude, with zero extension edits.
      **Two things this now needs and does not have:** a home in the twelve-week schedule (no
      week in `plans/team/` budgets for training or serving a model), and a decision on whether
      it serves from the same box as the API — which is the other half of #4.

### Day 3 (evening) — 2026-08-25 · Prathamesh's lane

Three Week 0 / Week 1 items taken early, chosen because everything left on Prathamesh's Week 0
list needs a device and a pair of eyes (a real Chrome profile, a real Tauri window) and these
needed neither.

- [x] **S1 fixture cut and committed** — `14f5547`, above. Closes #6 outright and discharges
      Varad's Thursday item 1, which `week-00.md` still had marked blocked.
- [x] **S1's `'N'` contradiction found and amended** — the contract pinned `aggressor_side` to
      `'B' | 'A'` while stating a row count that includes 1,811 trades (2.34%) with neither.
      Both could not hold. Resolved in the fixture by keeping every row and emitting `N`;
      `contracts.md` S1 now carries the amendment and the counts. **Not frozen by this** — S1's
      freeze is Friday's gate and the amendment goes into it, which is the right order.
      Consumers must exclude `N` from delta and never guess it: it carries real volume, so
      treating the split as exhaustive biases every CVD in the product by 2.34%.
- [x] **Fresh-clone build check — passes, done early** (W0D3). `pnpm install` clean,
      `pnpm build:all` green across extension/desktop/web, `cargo build` clean in 35.66s cold.
      Run against a scratch `git clone`, **not** `git clean -xdf` in place — see the new standing
      constraint below, this one nearly cost the month of tick data.
- [x] **⚠️ `pnpm build` covers one of four workspace projects** — root `build` is
      `pnpm --filter extension build`. The fresh-clone check as written in `week-00.md` would
      have gone green with `apps/desktop` and `apps/web` both broken. `pnpm build:all` is the
      real check. Decide at Friday's gate whether root `build` should just be `build:all`.
- [x] **S2 frozen in code — `apps/desktop/src/lib/engine/types.ts`** (W1D1, pulled forward).
      Faithful transcription of `contracts.md` S2 plus S6's `CaptureContext`; `tsc --noEmit`
      clean and the file is confirmed in the compilation, not merely on disk. This is the item
      `prathamesh/README.md` calls *"the most valuable half hour of the week"*, and it unblocks
      `engine/mock.ts` (W1D2) and all UI work in Weeks 1–3.
- [ ] **`FeedCreds` is undefined and S2 cannot be fully frozen until it isn't.** It is named in
      the `Engine` interface at `contracts.md:119` and **defined nowhere in the repo** (grepped,
      not assumed). Left deliberately open in `types.ts` rather than invented, because the
      credential fields are a function of the vendor and **the vendor is itself open** — C1
      proposes Databento → quantfeed and says plainly that nothing about it is confirmed.
      Guessing now means freezing a wrong guess. **Blocks nothing before Week 3** — `mock.ts`
      ignores creds — but it must be closed before the W3D3 integration day.

---

## Next

Ordered. Days 1–3 are complete except the items explicitly left unchecked above — a real
`pnpm tauri dev` window, reloading the extension, and the S1 fixture cut. Those are #6–#8
below, not optional, and they are the same shape: code that type-checks and tests green but
has never been run for real.

**#1 is no longer one of them.** The first live analysis was the fourth item on that list
until 25 Aug, when the backend question was closed by deciding to build our own model. It is
not blocked-and-waiting; it is off this list until that model exists.

| # | Item | Owner | Notes |
| :--- | :--- | :--- | :--- |
| 0 | 🔑 **Revoke the Anthropic key** | Varad | It was in the tracked `.env.example` (uncommitted, absent from history, placeholder restored) **and in a chat transcript.** Ten minutes, at console.anthropic.com. *Revoke*, not rotate: the own-model decision means nothing depends on it and there is no replacement to issue, so this got easier — the suite stays green on a placeholder because the tests only need the key **present**, not valid |
| 1 | ~~Pick the analysis backend, then run the live analysis once~~ — **PARKED 25 Aug: we build our own model** | Varad | No hosted backend is bought, so no live analysis runs and the 5 `LIVE_API_TESTS=1` tests stay skipped. Claude stays in as the interim implementation; the four-key contract stays frozen, so the own model is a drop-in behind the same `analyze()` — the Day 3 lexicon→Claude swap already proved that seam holds. **Scoped 25 Aug — and it does not need a week.** The "own model" turned out not to be a replacement for `analyze()` at all: it is a **GC strategy selector**, and it is a *personal research tool*, not a product feature. Design in [`docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md`](../docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md). It takes no week from `plans/team/`, so the "unscheduled model eats Week 6" risk is closed by the thing not being scheduled rather than by scheduling it. **`analyze()` keeps Claude as its interim implementation and stays `503` indefinitely** — that is unchanged and still unverified end to end |
| 2 | Click the demo through in **Firefox** | Either | Installs cleanly and CORS accepts it; only Chrome has rendered a verdict |
| 3 | Review the **popup UI** | Prathamesh | Written from scratch to unbreak the build — a starting point, not a design |
| 4 | Decide **where the API lives** | Both | Popup hardcodes `http://localhost:8000`, matching `host_permissions`; a deployed URL changes both, and the CORS entries start mattering once `host_permissions` no longer covers the host. **Now also a secrets question:** the API holds an Anthropic key, so it needs somewhere that can hold an env var — and the key must never move into the extension, which is public |
| 5 | **AMO / Web Store** submission prep | Undecided | See constraints below |
| 6 | ~~Run the Databento pull for real~~ — **DONE 24 Aug, `8aece67`** | Prathamesh | 1,616,772 GC trades, $2.52, aggressor split 48.32/47.79 — inside the band. Exceeded the bar this row set. **The S1 fixture cut is also done — 25 Aug, `14f5547`, and this row is now closed.** 77,532 rows, 110,817 contracts, GCQ6 only, committed through the `.gitignore` exception with `cut_s1_fixture.py` beside it so it is reproducible rather than a binary someone once made. Verified by reading the file back (dtypes conform; `timestamp` survives the round-trip as `datetime64[ns, UTC]`, not a silent `[us]` downgrade). **Nobody needs to ask for the parquet at Wednesday's standup and nobody re-pulls** — the ~$2.52 fallback stays unspent. *(NQ's ~$11.42 did **not** — see the corrected NQ bullet above; it was pulled on 25 Aug and the record was wrong.)* **It did change S1:** `aggressor_side` is `'B' \| 'A' \| 'N'`, N = 1,811 trades (2.34%) with no aggressor disseminated. Amendment written into `contracts.md` S1, **pending Friday's freeze gate** |
| 7 | Confirm `pnpm tauri dev` opens a real window | Either | Headless-browser screenshot of the compiled bundle isn't the same as a real native window — nobody has looked at one yet |
| 8 | Load the rebuilt extension in Chrome, confirm capture still works | Either | The `activeTab`/`scripting` rewrite (`955b374`) hasn't been checked in a real loaded extension. Fold #1's click-through into this if doing both at once |
| A1 | Compute delta and CVD ~~from the tick data~~ **done** · ~~validate against a real footprint chart~~ — **SUBSTANTIALLY CLOSED 24 Aug, `c504e50`** | Prathamesh | Closed by an independent *method* rather than an independent platform, which sidesteps the Windows-only blocker entirely: `pull_tbbo_validate.py` reclassifies every trade in the 2026-07-16 session by the **quote rule** (price vs the bid/ask immediately before the trade), using the `side` field not at all. **99.65% agreement with `SIDE_MAP` across 75,578 comparable trades**, a near-symmetric confusion matrix (96 vs 165), **0 of 23 hours disagreeing in sign**, and a footprint cross-check at 980/980 common price levels with volume r=1.0000 and delta r=0.9870. Separately `verify_settlement_close.py` resolved the 12.2-point gap against TradingView's reported close as settlement-window-vs-last-trade, VWAP matching within 0.25 — that one **is** an external reference, so contract and timezone are checked too. **Residual, and it must be carried downstream:** session-total delta is method-dependent at the ~15–20% level (side field +1,842 vs quote rule +2,216). **Direction and shape are robust; absolute magnitude needs an error bar.** *(`DELTA_CVD_FINDINGS.md` §3 rewritten 25 Aug — it now records the gate as closed, carries the residual as the file's headline number, and inverts the debugging order so the aggressor mapping is checked **last**, since it has four independent confirmations)* |
| A2 | ~~Pull spot XAUUSD, compute GC-vs-spot correlation and basis distribution~~ — **CUT 25 Aug** | — | Killed by the artifact's Fact Two, not deprioritised. It was scoping MT5 spot gold as a launch instrument; spot gold has no centralised volume — which is exactly why `real_volume` comes back empty — so there is no delta to compute and nothing to correlate against. Returns in the Week 12 quarter-two discussion as a **context-only** mode: rules, journal and capture work on MT5, delta does not, and we never claim it does. *(`DELTA_CVD_FINDINGS.md` §4 said "blocked on Dukascopy being unreachable" — true, and the wrong reason. Rewritten 25 Aug to lead with the real one: the blocker was never the download, it is that spot gold cannot carry the product's core number, so **nobody needs to find a working mirror**.)* |
| C1 | 🚚 **Feed vendor change — Databento → quantfeed** | Varad, **raise Wed 26** | Decided 25 Aug. Cheaper, and offers L1/L2/L3. **Contained:** Databento appears in exactly two files, both pull scripts; `compute_delta_cvd.py` reads the parquet through the S1 column contract and does not know who produced it, so the migration is "emit the same six columns" and nothing downstream moves. **What does not transfer is the load-bearing part:** the 99.65% quote-rule agreement validated *Databento's* `side` semantics (`A` = seller-initiated, which reads backwards in English). quantfeed's convention must be re-validated from scratch or every delta sign is a coin flip — `pull_tbbo_validate.py` is that harness and is reusable. **With L3 the quote rule becomes unnecessary**, since order-by-order data gives the aggressor exactly — strictly stronger than what closed the Week 3 gate. **Nothing about this vendor is confirmed yet**; §5 of the selector spec has the checklist. ⚠️ **Shreyas sends three distribution-licence emails Monday 31 Aug** (Databento, Rithmic, Tradovate) — if the vendor is changing, that list is wrong before it is sent. **Do not delete the Databento path** until quantfeed reconciles against the existing validated month; it is the only ground truth for checking the new vendor |
| B | Make `apps/desktop` behave like a real overlay — transparent, borderless, always-on-top, click-through toggle. Prove it floats over a live MT5 demo and that click-through reaches MT5 underneath | **Prathamesh**, W1D2–W2 | No longer gated on A1/A2 — it is Week 1 Day 2 and Week 2 in [`team/phase-1-kill-week.md`](team/phase-1-kill-week.md). Install the MT5 demo terminal first if nobody has it |

---

## Standing constraints

Things that are cheap to break and expensive to notice.

- **Python 3.12 only.** `requires-python = ">=3.12,<3.13"` is load-bearing. If a package will
  not resolve, change the package, not the bound.
- **Lockfiles are the source of truth.** `uv.lock` and `pnpm-lock.yaml` — let the tools write
  them, and give dependency changes their own reviewed commit.
- **Never `git clean -xdf` in this working copy.** `services/signal-data/data/gc_trades.parquet`
  is gitignored, was never pushed, and is **the only copy on any machine** of the 1,616,772-trade
  July 2026 pull that cost $2.52 and underwrites every delta number in the project. `-x` means
  "ignored files too", so it deletes exactly that. `.env` files and both `.venv`s go with it.
  **For a fresh-clone check, `git clone` into `/tmp`** — same guarantee (tracked files only),
  none of the blast radius. Noted 25 Aug when the W0D3 task, as written, said `git clean -xdf`.
- **`pnpm build` is not a whole-workspace build.** Root `build` is
  `pnpm --filter extension build` — one of four projects. **`pnpm build:all` is the real one.**
  A green `pnpm build` says nothing about `apps/desktop` or `apps/web`, which is the trap a
  fresh-clone check exists to catch and would itself have walked into.
- **The add-on id is permanent.** `browser_specific_settings.gecko.id`. Changing it after
  release makes existing installs a *different* add-on, not an update.
- **`strict_min_version` is 140**, because `data_collection_permissions` requires it. That
  excludes Firefox 109–139. Chosen deliberately on 21 Aug.
- **Rebuild `dist` with any `apps/extension/src` change** and commit it in the same commit. A
  clean `git status` after `pnpm build` means `dist` is current.
- **The API contract is frozen.** Changing field names or the confidence scale breaks the
  extension silently — no type checker spans that boundary.
- **`.env` stays local.** Only `.env.example` is tracked. It now carries two secrets, not
  one: `DATABASE_URL` and `ANTHROPIC_API_KEY`.
- **`.env` and `.env.example` sit next to each other and read almost identically.** A real
  key went into the tracked `.env.example` once already (25 Aug), and it was staged before it
  was caught — `git commit -a` would have committed it. Nothing leaked and no rotation was
  needed, but check which of the two files you are editing. `git check-ignore -v <file>` is
  the one-second answer.
- **`/api/v1/analyze` has no working backend.** The interim implementation calls Claude, and the
  account has no credit, so every call returns `503 analysis unavailable`. That is the *correct*
  behaviour for an unreachable upstream, not a bug — but it means the endpoint is not usable for
  anything right now, and nothing downstream should be written as though it is until the own model
  lands. **Nothing rate-limits or caches it**, which stopped mattering the day it stopped costing
  money and starts mattering again the moment the own model is serving.
- **Sentiment behaviour is held in place by nothing that runs.** In the interim implementation it
  lives entirely in the system prompt in `app/analysis.py`; no type checker and none of the default
  tests touch it, and the 5 `LIVE_API_TESTS=1` tests that would are skipped with no backend to run
  against. **This transfers to the own model unchanged** — it will have its own untested-by-default
  judgement, and the four Day 1 cases (bullish, bearish, neutral, negation) are the bar for both.
  Whatever replaces `analyze()` needs those four re-runnable without a paid API behind them.
