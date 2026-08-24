# Trading Intelligence — Current Plan

Live tracker: who owns what, what is done, what is next. **Last updated: 2026-08-25.**

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

| Area | Owner | Notes |
| :--- | :--- | :--- |
| `services/api` — backend, analysis, contract | Varad | Contract is frozen: see `services/api/README.md` |
| `apps/extension` — popup, manifest, browser support | Varad | Popup UI written to unbreak the build; styling needs Prathamesh's eye |
| `apps/web` — landing page | Prathamesh | The page moved here from the extension on 21 Aug |
| Deployment, hosting | Undecided | Blocking a non-local demo |

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
      this one thing is not, and cannot be until the backend question below is settled.
- [ ] **The analysis backend is an open decision again**, deliberately deferred on 25 Aug
      rather than defaulted. Options weighed: add Anthropic credit (~$5 ≈ 3,000 analyses, zero
      further work, code stays exactly as verified); Ollama running locally (free forever, no
      key, no rate limit, and page text never leaves the machine — but it cannot back a deployed
      API); Google Gemini's free tier (no card, closest drop-in, but rate-limited and its
      free-tier data-use terms need reading first). Whichever wins, `analyze()` keeps the same
      four keys, so the route, the contract and the extension are unaffected — that was the
      point of freezing it. **This is really the same question as #4** and should be decided
      with it: a local model removes the secret and rules out a hosted API; a cloud model does
      the reverse.

---

## Next

Ordered. Days 1–3 are complete except the items explicitly left unchecked above — a real
`pnpm tauri dev` window, the actual Databento pull, reloading the extension, and now the
first live analysis call. Those are #1 and #6–#8 below, not optional. Three of the four are
the same shape: code that type-checks and tests green but has never been run for real.

| # | Item | Owner | Notes |
| :--- | :--- | :--- | :--- |
| 1 | **Pick the analysis backend, then run the live analysis once** | Varad | Blocked on a decision, not on work — see the Day 3 notes. Anthropic credit, local Ollama, or Gemini free tier. Decide it together with #4, they are the same question. Once settled: `LIVE_API_TESTS=1 uv run pytest` (5 tests: bullish, bearish, neutral, negation, bounds), then click a real selection through the loaded extension. Until then the model's sentiment judgement is the one unverified thing in the change |
| 2 | Click the demo through in **Firefox** | Either | Installs cleanly and CORS accepts it; only Chrome has rendered a verdict |
| 3 | Review the **popup UI** | Prathamesh | Written from scratch to unbreak the build — a starting point, not a design |
| 4 | Decide **where the API lives** | Both | Popup hardcodes `http://localhost:8000`, matching `host_permissions`; a deployed URL changes both, and the CORS entries start mattering once `host_permissions` no longer covers the host. **Now also a secrets question:** the API holds an Anthropic key, so it needs somewhere that can hold an env var — and the key must never move into the extension, which is public |
| 5 | **AMO / Web Store** submission prep | Undecided | See constraints below |
| 6 | Run the Databento pull for real, confirm the numbers | Prathamesh | `services/signal-data/pull_futures_trades.py --estimate-only` then `--run`; confirm row counts (millions, not thousands), cost, aggressor split (~45–55% either way), and the gap check before trusting the output |
| 7 | Confirm `pnpm tauri dev` opens a real window | Either | Headless-browser screenshot of the compiled bundle isn't the same as a real native window — nobody has looked at one yet |
| 8 | Load the rebuilt extension in Chrome, confirm capture still works | Either | The `activeTab`/`scripting` rewrite (`955b374`) hasn't been checked in a real loaded extension. Fold #1's click-through into this if doing both at once |
| A1 | Compute delta and CVD from the tick data, validate against a real footprint chart | Prathamesh | Depends on #6 landing real parquet files. Validate **one session**, not the whole month, against a free footprint chart (ATAS demo or Sierra Chart trial). Unvalidated delta is worse than no delta — check aggressor-side mapping first if the sign or magnitude looks off |
| A2 | Pull spot XAUUSD for the same month; compute intraday GC-vs-spot correlation and the basis distribution | Varad | Depends on Prathamesh handing over a resampled GC price series (1-min/5-min bars, not the full tick parquet). Needs a separate spot-FX source — `GLBX.MDP3` doesn't carry spot XAUUSD, not yet picked. Deliverable: correlation coefficient **and** basis distribution (not just a mean), plus a v1-scope call. Nobody has published these numbers yet |
| B | Make `apps/desktop` behave like a real overlay — transparent, borderless, always-on-top, click-through toggle. Prove it floats over a live MT5 demo and that click-through reaches MT5 underneath | Both, after A1 + A2 | Bigger than the plain-window proof — budget real focused time. Install the MT5 demo terminal first if neither of you has it |

---

## Standing constraints

Things that are cheap to break and expensive to notice.

- **Python 3.12 only.** `requires-python = ">=3.12,<3.13"` is load-bearing. If a package will
  not resolve, change the package, not the bound.
- **Lockfiles are the source of truth.** `uv.lock` and `pnpm-lock.yaml` — let the tools write
  them, and give dependency changes their own reviewed commit.
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
- **Analysis costs money per request** — roughly $0.0015 a call at Haiku 4.5 rates. Nothing
  rate-limits or caches it yet, so anything that loops over `/api/v1/analyze` spends real
  money. Worth knowing before writing a batch script against it.
- **The system prompt in `app/analysis.py` is the only thing holding sentiment behaviour
  in place.** No type checker and none of the 13 stubbed tests will catch a regression in
  it. Re-run `LIVE_API_TESTS=1 uv run pytest` after editing it.
