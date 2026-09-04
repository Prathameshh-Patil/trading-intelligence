# AllTick gold: what depth you actually get

**Measured 2026-09-04 against the live free-plan key, not read off the docs.**
Two independent capture windows, three hours apart:

| | Window A | Window B |
| :--- | :--- | :--- |
| Start (IST) | 19:42 | 23:08 |
| Length | 240 s | 180 s |
| Book updates | 238 | 176 |
| Trade pushes | 238 | 164 |

`data/gold.json` holds window B, the most recent capture. Reproduce with
`ALLTICK_TOKEN=… make gold`.

## The answer

| Granularity | Available for `GOLD` |
| :--- | :--- |
| **L1** — best bid / best ask | **Yes**, but at 1 Hz |
| **L2 / MBP** — aggregated depth beyond the touch | **No.** The book is 1×1 on every update |
| **MBO** — order-by-order | **No.** Nothing order-level exists anywhere in the API |
| **Aggressor side** on trades | **Present but constant.** Unusable |
| **Historical tick or book** | **No endpoint exists.** Candles only |

**AllTick gold is a one-per-second top-of-book snapshot with a dead aggressor flag.**
Nothing in the Stage-1 stack — delta, CVD, `cvd_persistence`, absorption — can be
computed from it.

---

## 1. The book is one level deep, always

```
                        window A      window B
book updates                 238           176
shape                  1x1 ×238      1x1 ×176      (no other shape ever appeared)
spread  min / med / max   0.09 / 0.11 / 0.21     0.08 / 0.08 / 0.14
```

REST `/quote-b-api/depth-tick` returns the same 1×1 shape.

**This is not a plan cap.** The same free key, in the same session, returns deeper
books elsewhere:

| Code | Class | Bid levels returned |
| :--- | :--- | ---: |
| `700.HK` | HK equity | 10 |
| `BTCUSDT` | Crypto | 5 |
| `GOLD` | Spot metals | **1** |
| `000001.SH` | Index | 0 (no book at all) |

Depth is a property of the venue AllTick sources, not of the subscription tier.
Gold's source carries one level.

## 2. It is a 1 Hz snapshot, not a tick feed

```
                        window A      window B
book updates / second       0.99          0.98
trade pushes / second       0.99          0.91
tick_time % 1000               0             0     (every timestamp second-aligned)
```

Both streams tick about once per wall-clock second, and every timestamp lands on a
whole second. What arrives labelled `tick_time` is a **one-second bucket**, not the
time of a trade.

**How much is being dropped.** The `seq` field on the REST trade-tick response is a
venue-side counter. Sampling it either side of each capture window:

```
                        window A      window B
upstream ticks / second     52.4          33.6      (seq slope)
delivered ticks / second    0.99          0.91
fraction arriving           1.9%          2.7%
```

Window B was the quieter market of the two, and the delivered rate did not change —
which is what a fixed 1 Hz cap looks like, rather than a feed that simply had less to
send.

**And this is gold-specific, not a throttle on the key.** On the same free plan,
`TSLA.US` pushed 402 updates in 25 seconds — 16/second. The 1 Hz ceiling belongs to
the gold feed.

## 3. `trade_direction` is a constant, not an aggressor side

```
                        window A      window B
trade_direction = 1      238/238       164/164
price ticked up              116            77
price ticked down            120            82
price flat                     1             4
direction on down-ticks    1 ×120        1 ×82
direction on up-ticks           —        1 ×77
```

Price fell on 202 transitions across the two windows and the flag never once said
"SELL". It is not reporting who lifted or hit — it is a hardcoded 1.

This is the fact that decides the question. The GC work classifies aggressor side to
build delta and CVD; `pull_tbbo_validate.py` went to the trouble of reclassifying
every trade by the quote rule to earn 99.65% agreement on that field. AllTick's gold
flag carries **no information at all**, and there is no bid/ask history to reconstruct
it from — the book is only ever a single live snapshot.

## 4. The size numbers are not resting size

Bid and ask volume on `GOLD`, from two snapshots ~14 seconds apart in each window:

```
window A     bid 790,125 → 169,967      ask 789,611 → 162,457      4.6× swing
window B     bid 255,395 → 610,535      ask 299,320 → 595,050      2.4× swing
```

Bid and ask are near-identical to each other inside every snapshot, and the level
swings by multiples between them. That is not an order book. It is consistent with a
CFD venue publishing an indicative size, and with A2's existing finding that **spot
gold has no centralised volume** — which is why `real_volume` came back empty on MT5.

## 5. There is no CME gold here at all

The catalogue is 11,223 instruments across nine classes and contains **no futures
contract of any kind** — no `GC`, no `MGC`, no expiry-coded symbols. `GOLD` is spot /
CFD, and `USOIL` / `UKOIL` likewise. Whatever AllTick is, it is not a route to GC.

## 6. Nothing historical to backtest against

The API has six REST endpoints. `trade-tick` and `depth-tick` are **latest-value
only** — no timestamp parameter, no history for either. The only endpoint that goes
backwards is `/kline`:

- 500 candles per call, maximum
- `GOLD` daily returns 357 bars, 2025-04-21 → 2026-09-04
- `kline_timestamp_end` walks further back (forex, metals and crypto accept it; equities do not)
- all ten intervals work on gold, 1-minute through monthly

So even if the book were L2, you could not have backtested it. Book and tick data
exist only going forward, from whenever you start capturing.

---

## Verdict

**Not usable for order flow.** No depth beyond the touch, ~2% of ticks, a dead
aggressor flag, indicative sizes, and no history. Every input the signal work depends
on is either absent or unreliable.

**Usable for context, if anything.** OHLCV candles across ten intervals, and a 1 Hz
mid-price for an overlay. That is the same "context-only, we never claim delta on it"
box A2 already put spot gold in.

Databento stays the historical archive; the live GC feed question stays with
Ironbeam. Nothing here changes either.

## What was not tested

- **Paid tiers.** Everything above is the free plan. Depth being venue-shaped rather
  than plan-shaped is evidenced (§1), and the 1 Hz cadence is gold-specific rather
  than key-wide (§2) — but whether a paid gold subscription is a different feed
  entirely was not checked, and no tier was priced.
- **`trade_direction` on other instruments.** `TSLA.US` returned 0 (unknown) and
  `BTCUSDT` returned 1 in spot checks; neither was measured over a window the way
  gold was. The finding above is about gold.
- **Session coverage.** Two windows on one day, both inside London/NY hours. Nothing
  about the Asian session, the daily break, or rollover was observed.
