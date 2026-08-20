# Trading Intelligence — Current Plan

Live tracker: who owns what, what is done, what is next. **Last updated: 2026-08-21.**

## How the two folders work

| Folder | Answers | Cadence |
| :--- | :--- | :--- |
| `plans/` | *What are we doing, who owns it, what is left* | Edited as work is picked up and finished |
| `daily_updates/` | *What happened on a given day, and how it was verified* | One file per day, append-only once the day ends |

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

---

## Next

Ordered. Nothing here is Day 1 scope — Day 1 is complete.

| # | Item | Owner | Notes |
| :--- | :--- | :--- | :--- |
| 1 | Click the demo through in **Firefox** | Either | Installs cleanly and CORS accepts it; only Chrome has rendered a verdict |
| 2 | Review the **popup UI** | Prathamesh | Written from scratch to unbreak the build — a starting point, not a design |
| 3 | Decide **where the API lives** | Both | Popup hardcodes `http://localhost:8000`, matching `host_permissions`; a deployed URL changes both, and the CORS entries start mattering once `host_permissions` no longer covers the host |
| 4 | Replace the **lexicon** with a real model | Varad | Drop-in: `analyze(text)` keeps returning the same four keys |
| 5 | **AMO / Web Store** submission prep | Undecided | See constraints below |

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
- **`.env` stays local.** Only `.env.example` is tracked.
