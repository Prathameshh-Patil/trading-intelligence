# Trading Intelligence

FastAPI backend (`services/api`) and a Chrome extension (`apps/extension`) in a pnpm workspace.

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

## Extension

`apps/extension/dist` is **committed**, so a fresh clone can load the extension straight away
with no build step:

```sh
git clone … && cd trading-intelligence
```

The same `dist` loads in both browsers:

- **Chrome** — `chrome://extensions`, Developer mode on, "Load unpacked", pick `dist`.
- **Firefox** — `about:debugging#/runtime/this-firefox`, "Load Temporary Add-on…", pick
  `dist/manifest.json`. Firefox MV3 treats `host_permissions` as opt-in, so if Analyze fails
  with a network error, grant the localhost permission from the add-on's permissions panel.

The `browser_specific_settings.gecko.id` in the manifest is the add-on's permanent identity in
Firefox. Do not regenerate it — changing it after release makes existing installs a different
add-on rather than an update.

### If you change anything under `apps/extension/src`

Because `dist` is committed, it can go stale — the repo saying one thing while the loaded
extension does another. Rebuild and commit it in the same commit as the source change:

```sh
cd apps/extension
pnpm install          # first time only
pnpm build
git status            # dist/ should appear — commit it with your src change
```

Vite hashes the asset filenames, so a real source change always shows up in `git status` after
a build. **A clean `git status` after `pnpm build` means `dist` is current**; a dirty one you
did not expect means someone committed source without rebuilding.

`pnpm dev` runs the popup as a plain web page for faster iteration, and does not touch `dist`.

To use it: highlight text on any page, then open the popup and click **Analyze**. The popup
reads the selection via `activeTab` at the moment you open it — there is no content script and
no standing permission on any site. It posts to `http://localhost:8000`, so the backend above
must be running; Chrome blocks reading the selection on `chrome://` pages, the Web Store and
the PDF viewer.

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
