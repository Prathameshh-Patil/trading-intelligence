# Trading Intelligence — Day 1 Team Execution Plan

Current status, teammate responsibilities, integration/testing plan, likely conflicts, and the end-of-day target based on the work completed so far.

---

## 1. What Has Already Been Done

- **Repository**: monorepo with apps, services, packages, tests, docs and configs.
- **Chrome extension**: Vite + React + TypeScript extension loads successfully in Chrome as an unpacked extension.
- **Manifest/content script**: Manifest V3, Chrome storage/runtime APIs, and a content script for selected webpage text are in place.
- **Chrome types**: `@types/chrome` was added and TypeScript is configured for Chrome APIs.
- **Extension build**: `pnpm build` succeeds and generates the extension bundle.
- **Backend**: FastAPI runs on port 8000 with health and database-health endpoints.
- **Analysis endpoint**: `POST /api/v1/analyze` has been tested successfully and returns sentiment, confidence, summary and signals.
- **Web frontend**: `apps/web` exists as a Vite React app and its production build works.
- **Current web issue**: the starter Vite UI was still visible until `App.tsx`/CSS are replaced with the intended custom Trading Intelligence UI.

---

## 2. What Your Other Teammate Should Do Now

| Priority | Teammate task | Expected output |
|:---|:---|:---|
| P0 | Verify the FastAPI analysis contract and endpoint | Stable request/response shape, documented and tested |
| P0 | Test the backend independently with curl/Postman. | Known-good response for sample financial text. |
| P0 | Finish the backend analysis service if assigned. | Real analysis path replacing temporary mock when ready. |
| P1 | Confirm CORS/API configuration. | Web/extension clients can call the API. |
| P1 | Check database/migrations if assigned. | Migration and DB health check pass. |
| P1 | Add validation/error handling. | Bad requests return clean errors instead of crashes. |
| P2 | Document integration. | Endpoint URL, payload, response schema and env variables. |

---

## 3. What You Should Do

- Finish the web product UI: replace the Vite starter screen with the Trading Intelligence landing/product page.
- Connect extension → API: replace the temporary mock analysis with a POST request to `/api/v1/analyze`.
- Test the vertical slice: webpage → selection → extension → FastAPI → analysis → extension.
- Prepare deployment: build the website/extension and decide hosting for the public website and API.
- Keep commits focused: separate web UI, extension integration and unrelated fixes to reduce merge conflicts.

---

## 4. Integration Flow

```
Browser webpage → Chrome content script → selected text + URL + title → extension React UI → FastAPI /api/v1/analyze → sentiment/confidence/summary/signals → extension displays result
```

The web frontend is the public-facing product/marketing experience; it is separate from the extension.

---

## 5. Likely Conflicts

- **Same files**: avoid both people editing the same `App.tsx`, `package.json` or config simultaneously.
- **API contract mismatch**: request/response field names must be agreed before integration.
- **Port/environment mismatch**: local `127.0.0.1:8000` versus a deployed API URL.
- **CORS**: curl can work while browser requests fail.
- **Manifest/build mismatch**: source can be correct while `dist` lacks required extension files.
- **pnpm lockfile conflicts**: simultaneous dependency changes can modify `pnpm-lock.yaml`.
- **Secrets**: `.env` should stay local; share only `.env.example`.

---

## 6. How to Tackle Conflicts

1. Pull before starting and check git status.
2. Use separate branches such as `feat/web-ui`, `feat/backend-analysis`, and `feat/extension-api`.
3. Agree on the API contract before integration.
4. Let pnpm generate `pnpm-lock.yaml` changes rather than manually editing it.
5. If a conflict occurs, inspect git status, resolve only conflicting files, then rebuild/test.
6. Do not reset, force-push or overwrite the other person's work without discussion.

---

## 7. Minimum Day 1 Tests

| Test | Pass condition |
|:---|:---|
| Web build | `pnpm build` succeeds in `apps/web`. |
| Extension build | `pnpm build` succeeds in `apps/extension`. |
| Extension loading | Built extension loads from Chrome extensions page. |
| Backend health | `GET /health` returns `status=ok`. |
| DB health | `GET /health/db` returns `database=ok` when DB is running. |
| Analyze API | `POST /api/v1/analyze` returns the agreed schema. |
| Browser integration | Selected text can reach the API and analysis appears in extension. |
| Error case | Empty/invalid input is handled without crashing. |
| Git | All intended work is committed/pushed; no secrets tracked. |

---

## 8. End-of-Day 1 Definition of Done

- **Website**: custom Trading Intelligence UI runs locally and builds cleanly.
- **Extension**: Chrome extension loads from the built `dist`.
- **Selection**: financial text can be selected and passed into the extension.
- **Backend**: FastAPI is reachable and analysis endpoint returns a stable schema.
- **Integration**: extension calls the backend and displays the result.
- **Team**: ownership is clear and the API contract is documented.
- **Git**: clean commits/pushes with no accidental secrets.
- **Demo**: one complete happy-path demo works from webpage selection to result.

---

## 9. The Demo You Should Be Able to Show

Open a financial/news webpage → highlight text such as *"Apple reported stronger than expected earnings"* → open Trading Intelligence → selected text appears → click **Analyze** → FastAPI receives the request → response returns sentiment, confidence, summary and signals → result appears in the extension popup.

---

## 10. Do Not Overreach on Day 1

Do not spend Day 1 trying to publish globally, finish the final ML model, or fully deploy every service. First make the local vertical slice reproducible. Deployment and Chrome Web Store submission can follow once the core flow is solid.
