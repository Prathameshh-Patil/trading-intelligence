# Vision Hub

A desktop order-flow overlay for gold futures, and everything around it: the FastAPI backend
(`services/api`), the customer site (`apps/site`), the admin portal (`apps/admin`), the Tauri
desktop app (`apps/desktop`) and a browser extension (`apps/extension`), in a pnpm workspace.
The two web apps share `packages/contracts` (wire types, the API client) and `packages/ui`
(tokens and primitives). Formerly "Trading Intelligence"; the old name survives in a few
storage keys on purpose.

Dependency versions are locked in `services/api/uv.lock` and `pnpm-lock.yaml`. Those two files
are the source of truth — do not change versions to match a different machine. See
`trading_intelligence_environment_version_lock.pdf` for the full handoff rules.

## Prerequisites

- Python 3.12 (the project rejects 3.13+ via `requires-python`)
- [uv](https://docs.astral.sh/uv/) — the backend package manager, not pip
- Node.js and pnpm 11.22.0 (via corepack)
- Docker with the `compose` plugin, for PostgreSQL 17

## Database

```sh
docker compose up -d
docker ps          # expect container trading-postgres on port 5432
```

## Backend

```sh
cd services/api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

`.env` is required — neither `DATABASE_URL` nor `ANTHROPIC_API_KEY` has a default, so the
app and Alembic both fail fast without it. The Anthropic key is what `/api/v1/analyze` calls
(see [`services/api/README.md`](services/api/README.md)); get one from
<https://console.anthropic.com>. To run the tests it only has to be present, not valid.
Check it worked:

```sh
curl localhost:8000/health              # {"status":"ok",...}
curl localhost:8000/api/v1/health/db    # {"status":"ok","database":"ok"} — proves Postgres is reachable
```

Routers are mounted under `/api/v1`; the bare `/health` above is a separate
liveness check declared directly on the app.

### Auth material, and the first admin

The site and the portal need signing keys and an admin account before anything works:

```sh
cd services/api
uv run python -m app.cli gen-jwt-key            # paste the three lines it prints into .env
uv run python -m app.cli create-admin you@example.com   # prompts for a password, twice
```

`gen-jwt-key` prints `JWT_ACTIVE_KID`, `JWT_KEYS` and `KEY_ENCRYPTION_SECRET`. Restart the
API after editing `.env`. The email validator rejects special-use domains (`.local`, `.test`),
so use a real-looking one even for a local admin.

Check it: `curl localhost:8000/.well-known/jwks.json` shows the active `kid`, and
`curl -X POST localhost:8000/api/v1/keys/validate -H 'X-API-Key: vh_live_x'` answers
`200 {"valid": false, ..., "reason": "unknown"}`.

## The site and the admin portal

Both are Next.js static exports that talk to the API over `NEXT_PUBLIC_API_BASE`, baked in at
build time.

```sh
pnpm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 NEXT_PUBLIC_ADMIN_URL=http://127.0.0.1:3001 pnpm dev:site    # http://localhost:3000
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 pnpm dev:admin                                             # open http://127.0.0.1:3001
```

**Open the portal at `127.0.0.1`, not `localhost`.** Browsers scope cookies by host, not by
port, so `localhost:3000` and `localhost:3001` would share one refresh cookie and signing in to
one would sign in the other. `127.0.0.1` is a different host with its own cookie jar, and
same-site with `127.0.0.1:8000` so the refresh cookie still travels. `apps/admin/next.config.ts`
lists it under `allowedDevOrigins` for this reason.

The flow, end to end: sign up on the site → `/account` shows *Awaiting approval* → the user
appears on the portal's *Approvals* without a reload → *Approve* mints `vh_live_…` → the site
tab shows the key live → paste it into the desktop app's Licence screen → the account page's
last step flips to *Activated in the app*.

`pnpm build:site` and `pnpm build:admin` emit `out/` for Cloudflare Pages or any static host.

## Desktop

```sh
cp apps/desktop/.env.example apps/desktop/.env    # VITE_API_BASE, VITE_SITE_URL
pnpm dev:desktop                                  # Tauri; needs Rust
```

The app opens on its Licence screen until a valid `vh_live_` key is pasted; the key goes to
the OS keychain and nowhere else. `VITE_API_BASE=http://localhost:8000 pnpm --filter desktop
dev` runs the same UI as a plain page, with the key held in memory.

## Extension

The overlay in browser form: a floating panel on TradingView, cTrader Web and the MT5 web
terminal, gated by the same licence key as the desktop app, fed by the same API. Chrome and
Firefox, Manifest V3. `apps/extension/dist` (Chrome) and `apps/extension/dist-firefox`
(Firefox) are **committed**, so a fresh clone loads either with no build step:

- **Chrome** — `chrome://extensions`, Developer mode on, "Load unpacked", pick
  `apps/extension/dist`.
- **Firefox** — `about:debugging#/runtime/this-firefox`, "Load Temporary Add-on…", pick
  `apps/extension/dist-firefox/manifest.json`.

Then: click the toolbar icon, set the API address under Settings if the build has none baked
in (the committed `dist` does not), paste the `vh_live_…` key from your account page, open a
chart on one of the four hosts. The panel floats top-right; drag it by its header, collapse it
with ▾, and its place is remembered per site. **Sync chart** reads the symbol, timeframe and
last price from the page, on your click only, and shows them in the panel — nothing read from
the page leaves it. Alerts arrive over a WebSocket: *breaking* as a banner, *signal* as a badge
count, *analysis* in the list; each tier's treatment is a setting in the popup.

The `browser_specific_settings.gecko.id` in the manifest is the add-on's permanent identity in
Firefox. Do not regenerate it — changing it after release makes existing installs a different
add-on rather than an update. `public/manifest.json` is the one source; the Firefox copy is
derived by `scripts/firefox-manifest.mjs` at build time.

### If you change anything under `apps/extension/src`

Because both `dist` folders are committed, they can go stale — the repo saying one thing while
the loaded extension does another. Rebuild and commit them in the same commit as the source
change:

```sh
cd apps/extension
pnpm build            # tsc, the popup+worker build, the content-script build, the Firefox manifest
git status            # dist/ and dist-firefox/ should appear — commit them with your src change
```

Vite hashes the asset filenames, so a real source change always shows up in `git status` after
a build. **A clean `git status` after `pnpm build` means `dist` is current**; a dirty one you
did not expect means someone committed source without rebuilding.

`pnpm dev` runs a **harness** at `/dev/harness.html`: a fake chart page with the real service
worker, content panel and popup running in one tab over a `chrome.*` stub, against whatever
API `VITE_API_BASE` names. Everything but "Load unpacked" can be checked there — activation,
drag, chart sync, all three alert tiers (`POST /api/v1/admin/alerts` with an admin token), and
revocation re-gating the panel.

## Project tracking

| Folder | Answers |
| :--- | :--- |
| [`plans/`](plans/current.md) | What we are doing, who owns it, what is left |
| [`daily_updates/`](daily_updates/) | What happened on a given day, and how it was verified |

Any change to the repo updates both: `plans/current.md` moves the item's status, and the
day's file in `daily_updates/` records what was done and what proves it.

## Contributing

Work on a feature branch and open a PR — never push directly to `main`.

```sh
git checkout -b feat/your-change
git commit -m "feat: your change"
git push -u origin feat/your-change
```

Dependency changes are their own PR, with the lockfile diff reviewed. Never commit `.env`,
credentials, or API keys.
