# Trading Intelligence API

FastAPI service backing the Chrome extension. Setup (Docker, `uv sync`, migrations,
uvicorn) lives in the [repo README](../../README.md); this file is the API contract.

Base URL in development: `http://localhost:8000`. Interactive docs: `/docs`.

## Endpoints

| Method | Path                 | Purpose                                     |
| :----- | :------------------- | :------------------------------------------ |
| GET    | `/health`            | Liveness. Declared on the app, not the router. |
| GET    | `/api/v1/health/db`  | Readiness — runs `SELECT 1` against Postgres. |
| POST   | `/api/v1/analyze`    | Sentiment analysis of selected page text.    |

## POST /api/v1/analyze

Request:

```json
{
  "text": "Apple reported stronger than expected earnings, shares surged to a record.",
  "url": "https://example.com/aapl",
  "title": "Apple earnings"
}
```

| Field   | Type             | Required | Constraint                                  |
| :------ | :--------------- | :------- | :------------------------------------------ |
| `text`  | string           | yes      | Trimmed, then 1–20 000 characters           |
| `url`   | string \| null   | no       | ≤ 2 048 characters                          |
| `title` | string \| null   | no       | ≤ 512 characters                            |

Response `200`:

```json
{
  "sentiment": "bullish",
  "confidence": 95.0,
  "summary": "5 bullish and 0 bearish terms across 14 words. Lexicon baseline, not a market forecast.",
  "signals": ["Bullish language: growth, record, strong, stronger, surged",
              "Confirm against price and volume before acting"]
}
```

| Field        | Type            | Notes                                             |
| :----------- | :-------------- | :------------------------------------------------ |
| `sentiment`  | string enum     | `bullish` \| `bearish` \| `neutral` — lowercase   |
| `confidence` | float           | **0–100, a percentage**, not 0–1. Never above 95; 50 means no usable evidence |
| `summary`    | string          | One-sentence plain-English readout                |
| `signals`    | array of string | 1–4 short bullet strings, safe to render directly |

`url` and `title` are accepted and validated but do not yet affect the result — they are
there so the extension can send them from day one without a later contract change.

### Errors

| Status | When                                                              |
| :----- | :---------------------------------------------------------------- |
| `422`  | `text` missing, empty/whitespace-only, over 20 000 chars, or malformed JSON. Body is FastAPI's standard `{"detail": [...]}`. |
| `503`  | `/api/v1/health/db` only, when Postgres is unreachable. `{"detail": {"status": "error", "database": "unreachable", "error": "..."}}` |

Clients should treat any non-200 as "analysis unavailable" and show the `detail` text
rather than retrying.

## How the analysis works

`app/analysis.py` — a deterministic finance-word lexicon, no model and no network call.
It counts bullish and bearish terms, flips a term preceded by a negator within three words
("did not beat" reads bearish), and scores confidence from how lopsided the hits are times
how many there are. Deliberately a baseline: the point is a stable contract the extension
can integrate against now. Replacing it with a real model only requires `analyze(text)` to
keep returning the same four keys.

## CORS

`app/main.py` allows these origins via regex — the unpacked extension's id changes on every
reload, so a fixed origin list would break:

| Origin | Who sends it |
| :--- | :--- |
| `chrome-extension://<32 lowercase a–p chars>` | the popup on Chrome |
| `moz-extension://<uuid>` | the popup on Firefox |
| `http://localhost:<port>`, `http://127.0.0.1:<port>` | `apps/web`, and `vite preview` of the popup |

Methods `GET`/`POST`, header `Content-Type`. Credentials are not allowed; the API has no
cookie auth. Anything else is refused at preflight with a `400`, including a malformed
`moz-extension://` UUID.

## Tests

```sh
cd services/api
uv run pytest          # needs .env; the DB test needs `docker compose up -d`
uv run ruff check app tests
uv run mypy app
```

`tests/test_api.py` covers the contract at the HTTP boundary: both health checks, the three
sentiment outcomes, negation, response shape, the validation rejections, and CORS for the
Chrome, Firefox and localhost origins plus a foreign one that must be refused. 15 tests.
