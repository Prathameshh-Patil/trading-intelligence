# Trading Intelligence — Current Plan

Live tracker: who owns what, what is done, what is next. **Last updated: 2026-08-26.**

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
- [x] **Native Tauri window — confirmed on-device 25 Aug.** `pnpm tauri dev` compiles and
      launches `target/debug/desktop`, and the window it opens is a real AppKit window, not a
      headless render: the accessibility API reports **one window, title `Trading Intelligence`,
      size 460×820** — the exact `tauri.conf.json` geometry — and Launch Services shows the
      process registered `Foreground` with WebKit's `Networking` and `GPU` XPC children alive,
      which only spawn for a real `WKWebView`. **What is still unchecked is what is *inside*
      it:** no screenshot was taken (screen recording permission is not granted), so "a window
      opens at the right size" is proven and "the UI renders correctly in it" is not — that
      one is an eyeball, and the window is the place to do it.
- [x] **GC/NQ pull script written, logic dry-run tested** —
      `services/signal-data/pull_futures_trades.py` against Databento's `GLBX.MDP3`, `trades`
      schema, parent symbology. Writes `gc_trades.parquet` / `nq_trades.parquet` with
      `timestamp, price, size, aggressor_side` (+ `symbol`/`instrument_id`). Cost-estimate-first
      flow; per-day active-contract cleanup verified against a synthetic 200k-row roll month
      (correctly split two contracts by day).
- [x] **Run for real 24 Aug** (`8aece67`, Prathamesh) — **stale box, corrected 25 Aug.** The live
      call returned **1,616,772 GC trades for $2.52**, aggressor split 48.32/47.79, and running it
      is what surfaced the real-pull crash that same commit fixes. Row #6 in `Next` has carried
      the numbers since; this checkbox simply never moved. NQ was never pulled and is now dropped.
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
      🔴 **Corrected 26 Aug at merge:** this bullet said `contracts.md` now carries the
      amendment. It did on this branch — but the shared `contracts.md` carries it as **drafted
      and NOT applied**, because S1 changes only by all three agreeing in standup. The finding
      and the consumer rule are unchanged; only its status is. It is a yes/no for Wednesday's
      standup, not a Friday freeze formality.
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
### Day 3 (night) — 2026-08-25 · Stage 1's machinery · [`daily_updates/2026-08-25.md`](../daily_updates/2026-08-25.md)

The part of the selector design the S1 fixture unblocks. **No strategy is evaluated and no result
is claimed** — §8 of the design says one session builds and tests Stage 1's machinery and cannot
run it, and that boundary was held.

- [x] **`services/signal-data` has an environment, pinned to 3.12.** It had no `pyproject.toml`,
      so its scripts ran against ambient `python3` — **3.14.6 on this machine**, against a repo
      whose standing constraint is 3.12-only. Now `requires-python = ">=3.12,<3.13"`, the same
      load-bearing upper bound `services/api` carries, with `uv.lock` committed and `.venv` on
      **3.12.12**.
- [x] **`s1.py` — the S1 contract read once**, 100 lines. All three `contracts.md` traps encoded
      rather than commented: `SIDES` covers `B`/`A`/`N` and **raises** on an unknown code instead
      of defaulting to zero, `size` is cast before negation, nothing deduplicates. Reproduces the
      contract's own numbers on the fixture — 77,532 rows, **session delta +1,842**, `N`
      contributing 0, bar volume reconciling to 110,817 contracts.
- [x] **A real bug, found by pointing the old script at the new fixture.**
      `compute_delta_cvd.py` matched on `buy_initiated`/`sell_initiated` — what the pull script
      writes — while the S1 parquet carries `B`/`A`/`N`. `np.select` returned its default, so the
      project's main analysis script read **the file every test asserts against for twelve weeks
      as zero delta on every row, silently**, and printed a clean plausible empty result. Same
      class of failure as the `'N'` NaN: a mapping that does not cover its input.
- [x] **Fixed by deletion, not by patching.** `compute_delta_cvd.py`'s `load_trades`, `add_delta`,
      `session_cvd`, `minute_bars` and `SESSION_SHIFT` are gone and imported from `s1.py` —
      **439 → 376 lines**, one definition of a session and a bar. **Proof it changed nothing
      else:** the script re-run end to end on the fixture produces a footprint identical to the
      committed `analysis/gc_footprint_2026-07-16.csv` — cut from the *full month* through the
      *old* code — at **980 of 980 price levels, max abs diff 0**.
- [x] **`backtest.py` — design §4's metric set**, 108 lines. Horizons measured on the **clock, not
      row offsets** (empty minutes are dropped, so `iloc[i+5]` can be an hour later); no window
      crosses a session boundary; MFE/MAE per horizon; every summary carries `n` and a `thin` flag
      that fires under 30 samples, which is §6.5 made mechanical. `random_entries` is §6.3's null
      with matched count, holding period **and side mix**.
- [x] **16 tests, `ruff` and `mypy` clean on the new files.** 7 assert the contract's own numbers
      against the real fixture — including one that runs `drop_duplicates()` and asserts the
      **+1,842 → +1,989** drift, so the trap is executable rather than a paragraph. 9 run on
      hand-built bars where the answer is known by construction. One of them corrected a wrong
      comment of mine: MAE is the *least favourable* excursion and is **positive** when a trade
      never goes adverse.
- [x] **`ruff` and `mypy` clean across the whole module, not just the new files.** The four older
      scripts' 7 lint findings and 6 type errors — recorded that afternoon as cosmetic and left
      alone rather than folded into an unrelated change — are now their own change. **One was not
      cosmetic:** `pull_futures_trades.py` chose its default month with `date.today()`, and from
      IST the calendar flips 2.5h *before* August's last CME session ends, so a no-`--month` pull
      between 00:00 and 02:30 IST on 1 September would have bought an unfinished August and
      returned a truncated file that looks complete. Now on the exchange clock, matching the `ET`
      convention already in two sibling scripts. The rest are stub-precision casts and one
      `type: ignore` that carries its reason; the five shebangs were **deleted rather than
      `chmod +x`**, because they advertised a `./script.py` invocation that dies on the first
      import outside the `uv` venv. **16 tests still pass and `compute_delta_cvd.py` re-run on the
      fixture is identical to the committed footprint at 980/980 levels, max abs diff 0.** The two
      pull scripts were not re-run — both bill a live Databento call
- [ ] **Nothing is backtested, on purpose.** The harness was driven with a throwaway z-score rule
      (N=60, one session) to exercise the code; those numbers are a mechanism check, not evidence
      about GC, and are recorded as a finding nowhere.
- [x] **`thresholds_selector.md` written — Part A binding, Parts B and C empty on purpose.**
      §6.1's instrument, same mechanism as [`team/varad/thresholds.md`](team/varad/thresholds.md):
      a git timestamp earlier than the results. Part A restates what the design already committed
      to — walk-forward, both nulls, the sub-30 floor (which `backtest.py` now flags mechanically),
      ±20% threshold perturbation, pre-filter/post-filter side by side — so the committed file is
      the whole commitment rather than a pointer to one. **Parts B and C are the numbers, and they
      are Varad's**, for the same reason §3's `decision_filter.py` is: a threshold picked by an
      assistant looks like the mechanism working while doing none of what it is for.
- [ ] **⛔ Blocked on Varad, and this is now the only thing between here and a first backtest.**
      Part B needs the 3–4 candidate strategies stated precisely enough to implement, each with
      its committed median/hit-rate/margin-over-null/minimum-N — and the line the sibling file
      calls the most important one: *what result would make me say no.*

---

### Day 4 — 2026-08-26 · the candidates, as machinery · [`daily_updates/2026-08-26.md`](../daily_updates/2026-08-26.md)

The file the rules get written into, built so it **cannot be run before Part B exists**. Same
boundary as Day 3 and held the same way: no backtest, no result claimed about GC.

