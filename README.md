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

`.env` is required — `DATABASE_URL` has no default, so the app and Alembic both fail fast
without it. Check it worked:

```sh
curl localhost:8000/health              # {"status":"ok",...}
curl localhost:8000/api/v1/health/db    # {"status":"ok","database":"ok"} — proves Postgres is reachable
```

Routers are mounted under `/api/v1`; the bare `/health` above is a separate
liveness check declared directly on the app.

## Extension

```sh
cd apps/extension
pnpm install
pnpm build
```

The same `dist` loads in both browsers:

- **Chrome** — `chrome://extensions`, Developer mode on, "Load unpacked", pick `dist`.
- **Firefox** — `about:debugging#/runtime/this-firefox`, "Load Temporary Add-on…", pick
  `dist/manifest.json`. Firefox MV3 treats `host_permissions` as opt-in, so if Analyze fails
  with a network error, grant the localhost permission from the add-on's permissions panel.

`pnpm dev` runs the popup as a plain web page for faster iteration.

To use it: highlight text on any page, then open the popup and click **Analyze**. The popup
reads the selection via `activeTab` at the moment you open it — there is no content script and
no standing permission on any site. It posts to `http://localhost:8000`, so the backend above
must be running; Chrome blocks reading the selection on `chrome://` pages, the Web Store and
the PDF viewer.

## Contributing

Work on a feature branch and open a PR — never push directly to `main`.

```sh
git checkout -b feat/your-change
git commit -m "feat: your change"
git push -u origin feat/your-change
```

Dependency changes are their own PR, with the lockfile diff reviewed. Never commit `.env`,
credentials, or API keys.
