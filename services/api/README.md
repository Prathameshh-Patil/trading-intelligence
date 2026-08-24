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

Response `200` — illustrative, the wording is model-written and varies between calls:

```json
{
  "sentiment": "bullish",
  "confidence": 88.0,
  "summary": "Apple reported earnings above expectations and the stock reached a record high.",
  "signals": ["Earnings beat expectations",
              "Share price hit a record on the news",
              "Confirm the size of the beat and whether guidance was raised"]
}
```

| Field        | Type            | Notes                                             |
| :----------- | :-------------- | :------------------------------------------------ |
| `sentiment`  | string enum     | `bullish` \| `bearish` \| `neutral` — lowercase   |
| `confidence` | float           | **0–100, a percentage**, not 0–1. The prompt asks for 50–95 and 50 means no usable evidence, but only 0–100 is enforced — see below |
| `summary`    | string          | One-sentence plain-English readout                |
| `signals`    | array of string | Short bullet strings, safe to render directly. The prompt asks for 1–4; only non-empty is enforced |

`url` and `title` are accepted and validated but do not yet affect the result — they are
there so the extension can send them from day one without a later contract change.

### Errors

| Status | When                                                              |
| :----- | :---------------------------------------------------------------- |
| `422`  | `text` missing, empty/whitespace-only, over 20 000 chars, or malformed JSON. Body is FastAPI's standard `{"detail": [...]}`. |
| `503`  | `/api/v1/health/db`, when Postgres is unreachable. `{"detail": {"status": "error", "database": "unreachable", "error": "..."}}` |
| `503`  | `/api/v1/analyze`, when the upstream model call fails or returns nothing that satisfies the schema. `{"detail": {"status": "error", "analysis": "unavailable", "error": "..."}}` |

Clients should treat any non-200 as "analysis unavailable" and show the `detail` text
rather than retrying.

## How the analysis works

`app/analysis.py` sends the selected text to Claude (`claude-haiku-4-5`) with a system
prompt that defines each field, and decodes the reply through a Pydantic schema using
structured outputs. The schema is the enforcement: a malformed or half-written answer
raises here rather than reaching the extension as a wrong-shaped `200`.

**What the schema does and does not enforce.** Field names, types, the required set and
the `sentiment` enum are sent in the JSON schema and are enforced. Numeric bounds and list
maximums are *not* — the SDK strips them and they survive only as a description hint, so
`confidence: 50–95` and `1–4 signals` are things the prompt asks for, not guarantees. This
was verified against the generated schema, not assumed.

`Analysis` is therefore written to the contract, not to the prompt's style: it validates
`confidence` at 0–100 and `signals` as non-empty. Validating the prompt's preferences
instead would turn a perfectly usable answer that came back with `confidence: 97` into a
failed request — `messages.parse` validates client-side, so any bound put on the model
becomes a hard error rather than a correction. Genuinely unusable output (truncated JSON, a
refusal) still fails, and becomes the `503` above.

This replaced the Day 1 lexicon on 25 Aug. That lexicon was a deterministic word-count
with a hand-written negation window; it could not read anything its word lists did not
contain, which is why it was always described as a baseline. The contract did not change
— `analyze(text)` returns the same four keys, which is what made the swap a drop-in.

Two consequences worth knowing:

- **`ANTHROPIC_API_KEY` is required for the service to start.** It is a `Settings` field
  like `DATABASE_URL`, so a missing key fails loudly at startup rather than at the first
  request. Tests only need it present, not valid.
- **Analysis is a network call**, so it can fail and it costs money — roughly $0.0015 per
  request at Haiku 4.5 rates for a typical selection. Failures are a `503`, below.

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
uv run pytest                      # needs .env; the DB test needs `docker compose up -d`
LIVE_API_TESTS=1 uv run pytest     # also runs the 5 live tests — real calls, real cost
uv run ruff check app tests
uv run mypy app
```

`tests/test_api.py` covers the contract at the HTTP boundary: both health checks, the
response shape, whitespace stripping, the validation rejections, the upstream-failure
`503`, and CORS for the Chrome, Firefox and localhost origins plus a foreign one that must
be refused. 17 tests, none of which need a valid key.

Four of them swap the *Anthropic transport* rather than stubbing `analyze`, so the real
request building and response decoding in `app/analysis.py` are exercised: what goes over
the wire (model, system prompt, generated schema), a well-formed reply decoding correctly,
a reply that drifts outside the prompt's style still returning `200`, and a truncated reply
becoming a `503`. Stubbing `analyze` itself would leave `analysis.py` untested entirely.

Whether the model actually *reads sentiment correctly* is a separate claim, and stubs
cannot support it. That lives in 5 live tests (bullish, bearish, neutral, negation, and the
confidence/signal bounds) which skip unless `LIVE_API_TESTS=1` is set, so a normal run never
spends credit. Run them after any change to the system prompt in `app/analysis.py` — that
prompt is the only thing holding the sentiment behaviour in place, and nothing else will
catch a regression in it.