- [x] **`strategies.py` — 191 lines, 11 tests.** Four state features (`delta_z`, `cvd_slope`,
      `absorption`, `bar_imbalance`) that §2's `regimes.py` will read rather than re-derive, and
      four candidates (`delta_outlier`, `cvd_divergence`, `absorption_fade`, `footprint_stack`),
      each `(bars, *, thresholds) -> Series of +1/-1/0` — what `backtest.evaluate` already
      consumes. **`s1.py` and `backtest.py` untouched.**
- [x] **Built flat as `strategies.py`, not §7's `strategies/gc.py`.** A package directory for one
      module while GC is the only instrument buys nothing; `NQ` was dropped and the rest of the
      folder is flat. Rule of three — no package until a second instrument exists. Departure from
      the spec, agreed before writing.
- [x] **Entry-only; the horizon is the exit.** `backtest.evaluate` has no exit mechanism, and
      MFE/MAE already say what a stop or target would have done without committing to one. A stop
      and a target per strategy would be two more Part B numbers and a multiplied search space
      §6 exists to guard. If a candidate survives its bar, the exit engine gets built then.
- [x] **§6.1 enforced by the signature, not by memory.** No threshold has a default, so calling a
      strategy without its numbers raises `TypeError` — and `mypy` rejects the same calls
      independently. The gate holds even for someone who has not read the file.
- [x] **Three lookahead traps, one test each**, all of which produce plausible-looking output:
      session-scoped statistics (a 09:30 bar scored against the day's own σ has read the
      afternoon); rows-not-minutes (`minute_bars` drops empty minutes, so `.rolling(30)` is thirty
      *bars* — the trap `backtest.py` already solved for horizons); and reading a later bar,
      tested by mutating the future and asserting the past did not move. Plus two that turn the
      *strongest* case into a dropped row: `high == low` must not divide by zero, and a lone print
      with nothing opposite is not an infinite imbalance.
- [x] **28 tests pass, `ruff` and `mypy` clean** — `mypy` over `tests/` too, matching Day 3.
- [x] **A real defect in `absorption`, found by printing the distribution Varad asked for.** The
      ratio `|delta| / range_ticks` is **scale-free**, so a 5-lot bar in a one-tick range scores
      exactly what a 294-lot bar in a 21-tick range does. On the real session, half the top-eight
      bars were 5-, 6-, 16- and 32-lot prints in the Globex-open dead zone — the rule was
      selecting for **illiquidity**, the opposite of absorption. It would have entered Stage 1
      firing on an empty overnight market and produced a perfectly plausible distribution.
      **Fixed:** `absorption_fade` now requires `min_delta` alongside `min_ratio`, with a test
      that a 5-lot tight bar does not fire and a 900-lot one does. The scale, for the record:
      p50 **0.61**, p99 **4.35**, max **10.67** — the placeholder had been 500.
