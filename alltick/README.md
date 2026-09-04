# alltick

What the AllTick market-data API actually provides, measured rather than quoted.

AllTick's own docs ship a truncated sample of each product list and a rate-limit table that
doesn't match what the server does. This repo pulls the real catalog, calls every documented
endpoint once with a real token, and records what came back.

**Closed 2026-09-05: the historical track stays Databento.** This directory is the record of
why, kept so the question does not get re-litigated from a blank page. See `plans/current.md`
row C2.

**For the gold order-flow question, read [`GOLD.md`](GOLD.md).** Short version: `GOLD` is a 1 Hz
top-of-book snapshot with a hardcoded aggressor flag — L1 only, no L2, no MBP, no MBO, and no
history for either book or ticks.

## Layout

```
packages/catalog/extract.py   product spreadsheet -> data/catalog.json (11,223 instruments)
packages/probe/client.py      HTTP client; surfaces the undocumented 429 envelope
packages/probe/rest.py        every REST endpoint once  -> data/rest.json
packages/probe/entitlements.py which codes this token can read -> data/entitlements.json
packages/probe/suspension.py  halt/resume feeds -> data/suspension.json
packages/probe/ws.py          WebSocket subscribe + push capture -> data/ws.json
packages/probe/gold.py        GOLD depth + cadence + aggressor measurement -> data/gold.json
packages/probe/pull_klines.py pages candle history backwards, resumable -> data/klines/*.jsonl
packages/edge/ohlcv_edge.py   is there anything OHLCV-only features can find?
data/reference.json           plan limits, error codes, cmd_ids, transcribed from the docs
```

## Run

```sh
echo 'your-token' > .token     # or export ALLTICK_TOKEN
make all                       # ~25 min on the free plan; it is mostly sleeping
make klines                    # ~1.9 h: 5-minute gold back to 2022-06
make edge                      # the test that decides whether any of this is worth buying
```

`make klines` checkpoints after every page and stops at the free plan's daily request
cap with a resume line; re-running the same command picks up where it left off.
`make klines-1m` is the same pull at 1-minute resolution — ~3,070 pages, so about three
days on the free key against roughly an hour on Basic.

Python 3.12, standard library only, except `websockets` for `make stream` and `make gold`.

## What the probes found

- **11,223 instruments** across nine asset classes, from the product spreadsheet. The docs' own
  code lists show a dozen rows per class and point at the sheet for the rest.
- **The free plan is one sample instrument per asset class, not a sample of every instrument.**
  Probing 311 codes, 10 answered: `USDJPY`, `GOLD`, `USOIL`, `HK50`, `BTCUSDT`, `TSLA.US`,
  `700.HK`, `000001.SH`, `399001.SZ`, `.DJI.US`. Everything else returns `604 code unauthorized`.
- **Two hosts, not one.** `quote-b-api` serves forex, metals, energy, CFD indices and crypto;
  `quote-stock-b-api` serves US/HK/A-share equities and market indices. A code sent to the wrong
  one returns `600 code invalid`.
- **Entitlement is per product.** Unauthorised codes are dropped silently from a mixed request;
  only a request where *every* code is unauthorised returns `604`.
- **The free plan's real limit is one request per ten seconds per endpoint**, and exceeding it
  returns HTTP 429 with `{"error_msg": "Too many requests"}` — no `ret`, no `msg`, so a client
  that only reads `ret` sees a malformed success instead of a rate limit.
- **`/static_info` is stock-host only.** On `quote-b-api` it answers HTTP 200 with the plain-text
  body `Unable to find matching target resource method`. There is no reference data for forex,
  metals or crypto.
- **`/kline` caps at 500 candles, and GOLD only has 357 daily bars** (2025-04-21 to 2026-09-04).
  Deeper history means walking `kline_timestamp_end` backwards, which only forex, metals and
  crypto accept.
- **All ten candle intervals work on the forex host.** On equities, 2h and 4h return `ret=200`
  with an empty `kline_list` rather than an error.
- **Order book depth varies by venue, not by plan:** 10 levels on HK equities, 5 on crypto, 1 on
  spot metals, none on indices.
- **WebSocket pushes are live and fast** — 235 ticks in 25s on three forex/metals/crypto codes,
  402 on `TSLA.US` alone. Push bodies match the REST tick shapes exactly.

## Known limits of this measurement

- A closed market looks identical to a denied one, so a miss is "no data for this token right
  now", not a proven permission error.
- The entitlement scan sampled 50 codes each from the three equity books (2,962 / 2,870 / 5,086)
  and swept the small classes whole.
- Trading hours in the spreadsheet are merged cells covering a whole exchange, so they describe
  an exchange rather than an instrument; `data/catalog.json` keeps the raw per-row values.

Sources: [AllTick API docs](https://alltick.co/apis/en),
[official GitHub](https://github.com/AllTick-Official/alltick-realtime-forex-crypto-stock-tick-finance-websocket-api).

`.token` is gitignored. Rotate the key if it has been shared.