- [ ] **A rule question for Part B that is not a threshold.** Absorption is classically a
      *price-level* phenomenon — size stacking at one price and failing to break it — and
      `compute_delta_cvd.py`'s `footprint()` already aggregates by price level. `|delta| / bar
      range` is a proxy, and with a median bar range of **15 ticks** it is a loose one. Whether
      absorption should be measured at the price level instead is Varad's call, and it comes
      before any number does.
- [x] **Smoke run on the fixture — counts only, no forward returns computed.** 77,532 trades →
      1,379 bars. `delta_outlier` 19 signals, `cvd_divergence` 24, `absorption_fade` **0** (off-scale placeholder, see the defect above),
      `footprint_stack` 64. The zero is an off-scale placeholder, not a dead rule; **the ratio's
      distribution was deliberately not printed**, because knowing the p99 of what you are about
      to threshold is the contamination §6 exists to prevent. Three of four candidates land under
      A4's sub-30 floor from one session, which is §8's point made mechanical.
- [ ] **The prose in each docstring is a proposal, not a transcription.** It is a literal reading
      of each family, and the likeliest one to be wrong says so in the file: `absorption_fade`
      assumes the aggressor was trapped, where the same bar reads as *continuation* if you think
      the aggressor is early. One sign change either way, but it is a decision.
- [x] **`stage1.py` — the runner, 118 lines, 6 tests.** Every candidate through `backtest.py`
      with its null and A5's perturbation: one row per strategy × variant × horizon, N on all of
      them. Holds **no thresholds of its own** — the caller binds bars (and ticks) with
      `functools.partial` and supplies the committed numbers, which is what lets candidates of
      different arities share one loop. `decision_filter` is a parameter, not a stub module, and
      the `filtered` variant appears only when one is given; its absence is the honest report that
      none has been applied. **No walk-forward split, deliberately** — A1's split is about regimes,
      regimes are Stage 2, and nothing here fits anything. `tests/conftest.py` added because
      `bars_at` was about to become its third copy. **34 tests, `ruff` and `mypy` clean on 9 files.**
- [x] **A5 does not mean what it looks like for two of the four candidates.** It exists for the
      ~15–20% delta method-dependence, and that reasoning holds for a threshold in **contracts**.
      A z-score divides by the standard deviation of the same series, so a uniform 20% rescale of
      delta cancels exactly — asserted in a test: `delta_outlier`'s signals are *identical* on a
      frame whose delta reads 20% larger, `absorption_fade`'s are not. `footprint_stack`'s `ratio`
      is invariant for the same reason. **So `cvd_divergence` and `absorption_fade` carry the
      inherited error; `delta_outlier` and `footprint_stack` are structurally immune.** Reporting
      `delta_outlier`'s ±20% threshold swing as if it were the inherited error would *overstate*
      its uncertainty. `PERTURB` in `stage1.py` records which keys move and why.
- [x] **`bar_imbalance` benchmarked, and the concern is closed.** Flagged as the expensive
      candidate and worth timing before it went inside any loop: **0.02s on all 77,532 ticks**,
      extrapolating to roughly **0.4s for a 1.6M-trade month**. A full `stage1.run` over the
      session is 0.35s. Measured, not assumed.
- [x] **Part B scaffolded, and deliberately not filled.** Asked to fill it in, Claude declined the
      numbers: §6.1's mechanism is a commitment by the person with the bias, and a threshold picked
      by an assistant makes the guardrail *look* satisfied while doing none of its work. What was
      written instead is the four blocks with the rules transcribed from their docstrings, each
      naming exactly which thresholds its function requires, plus the table of which two candidates
      inherit the ±15–20% delta error. **Every `<...>` field is empty and still Varad's.** The
      file's status section records the ask and the refusal, so the history shows the gate holding
      rather than the file quietly filling up.
- [ ] **⛔ Still blocked on Varad, unchanged.** Part B is still the only thing between here and a
      first backtest. Four rule-shaped functions now exist to be corrected rather than four blank
      blocks — a smaller ask, the same ask. **Part B must be committed before the first backtest
      runs, not before it is presented**; the git timestamp is the entire mechanism.


### Day 4 (evening) — 2026-08-26 · Stage 2 arrived, and did not run · `f7e411e`, `dcbde04`

`regimes.py` (642 lines) and a committed k=3 run — `regime_labels_window_5min_k3.csv` (6,277 rows),
`regime_definitions_window_5min_k3.json`, and a plot — came in with the afternoon pull, on
`56bbf73` / `70b5ac4` / `477dee3`. **Neither this file nor `daily_updates/` moved with them**, which
is the one rule at the top of this document. Recorded here after the fact; the entry is late, not
the work.

The module itself is careful. The state-only boundary is structural — no import of `backtest.py`
or `strategies.py`, and the docstring says it must never gain one. It routes through `s1.py` after
`477dee3`, so the `'N'` encoding reads correctly. And the finding it was written to produce is real:
**one-hot session dummies dominate a standardized Euclidean KMeans**, recovering "which session" at
100/100/100 percent instead of a flow distinction. That was found by running it, not assumed.

- [x] **`scikit-learn` was never a dependency** — `f7e411e`. `regimes.py` imports `KMeans`,
      `StandardScaler` and `silhouette_score` at module level; scikit-learn was in neither
      `pyproject.toml` nor `uv.lock` nor the venv, so the script died on the import on this machine.
      The docstring's "all already used elsewhere in this directory" was true of matplotlib, numpy,
      pandas and pyarrow and false of the one that matters. Added with `joblib`, `scipy`,
      `threadpoolctl` and `narwhals` as transitives, in its own commit per the standing rule.
- [x] **The walk-forward split cut on the wrong date** — `dcbde04`. It read
      `feat.index.tz_convert(ET).date`, but a Globex session runs 18:00 → 17:00 ET, so 18:00–23:59
      already belongs to the *next* session. Calendar-dating it hands **72 five-minute bars** of the
      split session to the set KMeans fits its boundaries on. **The committed run is unaffected —
      its split date, 2026-07-19, is a Sunday**, so both rules select the same 3,516 bars and the
      labels do not move. Verified against the committed labels CSV rather than assumed. Any weekday
      split would have leaked. The frame already carried the `session` column every other feature
      groups by; it now uses it.
- [x] **Lint, types and tests** — `dcbde04`. 2 `ruff` errors and 9 `mypy` errors on arrival, against
      a directory that was otherwise clean. Added `tests/test_regimes.py`, 24 tests; **58 pass**
      across the service, `ruff` and `mypy` clean over all 16 files. The two tests that matter assert
      the session split and that **no feature can see a later bar** — truncate the frame and every
      surviving row must be identical, which is the leakage rule as an executable claim rather than
      a docstring promise.
- [ ] **The committed Stage 2 outputs cannot be reproduced here, and were not.** `data/` in this
      working copy holds `fixtures/` and nothing else — no `gc_trades.parquet`, no `nq_trades.parquet`,
      no `data/raw/`. That is the same fact `daily_updates/2026-08-26.md` already carries as an ask,
      with a new consequence: **every number in `analysis/regimes/` is currently unverifiable by
      anyone but Prathamesh.** `regimes.py` was smoke-tested end to end against the S1 fixture
      instead (77,532 trades → 276 bars at 5min, k=3, plot and JSON written).
- [x] **✅ The persistence problem was half a defect — `d3c896f`.** The features barely move
      (lag-1 autocorrelation 0.83–0.96) while the label flipped on 28.9% of bars, so the fault was
      never in the market. **`window_features` let a trailing window straddle the session CVD reset**,
      and since `cvd` restarts at ~0 each session, such a window reads the reset as a move: the eight
      largest `cvd_slope` values in July 2026 all sit at `bar_in_session` 2–8 and read **positive, up
      to +505, on bars whose CVD was negative**. Median `|cvd_slope|` 5.8× higher there than on clean
      bars. Only 253 bars (4.0%) — but they were the month's extremes, so after `StandardScaler` they
      pulled a centre and destabilised assignment everywhere. **Median run 2 → 4 bars, flips 29.1% →
      13.7%, silhouette 0.256 → 0.305.**
- [x] **✅ …and it closed the `k` question. 🔴 Correcting the bullet below and this morning's review:**
      the silhouette that appeared to prefer k=2 was substantially that bug. With the straddling bars
      out, **k=3 beats k=2 on every measure — silhouette 0.305 vs 0.247, median run 4 bars vs 2.**
      The committed run's k=3 was right for a reason nobody had.
- [x] **✅ The dwell penalty is in, at λ=0.5 — `83165d8`.** `--dwell-lambda` charges a cost for
      changing regime between adjacent bars, **forward pass only**, so bar *t* is decided from bars
      ≤ *t* and the labels stay usable live. A full Viterbi decode is stickier and is deliberately
      not used — it reads bars after *t*, which is the one thing this module exists not to do;
      `test_the_labels_are_causal` pins that, and **the test discriminates** (a Viterbi
      implementation fails it). The running cost **restarts each session**: carried across the
      overnight halt it suppressed real session-to-session change rather than noise (label changed
      across a boundary 4.5% of the time against plain KMeans's 45.5%). `λ=0.0` reproduces plain
      KMeans exactly, so the old behaviour is one flag away and testable against. `regimes.py` now
      also **reports persistence next to every run** — median run, longest, flip rate — and records
      it in `regime_definitions.json`. 70 tests, `ruff`/`mypy` clean.

      | λ | median run | flips | silhouette | 30min survival |
      | ---: | ---: | ---: | ---: | ---: |
      | 0.0 | 4 bars | 13.7% | 0.305 | 46.2% |
      | **0.5** | **7 bars** | **9.5%** | **0.290** | **54.0%** |
      | 1.0 | 9 bars | 7.9% | 0.270 | 59.0% |

      *Two things it does not claim.* The silhouette from `silhouette_preview` describes the
      **clustering**, not the emitted labels — at λ > 0 the labels are deliberately less separated,
      and the docstring says so. And **no λ rescues the 30-minute horizon.**
- [ ] **One small Stage 2 decision nobody has taken out loud: should
      `--no-session-phase-in-clustering` be the default?** Every run that matters has passed it, and
      the reason it exists is a *finding* — session one-hots at {0,1} separate at distance √2 after
      standardization and make KMeans recover "which session" — not a preference. But flipping the
      default is a §6.2 change to the definitions, so it stays an explicit flag until it is said out
      loud. Two minutes at Wednesday's standup.
- [ ] **⏭ The horizon question is the one still open, and it is not about clustering.**
      Measured against `backtest.py`'s `HORIZONS = (5, 15, 30)` minutes, the share of entries whose
      regime **survives the trade** is now **90.3% / 73.6% / 54.0%** at λ=0.5. Even at λ=1.0 the
      thirty-minute figure only reaches 59.0% — **more than four entries in ten finish in a different
      regime than the one that selected them**, and no setting of λ fixes that without dissolving the
      clusters into the smoothing. **Stage 2 is defensible at the 5-minute horizon, arguable at 15,
      and thin at 30.** That is an argument about which horizon Stage 1's kill gate is judged on, and
      it wants settling **before `select.py` exists** rather than after. *(The residual flipping is
      not noise, for what it is worth: flips concentrate near the cluster boundary — median relative
      margin 0.298 against 0.440 for bars that held — but only 11.7% of bars sit within 10% of tied.
      It is KMeans being asked for a hard label on a space with no gaps in it.)*
- [x] **✅ Two of the five features were the same feature — closed by `871690f`, below.**
      `cvd_persistence` and `cvd_efficiency_specced` correlated at **r = 0.803** on the committed
      labels — both are `abs(CVD)` over a denominator — which double-weighted CVD directionality in a
      Euclidean KMeans, and was exactly the axis regime 2 separated on (standardized centres 1.27 and
      1.19). This measurement *is* the argument the efficiency decision was made on; the two bullets
      are one item.
- [x] **✅ The efficiency ambiguity is closed — `871690f`.** §2 defines directional efficiency as
      `abs(CVD)/range`; the 0.90 cited as validating it came from `abs(close-open)/range` on price
      alone. Prathamesh computed both rather than guess, which was right, and the file's own
      `KNOWN_SPEC_AMBIGUITY` said not to pre-commit definitions built on either until it was resolved —
      **`70b5ac4` pre-committed definitions built on both.** *(The §6.2 artefact was premature, not
      wrong.)* **Varad's call, 26 Aug: keep the price ratio, drop the spec's formula.** It is the
      Kaufman efficiency ratio, dimensionless and bounded in [0, 1]; `abs(CVD)/range` divides
      contracts by dollars, is unbounded, and its honest order-flow counterpart —
      `abs(sum delta)/sum(abs delta)` — was already in the feature set as `cvd_persistence`, which is
      what the r = 0.803 was. **Five features become four**, and `price_efficiency_asused` became
      `price_efficiency` — the suffix only ever named a contrast. `regime_definitions.json` now
      carries `spec_deviation` (the resolution) in place of `known_spec_ambiguity` (the open
      question). Verified end to end on the S1 fixture; 61 tests, `ruff`/`mypy` clean.
- [ ] **⏭ `analysis/regimes/` is now stale and must be regenerated — Prathamesh's, since only he has
      the month.** Its cluster centres, scaler and `regime_summary` are all five-dimensional, and the
      labels themselves move under four features. **Not deleted:** those files are the §6.2
      pre-commitment and quietly rewriting them is the thing §6.2 exists to prevent, so
      [`analysis/regimes/README.md`](../services/signal-data/analysis/regimes/README.md) marks them
      superseded and carries the exact re-run command. Two things to settle while re-running: the
      `k=3`-vs-silhouette question below, and whether these are regimes at all.
- [x] ~~**The silhouette preferred k=2 and the committed run is k=3.**~~ **Resolved — see the two
      bullets above.** It *was* an artefact after all, just not of the month: of the straddling-window
      bug. The reason still belongs in the artefact under §6.2, and now there is one to write down.

### Day 5 — 2026-08-27 · which horizon the kill gate is judged on · [`daily_updates/2026-08-27.md`](../daily_updates/2026-08-27.md)

The question Day 4 refused to answer with a smoother. `horizon.py` (177 lines) measures what each of
`backtest.py`'s `HORIZONS` could *prove*, taking no threshold and reading no strategy — §6.1 intact,
Part B still empty, no backtest run.

**GC July 2026 is a random walk at 5, 15 and 30 minutes, and two independent measurements say so.**
Dispersion grows as √h to within 0.1% (σ = 34.53 / 59.86 / 84.68 ticks), and the overlap correlation
between adjacent bars' legs lands at 0.659 and 0.831 against a random walk's predicted (h−5)/h =
0.667 and 0.833. Neither was fitted to the other. A longer horizon therefore buys variance at exactly
the rate that makes an edge harder to prove and returns no structure for it: **judged at 30 minutes,
Stage 1 needs an edge 2.45× larger in ticks than at 5 to reach the same significance.**

- [x] **The month's bars were already committed and nobody had noticed.**
      `analysis/regimes/regime_labels_window_5min_k3.csv` carries OHLC, delta, volume, cvd and
      session for all 6,276 five-minute bars of July, not just labels. Its *derived* columns are
      stale twice over; OHLC and session are resampled off the ticks and neither `871690f` nor
      `d3c896f` touched them. **This question did not need `data/gc_trades.parquet`.** The next one
      will — 1-minute resolution, and no strategy can be backtested on 5-minute grid entries.
- [x] **A real defect in `backtest.py`, found by the measurement and fixed.** `evaluate` NaN'd a leg
      only when it was *entirely* empty, so a leg the session cut short was reported as a full-horizon
      move — **2.2% of bars at 30m against 0.4% at 5m, every one biased toward zero, at exactly the
      horizon under question.** The fix made the result *cleaner* (σ ÷ √h 0.993 → 1.001 at 30m), which
      is the corroboration worth having; nothing was tuned to produce it. Three tests asserted the old
      behaviour and were rewritten rather than bent. 72 tests, `ruff`/`mypy` clean.
- [x] **Robustness, since one month and one instrument is not much.** Both walk-forward halves scale
      identically (0.992–1.016) while their volatility *levels* differ by 19% — the level moves, the
      exponent does not. The 2026-07-16 session rebuilt at 1-minute resolution through a different
      code path gives 1.000 / 1.011 / 1.019. The 5-minute grid costs 1.1% on σ.
- [ ] **⏭ The decision: judge the kill gate at 5 minutes, 15 and 30 descriptive only.** Not because 5
      is good — because 15 and 30 are not decidable on any data budget this project will have. Stage
      2's regime survival agreed independently (92% / 78% / 54%), and the two arguments are unrelated:
      one is whether a regime outlives the trade it selected, the other whether the tape's noise leaves
      anything to measure. **Not Varad's alone to take** — it changes what Part B's thresholds are
      written against. **Drafted as item 3 of [`plans/team/varad/2026-08-28-gate-note.md`](team/varad/2026-08-28-gate-note.md)
      for Friday's Week 0 gate**, next to the `'N'` amendment and the duplicate-row line — both of
      which were queued for a Wednesday standup that passed without them being put. `contracts.md`
      and `week-00.md` repointed accordingly.
- [ ] **⏭ The uncomfortable half: the kill gate is underpowered at every horizon, 5 included.** At a
      plausible 100–250 signals the smallest separable edge is 8.65–13.68 ticks ($87–$137 a trade);
      a real order-flow edge is one to three. Proving a 3-tick edge at 5m needs **2,081 signals**
      against a month holding 6,253 bars. **§6's recorded prediction of *inconclusive* is confirmed
      quantitatively and is worse than written** — it expected Stage 2's cells to be thin; Stage 1 is
      thin on its own, before any regime split. This is the *more months* argument with a number
      attached at last: at 5 minutes six months puts a 3-tick edge inside reach, **at 30 minutes six
      would not be enough and neither would twelve.**

### Day 6 — 2026-08-28 · the week moves, and the metric was break-even · [`daily_updates/2026-08-28.md`](../daily_updates/2026-08-28.md)

**No code. Two schedule facts and one arithmetic finding**, all in `3f1d158`.

- [x] **Week 1 is 5–11 Sep, not 31 Aug – 4 Sep, and everything downstream shifts one week right.**
      Neither engineer works 29 Aug – 4 Sep. Week 12 ends **27 Nov**. Gates are unchanged in content;
      only their dates moved — which is a week lost deliberately with everyone knowing, and the
      opposite of what `gates.md` warns about. [`plans/team/week-01.md`](team/week-01.md) carries the
      rescheduled week day by day for both engineers and is authoritative on dates until the four
      phase files are rewritten; `plans/team/README.md` says so at the top, because every date in
      them is now a week early.
- [x] **The two lanes are made independent by discharging both seams before the week starts, not
      during it.** Varad in `services/signal-data/`, Prathamesh in `apps/desktop/` — no shared file,
      so a merge conflict is structurally impossible. The S2 type freeze (30 minutes, joint) and the
      regenerated month bar table both move to **Fri 28 Aug**. After tonight the lanes touch in one
      place, the gate room on 11 Sep, and that is a meeting rather than a handoff.
- [x] **`planfortoday.md`'s success metric is the break-even line, not a pass.** For a driftless
      random walk `P(hit +70 before −20) = b/(a+b) = 22.22%`, and break-even at 3.5:1 is
      `1/(1+3.5) = 22.22%` — **the same number, and necessarily so: a fixed target/stop pair on a
      driftless walk always lands exactly on its own break-even.** Day 5 measured this month to *be*
      that walk. Add ~$25 round-turn cost on a $700/$200 pair and break-even is **25.0% exactly** —
      the target as written. Worse, at the 50–150 signals the file plans for, the smallest rate
      separable from that null at 2σ is **34.0% / 29.0%**: a true 25% edge could not be shown on one
      month however real it was. **This is the *more months* argument arriving a third time** — Day 5
      reached it from variance, §6 from cell counts, this from binomial power.
- [ ] **⏭ So the pre-written threshold is a margin over a measured null**, `N ≥ 100`, with
      *inconclusive* kept as a first-class outcome. Drafted wording in `week-01.md` §2. **Varad's to
      commit on Fri 28 Aug, before Part B and before anything runs** — the mechanism is the git
      timestamp and nothing else. `backtest.random_entries` already measures the null; a second one
      must not be written.
- [ ] **⏭ Six corrections to `planfortoday.md` carried into the week** (§5, and the file is now
      tracked so they can be checked against it): Polars → **pandas**, which the service actually
      uses · the regime labels are **stale**, not a done prerequisite · "30 bars" is **150 minutes**
      at 5-minute bars and should be 6 · Part B is derived on the **training half only**, the only
      reading that satisfies both §6.1 and "not guessed" · the month parquet **is** needed, for
      Layers 4–5 · and **`strategy.md` does not exist in this repo** while `phase-1-kill-week.md` and
      `roles.md` both schedule work against it. That phantom should be retired rather than chased;
      `planfortoday.md`'s four conditions are its live replacement.
- [ ] **⏭ The regenerated regime labels are the one thing that can strand Varad for a week.** Every
      one of his seven days reads that CSV, the committed one is stale twice over, and only
      Prathamesh has `data/gc_trades.parquet`. Ten minutes of compute — **and it has to happen Friday,
      not on the 5th.** Land the new run *alongside* the old files, never over them: they are the
      §6.2 pre-commitment. ⚠️ **Same trip: that parquet is still the only copy on any disk** and is
      about to sit through seven unattended days.

### Day 6 (night) — 2026-08-28 · the literature, triaged · [`docs/research/2026-08-28-gold-literature-triage.md`](../docs/research/2026-08-28-gold-literature-triage.md)

**No code. A reading list, and one correction to a number committed earlier the same day.**

- [x] **`Gold Quant Trading Research Papers.pdf` triaged against this repo, not against gold in
      general.** It is an **AI-generated survey, not research**: entry #23's ORB claim rests on a
      studocu bachelor thesis, three citations are Scribd re-uploads, one is a broken viewer URL to a
      price-forecast page, and Pillar 5's headline returns trace to preprints with no described
      out-of-sample discipline. **The 53 URLs on pp.21–23 are the load-bearing part; the tables are a
      lossy index.** Same posture as the version-lock PDF. Verdict per pillar, with pages, is §0 of
      the note.
- [x] **Three things in it are worth acting on.** Realized semivariance (`RS⁺`/`RS⁻`) is a fifth
      Stage 1 candidate computable from the parquet we already own and shaped like the four in
      `strategies.py` · `PMC9759686` is free, peer-reviewed and the only cited paper at our horizon
      (1–15 min) · and **entries clustering on CPI/NFP bars would make a 5-minute edge an event
      artifact** — cheap to check by tagging entries with distance to the nearest release, and worth
      checking *before* Part B is judged, given Day 5 measured the month as a random walk at 5m.
- [x] **The costs paragraph on p.20 is the same finding as this morning's, arriving from a second
      direction.** `backtest.py` reports ticks gross. The correct fix for a threshold-triggered rule
      is to **widen the threshold to cover the round trip**, not to subtract cost at the end — the
      second leaves the entry population unchanged and reports trades that were never worth taking.
      The ~$25 round turn that moved break-even to 25.0% in `daily_updates/2026-08-28.md` is the same
      number and belongs in the entry rule, not the report.
- [x] **The larger finding is what the PDF does not contain: our own literature.** It has five
      pillars and none is market microstructure. `absorption` is **Kyle's lambda** inverted,
      `delta_z` is a coarse **order-flow imbalance**, `absorption_fade` is **flow toxicity / VPIN**,
      `backtest.evaluate` is the **triple-barrier method** with the vertical barrier only, and
      `pull_tbbo_validate.py` is **Lee–Ready** — which means the 99.65% agreement has a published
      comparison set to be judged against. §4 of the note carries the primary sources.
- [ ] **⏭ One live defect, and it corrects a number already committed today.** 30-minute horizons on
      5-minute bars produce **heavily overlapping labels**; those observations are not independent,
      so the **effective N is below the nominal N** and this morning's separable hit rates
      (34.0% / 30.5% / 29.0% at N = 50/100/150) are **optimistic, not conservative**. That is a
      fourth independent argument for more months, and the correction is mechanical — sample
      uniqueness weighting, AFML Ch. 4, with purged-and-embargoed splits (Ch. 7) for the §6.4
      half-split, which currently leaks across its boundary for the same reason. **Not implemented,
      not benchmarked.**
- [ ] **⏭ §4 is cited from knowledge and nothing in it was fetched or verified in-session.** Titles,
      authors and years are search terms. **Verify each DOI before any of it is quoted to Shreyas or
      a vendor**, and do not let a name in that table become a claim about a feature until it has.

### Day 6 (night, later) — 2026-08-28 · the pull that would also have bought NQ

- [x] **`pull_futures_trades.py` had no instrument filter, and the $30 guard does not catch it.**
      `estimate_cost` and the run loop both iterated `INSTRUMENTS.items()` — **GC and NQ** — so the
      six-month pull would have cost **~$83 instead of ~$21**, buying an instrument the project
      dropped on 25 Aug with "the ~$11.42 stays unspent". The per-run guard is $30 and a GC+NQ month
      lands near $14, so it passes the check and the money goes quietly. **The docstring still
      claimed the script always pulls both**, which is what made it look intended.
- [x] **Fixed: `--instrument`, `nargs="+"`, `choices={GC,NQ}`, default `["GC"]`.** +29/−7.
      `estimate_cost` now takes the roots it was asked for rather than every root it knows.
      **72 tests, `ruff` and `mypy` clean, and verified against the live API** — six
      `--estimate-only` calls printed one `GC` line each and **no `NQ` line**, which is the
      behaviour the flag exists for. The billed path is exercised by the pull below, not by this.
- [x] **Six months estimated: $21.12** — Jan $5.51, Feb $3.10, Mar $4.32, Apr $2.73, May $2.65,
      Jun $2.82, against $125 of unspent free credit. **Above the ~$15 the gate note assumed**; the
      heavier months are GC's active-month cycle, not an error. Jan–Jun makes **Jan–Jul contiguous**
      with the month already held.
- [x] **The pull ran. Six months, `exit=0` each, 14,108,072 rows over 131 sessions**, into
      `data/2026-01/` … `data/2026-06/`, 422 MB on disk (112 MB parquet, ~310 MB raw DBN cache).
      Jan 3,531,687 · Feb 2,146,721 · Mar 2,739,204 · Apr 1,958,866 · May 1,721,952 · Jun 2,009,642.
      **With July's 1,616,772 that is 15.7M trades over 154 sessions, Jan–Jul contiguous** — against
      the 22 sessions every power argument today was computed on.
- [x] **`collapse_to_active_contract` survived six real roll cycles, and this is the result that
      mattered.** The symbol sequence is `GCG6 → GCJ6 → GCM6 → GCQ6`, which is GC's Feb/Apr/Jun/Aug
      cycle exactly. **The roll months carry two contracts and the mid-cycle months carry one** —
      Jan `G6`+`J6`, Feb `J6` only, Mar `J6`+`M6`, Apr `M6` only, May `M6`+`Q6`, Jun `Q6` only — and
      each month's closing contract is the next month's opening one, with **no gap, no interleaving
      and no orphan contract anywhere in the chain.** June ends on `GCQ6` and July, pulled a month
      ago on a different machine, is `GCQ6` throughout. That is an independent join.
- [ ] **⏭ `'unknown'` aggressor side is a bigger problem than the pending amendment assumes.** The
      `contracts.md` amendment for `'N'` was drafted against July's **2.34%**. The seven-month range
      is **1.70% – 5.23%** (Jan 5.23%, Mar 5.02%, both of which trip the script's own warning). Those
      rows cannot be signed, so they contribute nothing to delta or CVD — **at 5.23% that is more
      than double the unsigned volume the amendment was written for.** It needs the real range at
      Wednesday's standup, not July's number.
- [ ] **⏭ Six degraded sessions, and only two of them matter.** Databento flagged `2026-01-31`,
      `2026-03-15`, `2026-03-16`, `2026-03-21`, `2026-04-10`, `2026-05-24` as reduced quality. Four
      are Sat/Sun — near-empty or a thin Sunday open. **`2026-03-16` (Mon) and `2026-04-10` (Fri) are
      full sessions**, and `03-15`/`03-16` are one contiguous degraded stretch from the Sunday open
      through Monday. July carried no such flag, so this is a grade of data the validated month never
      had. **Decide whether they are excluded before they enter a backtest, not after.**
- [ ] **⏭ The billed total is unconfirmed.** $21.12 is the sum of six *estimates*; the script prints
      estimates, not charges. Check the Databento portal against $125 of credit.
- [ ] **⏭ A second Databento key is now in a chat transcript.** Same failure as #0, five days later
      and with the first one still open. **Rotate it**, and note that `.env` was written at mode
      `600` and `git check-ignore` confirms `.gitignore:1` covers it — the file is not the leak, the
      transcript is.

### Day 6 (night, last) — 2026-08-28 · twelve more months, and the roll chain holds across all of them · [`analysis/gc_data_manifest.md`](../services/signal-data/analysis/gc_data_manifest.md)

- [x] **Jan–Dec 2025 pulled, `exit=0` each, 30,309,969 rows.** $43.08 estimated; running total
      **$64.20 against $125 of free credit**, ~$61 left. **The local set is now 18 months,
      44,418,041 trades, 396 sessions, Jan 2025 – Jun 2026 contiguous** — against the 22 sessions
      every power argument written this morning was computed on.
- [x] **The roll chain is unbroken across all 17 handoffs, including the year boundary.**
      `GCG5 → GCJ5 → GCM5 → GCQ5 → GCZ5 → GCG6 → GCJ6 → GCM6 → GCQ6`, roll months carrying two
      contracts and mid-cycle months one, every month's closing contract opening the next.
      **`GCZ5` spans four months (Jul–Nov 2025)** — GC's cycle skips V and X, so the long-dated
      December contract is the least-exercised path in `collapse_to_active_contract`, and it held.
- [x] **The backup is done and verified.** All 18 parquets copied to
      `~/Library/Mobile Documents/.../trading-intelligence-data/gc-parquet/`, **351 MB, every file
      `sha256`-matched against source**. Raw DBN (~1 GB) deliberately not copied: it exists only to
      avoid re-billing, and the data is re-purchasable. **`analysis/gc_data_manifest.md` is the
      tracked record** — `data/` is gitignored, so that file is the only committed proof that a
      result came from a particular month's bytes.
- [ ] **⏭ `'unknown'` side is a roll-month artifact, and that is a better problem than a drifting
      one.** Across 18 months the rate is **1.15–5.23%**. Split by month type: **roll months mean
      3.73%, single-contract months 1.92%** — roughly double. The ranges overlap (2025-08 at 3.63%
      and 2026-02 at 3.00% both exceed the roll minimum of 2.68%), so this is a strong tendency, not
      a clean separation. **The plausible mechanism is calendar-spread legs carrying no aggressor
      side**, which is testable and nobody has tested it. What it means for the `contracts.md`
      amendment: `'N'` is not noise to be tolerated at a flat rate — **it concentrates exactly in
      the months where the active contract switches**, so delta is systematically most incomplete
      when the instrument underneath it is changing.
- [ ] **⏭ Aggregate power is now fine; per-cell power is not.** 18 months at 50–150 signals/month is
      ~900–2,700 signals, test half ~450–1,350, which puts the aggregate separable rate at
      **24.5–26.1%**. But split across 4 strategies × 3 regimes that is **37–112 signals per cell**,
      and at the pessimistic end a single cell's own separable rate is **~36%**. **The kill gate is
      now decidable and the selector still is not.** That is a different sentence from this
      morning's and it should be said out loud on 11 Sep.
- [ ] **⏭ Three degraded sessions in 2025** — `2025-09-17` (Wed), `2025-09-24` (Wed), `2025-11-28`
      (Fri, the half session after Thanksgiving). Far fewer than 2026's six. Same decision as those:
      ruled in or out before they enter a backtest.
- [x] **July 2026 pulled here, and it reproduced exactly.** **1,616,772 rows and a 48.32 / 47.79
      aggressor split** — identical to the 24 Aug pull on Prathamesh's machine, four days later on
      different hardware. 23 sessions. **The local set is now 19 months, 46,034,813 trades, 419
      sessions, Jan 2025 – Jul 2026 contiguous**, and the chain extends to `… GCM6 → GCQ6 → GCZ6`.
- [x] **`contracts.md`'s `'N'` wording fixed — the defect was the generalisation, not the figure.**
      Its **2.34% / 1,811 trades** is correct *for the S1 fixture*: one session, 2026-07-16, 77,532
      rows. The drafted amendment then generalised it to "~2.3% of trades", **and that is false at
      month scale — the full July month is 3.89%.** Worse for the amendment
      and better for the theory: July is itself a roll month (`GCQ6`→`GCZ6`), and 3.89% lands on the
      roll-month mean of 3.75% — **an out-of-sample confirmation, since July was not in the 18
      months that produced that statistic.** The amendment needs a month-scale figure and a
      roll/non-roll split. Wednesday's standup.
- [x] **All 19 parquets backed up and `sha256`-verified**, 364 MB in iCloud. Manifest regenerated.
- [ ] **⏭ The iCloud upload is copied but not confirmed landed.** `brctl` reports nothing usable and
      there are no `.icloud` placeholders. Until Finder shows the upload complete, 351 MB sits on the
      same `disk3s5` as the original. **Eyeball it before the lid closes.**

### Gap — 2026-09-02 · three of the four Friday prep items, done three days into the gap · [`daily_updates/2026-09-02.md`](../daily_updates/2026-09-02.md)

**Not a Week 1 day.** 5–11 Sep is still the plan; this is Claude picking up part of Prathamesh's
28 Aug prep list from `week-01.md` §1, which had not actually been started. **The Week 0 gate itself
did not happen** — the S1 `'N'` amendment is still an unvoted proposal, the Anthropic key is still
live, Part B is still empty, and no human checked Firefox, took the Tauri screenshot, sent the vendor
emails, or booked the CA call. None of that is closed by anything below.

- [x] **`analysis/regimes_2026-09-02/` regenerated** — the four-feature, straddle-fixed rerun that
      `week-01.md` D1 needs and calls "the hard blocker." Landed under a new directory, `analysis/
      regimes/` untouched, per §6.2. Split 15.4% / 21.5% / 63.0% across 3 regimes, median run 7 bars
      (35 min), 9.5% flip rate. **Not reviewed against the plot by a second person** — that's still
      Varad's/the room's call, including whether to promote it over the stale directory.
- [x] **`export_fixture_json.py` written and run** — `apps/desktop/public/fixtures/
      gc_ticks_1session.json`, 77,532 raw ticks, 4.8 MB, fetchable by `engine/mock.ts` on W1D2.
      Deliberately left `aggressor_side` as `'B'/'A'/'N'` rather than mapping it into S2's `Side`
      type — that mapping is mock.ts's decision, not this script's.
- [x] **Fresh-clone check re-run** — scratch clone, `pnpm install` → `pnpm build:all` (3/3 projects
      clean) → `cargo build` (clean, 38s cold). `pytest`: 72/72. Nothing regressed since 28 Aug.
- [x] **`FeedCreds` checked, not changed** — already defined in `types.ts` (`10ed7c5`, 25 Aug) as a
      `{ vendor: string; [field]: string }` bag. The file's own comment says "left open," which reads
      as a contradiction until you notice it means *no vendor-specific fields pinned yet*, not
      *undefined*. Good enough to freeze; no edit made.
- [ ] **Not touched, deliberately:** the S1 vote, the Anthropic key, and `thresholds_selector.md`
      Part B. A prior Claude session already declined to fill Part B in — "a threshold picked by an
      assistant is not a commitment by the person with the bias" — and that reasoning held here too.

### Day 7 (pre-week check) — 2026-09-03 · CA and data-sourcing move off-tracker; Week 1 readiness confirmed · [`daily_updates/2026-09-03.md`](../daily_updates/2026-09-03.md)

- [x] **CA calls are off this tracker, by decision, not by resolution.** Handled manually and
      directly by Prathamesh going forward; not reported back for logging. Was reading as an open
      blocker since the 2 Sep gap entry — it is not one to chase.
- [x] **Data acquisition is being scaled via outsourcing**, addressing Day 6's power-analysis
      finding directly (per-regime cells thin at 37–112 signals even across 19 months). The
      mechanics that finding surfaced — roll-chain integrity, degraded-session calls, checksum
      backup — still apply to whatever arrives.
- [x] **Prathamesh's Week 1 lane confirmed clear against `week-01.md` §4's own dependency table** —
      all three pre-week items (`types.ts`+`FeedCreds`, the regenerated bar table, the fixture
      JSON) landed before today. D1 reads only `types.ts`. Nothing blocks starting Sat 5 Sep.
- [ ] **Varad's lane confirmed clear only through D2.** D3 onward (`signals/engine.py`, every
      D4–D6 backtest) is gated on Part B, still open as of today. Not a tooling gap — two prior
      Claude sessions already declined to author it, on the file's own stated reasoning. Needs to
      land before D3 (Mon 7 Sep) or two of his seven days go idle.
- [ ] **New gap, from today's own C1 decision:** D5's 30-minute live-feed hold is now an Ironbeam
      connection, and nobody has an Ironbeam account or API credentials yet. Not tracked as
      anyone's prep item before now. Needed before Wed 9 Sep.

### W1D1 — pulled forward to 2026-09-03 · the overlay skeleton · [`daily_updates/2026-09-03.md`](../daily_updates/2026-09-03.md)

Scheduled Sat 5 Sep, done two days early on the readiness finding above. **D1's number, all three
parts:** six views render · zero console errors · geometry matching `tauri.conf.json` to the pixel.

- [x] **The window is the overlay shell — 380×820, transparent, borderless, always-on-top.**
      Geometry confirmed by the accessibility API at **380×820 at (545, 37)**, and it read the same
      on all six captures. The home screenshot keeps the desktop in frame on purpose: no titlebar,
      the window behind stays behind, and **the desktop shows through outside the rounded corners**,
      which is what proves `transparent: true` took effect rather than degrading silently.
- [x] **All six views render at 380px** — home, analyze, rules, strategy-review, strategy-change,
      journal. Nothing clips or reflows at a width the UI was built 412 for.
- [x] **"Zero console errors" stopped being an unverifiable claim.** This morning's entry recorded
      that a `WKWebView` doesn't reliably forward `console.error` to the terminal, so a clean log
      proved nothing. `src/lib/webviewLog.ts` + a `log_webview` Rust command now forward
      `console.error`/`warn`, uncaught errors and unhandled rejections to stderr — **and the bridge
      was proved to discriminate** with a temporary probe before being trusted. Across the whole
      run those three probe lines are the only `[webview:*]` lines in the log.
      *Honest deduction:* Vite 8's dev client also forwards `console.error`, so the terminal was
      less blind in `tauri dev` than assumed — the bridge's real value is that it holds in a
      **built** app, and that it catches `unhandledrejection`, which Vite's does not.
- [x] **`macos-private-api` is a required Cargo feature, not a nicety** — without it the build
      fails loudly instead of shipping a silently-opaque window. `shadow: false` too: a system
      shadow draws a square outline around a rounded transparent window.
- [ ] **Navigation by clicking is unexercised, and dragging with it.** Accessibility permission is
      still ungranted (`osascript` → `-25208`), so the five non-home views were reached by
      temporarily setting the initial view and reloading, not by clicking tiles. **Each view is
      proved to render; the tiles, the back button and the topbar drag region are not proved to
      work.** Granting Accessibility closes both — and D3 will want it anyway.
- [ ] **`apps/desktop` and `apps/extension` have genuinely diverged.** `theme.css` and
      `SidePanel.tsx` were byte-identical copies since 24 Aug; the overlay changes are desktop-only.
      The extension is unaffected (`body.standalone` never applies there) and builds green, but the
      identical-copy property is spent — which was always going to happen the day the desktop app
      became an overlay.

---

## Next

Ordered. Days 1–3 are complete except the items explicitly left unchecked above — now just
reloading the extension. That is #8 below (#6, the S1 fixture cut, and #7, the real Tauri
window, both closed on 25 Aug), not optional, and it is the same shape as the two that closed:
code that type-checks and tests green but has never been run for real.

**#1 is no longer one of them.** The first live analysis was the fourth item on that list
until 25 Aug, when the backend question was closed by deciding to build our own model. It is
not blocked-and-waiting; it is off this list until that model exists.

| # | Item | Owner | Notes |
| :--- | :--- | :--- | :--- |
| 0 | 🔑 **Revoke the Anthropic key** | Varad | It was in the tracked `.env.example` (uncommitted, absent from history, placeholder restored) **and in a chat transcript.** Ten minutes, at console.anthropic.com. *Revoke*, not rotate: the own-model decision means nothing depends on it and there is no replacement to issue, so this got easier — the suite stays green on a placeholder because the tests only need the key **present**, not valid |
| 1 | ~~Pick the analysis backend, then run the live analysis once~~ — **PARKED 25 Aug: we build our own model** | Varad | No hosted backend is bought, so no live analysis runs and the 5 `LIVE_API_TESTS=1` tests stay skipped. Claude stays in as the interim implementation; the four-key contract stays frozen, so the own model is a drop-in behind the same `analyze()` — the Day 3 lexicon→Claude swap already proved that seam holds. **Scoped 25 Aug — and it does not need a week.** The "own model" turned out not to be a replacement for `analyze()` at all: it is a **GC strategy selector**, and it is a *personal research tool*, not a product feature. Design in [`docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md`](../docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md). It takes no week from `plans/team/`, so the "unscheduled model eats Week 6" risk is closed by the thing not being scheduled rather than by scheduling it. **`analyze()` keeps Claude as its interim implementation and stays `503` indefinitely** — that is unchanged and still unverified end to end. **Stage 1's machinery landed the night of 25 Aug** — `s1.py`, `backtest.py`, 16 tests, and a 3.12-pinned environment for `services/signal-data`, which had none. **Still not started: any actual backtest.** `thresholds_selector.md` now exists with §6.1's Part A binding, but **Parts B and C are empty and only Varad can fill them** — the candidate strategies are his to author (§9 Q1), and a threshold picked by an assistant is not a commitment by the person with the bias. One session cannot support §6 regardless; the full month is still only on Prathamesh's disk. **Stage 1's candidates landed 26 Aug** — `strategies.py`, 191 lines, four features and four entry-only rules, 27 tests green. **No threshold in it has a default**, so §6.1 is enforced by the function signature: the file raises `TypeError` (and fails `mypy`) until Part B exists. The four rules are now shaped functions to be *corrected* rather than blank blocks to be *authored*, which is a smaller ask — but Part B is still the only thing between here and a first backtest |
| 2 | ~~Click the demo through in **Firefox**~~ — **reported done, ~28 Aug or before** | Either | Prathamesh reports capture verified end-to-end in both a real Chrome profile and a real Firefox profile with the rebuilt (`955b374`) extension. **Not contemporaneously logged** — no daily update, commit, or screenshot from the time records it, so this row is closed on his account rather than on independent evidence. If that evidence turns up (a screenshot, a `daily_updates` entry) it should still get linked here |
| 3 | Review the **popup UI** | Prathamesh | Written from scratch to unbreak the build — a starting point, not a design |
| 4 | Decide **where the API lives** | Both | Popup hardcodes `http://localhost:8000`, matching `host_permissions`; a deployed URL changes both, and the CORS entries start mattering once `host_permissions` no longer covers the host. **Now also a secrets question:** the API holds an Anthropic key, so it needs somewhere that can hold an env var — and the key must never move into the extension, which is public |
| 5 | **AMO / Web Store** submission prep | Undecided | See constraints below |
| 6 | ~~Run the Databento pull for real~~ — **DONE 24 Aug, `8aece67`** | Prathamesh | 1,616,772 GC trades, $2.52, aggressor split 48.32/47.79 — inside the band. Exceeded the bar this row set. ~~**What's left: the S1 fixture cut — and it is blocked.**~~ **DONE 25 Aug, `14f5547`.** Blocked in the morning (the month lived only on Prathamesh's disk) and closed the same evening — he cut the session with `cut_s1_fixture.py` and pushed the fixture rather than the month, landing on the one path the `.gitignore` exception carved out hours earlier. **Verified independently after pulling:** 77,532 rows exactly, all six S1 columns with correct dtypes and no extras, `GCQ6` only, CME session window, and **session delta +1,842 — matching `DELTA_CVD_FINDINGS.md` §3 to the unit**, which is a number computed by a different script on a different machine. **Two things came out of it:** `aggressor_side` carries a real third value `'N'` (1,811 trades, 2.34%) that S1 does not admit — **a pending amendment, drafted in `contracts.md`, needs all three at Wednesday's standup** — and the fixture holds 421 genuine duplicate rows where `drop_duplicates()` would shift session delta by **8%**. Both recorded in S1. NQ dropped 25 Aug — the ~$11.42 stays unspent |
| 7 | ~~Confirm `pnpm tauri dev` opens a real window~~ — **DONE 25 Aug, pixels confirmed 3 Sep** | Varad | Ran on-device. Warm `cargo` rebuild in **4.27s**, vite on `:1420`, `target/debug/desktop` running. **Evidence, not a screenshot of a bundle:** the accessibility API reports the process owning **one window, title `Trading Intelligence`, 460×820 at (610, 80)** — the geometry is `tauri.conf.json`'s `width`/`height` to the pixel, so the config is what produced the window; and Launch Services lists it `Foreground` with `desktop Networking` (`com.apple.WebKit.Networking`) and `desktop Graphics and Media` (`com.apple.WebKit.GPU`) as children, which exist only when a real `WKWebView` is instantiated. **The pixel gap closed 3 Sep** ([`daily_updates/2026-09-03.md`](../daily_updates/2026-09-03.md)): Screen Recording permission granted, `screencapture -x` on a real launch shows the summary view rendered correctly — header, strategy card, stats, five action tiles, nothing blank or broken. Window bounds back-calculate to ~460×820pt at 2x, matching the accessibility-API number independently. **Still not claimed:** the other five views (only the home view was checked) and console errors (no devtools was attached; the terminal log is clean but a WKWebView doesn't reliably forward `console.error` to it). Reviewing the UI is #3 and stays open |
| 8 | ~~Load the rebuilt extension in Chrome, confirm capture still works~~ — **reported done, ~28 Aug or before** | Either | See row #2 — same report, same caveat: closed on Prathamesh's account, not on a logged artifact from the time |
| A1 | Compute delta and CVD ~~from the tick data~~ **done** · ~~validate against a real footprint chart~~ — **SUBSTANTIALLY CLOSED 24 Aug, `c504e50`** | Prathamesh | Closed by an independent *method* rather than an independent platform, which sidesteps the Windows-only blocker entirely: `pull_tbbo_validate.py` reclassifies every trade in the 2026-07-16 session by the **quote rule** (price vs the bid/ask immediately before the trade), using the `side` field not at all. **99.65% agreement with `SIDE_MAP` across 75,578 comparable trades**, a near-symmetric confusion matrix (96 vs 165), **0 of 23 hours disagreeing in sign**, and a footprint cross-check at 980/980 common price levels with volume r=1.0000 and delta r=0.9870. Separately `verify_settlement_close.py` resolved the 12.2-point gap against TradingView's reported close as settlement-window-vs-last-trade, VWAP matching within 0.25 — that one **is** an external reference, so contract and timezone are checked too. **Residual, and it must be carried downstream:** session-total delta is method-dependent at the ~15–20% level (side field +1,842 vs quote rule +2,216). **Direction and shape are robust; absolute magnitude needs an error bar.** *(`DELTA_CVD_FINDINGS.md` §3 rewritten 25 Aug — it now records the gate as closed, carries the residual as the file's headline number, and inverts the debugging order so the aggressor mapping is checked **last**, since it has four independent confirmations)* |
| A2 | ~~Pull spot XAUUSD, compute GC-vs-spot correlation and basis distribution~~ — **CUT 25 Aug** | — | Killed by the artifact's Fact Two, not deprioritised. It was scoping MT5 spot gold as a launch instrument; spot gold has no centralised volume — which is exactly why `real_volume` comes back empty — so there is no delta to compute and nothing to correlate against. Returns in the Week 12 quarter-two discussion as a **context-only** mode: rules, journal and capture work on MT5, delta does not, and we never claim it does. *(`DELTA_CVD_FINDINGS.md` §4 said "blocked on Dukascopy being unreachable" — true, and the wrong reason. Rewritten 25 Aug to lead with the real one: the blocker was never the download, it is that spot gold cannot carry the product's core number, so **nobody needs to find a working mirror**.)* |
| C1 | 🚚 **Feed vendor — historical stays Databento, live moves to Ironbeam** | Prathamesh, **decided 3 Sep** | **Supersedes the quantfeed evaluation** — no record in this repo that the 26 Aug quantfeed call happened or what it found; Ironbeam is a separate decision, reported directly, not derived from that call. **Historical/backtest track is unaffected:** the 19-month Databento archive, S1's contract, the quote-rule validation (99.65% agreement) and `contracts.md`'s `'N'` amendment all stand exactly as documented — nothing here is being re-derived on Ironbeam data. **Live feed moves to Ironbeam** (free L1/L2 for non-pro accounts, free API after 5 contracts/month traded, otherwise $249/mo) for both the personal GC-strategy-selector bot and, pending confirmation, the product's live overlay feed (`week-01.md` D5's "hold a live feed 30 minutes" task). **Checked against Ironbeam's own docs, not taken on faith:** the trade stream has an `as` (aggressor side) field, but its value semantics are undocumented (`0` in the example) — **treat it as unvalidated until checked against real data**, the same way Databento's `side` needed `pull_tbbo_validate.py` before it was trusted. **No historical L2/tick data exists via Ironbeam's REST API** — only live streaming — so any book-based backtesting starts from whenever capture begins, which is why keeping the Databento historical archive matters rather than trying to backfill from Ironbeam. **The vendor-licensing question likely changes shape, not just vendor:** Ironbeam is a broker, not a data reseller — if every end user connects through their *own* funded Ironbeam account, that is the same "runs on the user's machine, uses the user's own entitlement" model the product already assumes for MT5 (item B below), which is the model the drafted licence-email question was written to test favourably. **Still not legal advice** — confirm this reading with Ironbeam and the CA in writing before relying on it, same rule as everywhere else licensing comes up in this repo. **Open:** whether the three drafted emails (Databento, Rithmic, Tradovate) still go out as-is, get a fourth (Ironbeam) added, or get replaced — nobody has redrafted them yet |
| B | Make `apps/desktop` behave like a real overlay — transparent, borderless, always-on-top, click-through toggle. Prove it floats over a live MT5 demo and that click-through reaches MT5 underneath | **Prathamesh**, W1D2–W2 | No longer gated on A1/A2 — it is Week 1 Day 2 and Week 2 in [`team/phase-1-kill-week.md`](team/phase-1-kill-week.md). Install the MT5 demo terminal first if nobody has it |
| 9 | 🔌 **Get an Ironbeam account and API credentials** | Prathamesh | Surfaced 3 Sep, checking Week 1 readiness. `week-01.md` D5 has Prathamesh holding a live feed connection 30 minutes in Rust; under today's C1 decision that connection is Ironbeam's, and nobody has an account or credentials yet. Needed before Wed 9 Sep, not that morning |

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
- **CA calls and data-pull scaling are handled outside this tracker, decided 3 Sep.** Compliance
  calls are Prathamesh's own manual track and are not reported back here — don't chase or flag them
  as an open item. Data acquisition is being scaled via outsourcing rather than solely his own
  Databento pulls, to relieve the thin-per-cell power problem Day 6 found; the mechanics that
  finding also surfaced (roll-chain integrity, degraded-session calls, checksum-verified backup)
  still apply to whatever arrives.
