# Contracts — the six seams, and why nobody ever waits

This is the file that answers *"how do we not depend on each other."*

## The rule

> **Whoever owns a seam ships the type and a fake on the first day the seam exists. The consumer
> builds against the fake. The producer swaps in the real implementation later, behind the same
> type. Neither side ever waits.**

You have already done this once and it worked: the `/api/v1/analyze` contract was frozen on Day 1
(`sentiment` lowercase, `confidence` 0–100), and on Day 3 the entire analysis implementation was
replaced — lexicon out, Claude in — **with zero changes to the extension**. Same four keys, so
nothing downstream noticed. That is the whole technique. Do it five more times.

A fake is not a stub that returns `null`. A fake returns **realistic, shaped, varying data** —
enough that the consumer discovers their layout breaks on a 7-digit CVD or a 40-character symbol.
A fake that always returns the same tidy row teaches you nothing and hides bugs until integration.

## Freeze discipline

A frozen contract changes only by all three agreeing in standup, and the change lands as **one
commit that updates the type, the fake, the real implementation and both consumers together**.
Never half. `plans/current.md` already carries this rule for the analyze contract; these six join it.

---

## S1 · Tick record — Varad → everyone

The atom. Everything else is derived from this.

```
timestamp        datetime64[ns, UTC]   exchange timestamp, not receipt time
price            float64
size             int64
aggressor_side   category  'B' | 'A'   B = buyer lifted the ask, A = seller hit the bid
symbol           string                'GCQ6', 'GCZ6' — resolved contract, not the parent
instrument_id    int64
```

**Fixture:** `data/fixtures/gc_ticks_1session.parquet` — the **2026-07-16 GCQ6 session**, 77,532
trades, already chosen as the validation session in `DELTA_CVD_FINDINGS.md` for its 0.90 directional
efficiency and because it sits clear of both the 29 Jul GCQ6→GCZ6 roll and the 30 Jul day Databento
flagged `degraded`. Cut it from the existing `data/gc_trades.parquet`. This is the file every test
in the project asserts against for the next twelve weeks.

**The `.gitignore` exception is in place** (25 Aug). `data/` is excluded as of `8aece67`, and git
does not descend into an excluded directory — so a bare `!data/fixtures/gc_ticks_1session.parquet`
silently does nothing. Every level is re-included in turn, and only this one path comes back:

```
services/signal-data/data/gc_trades.parquet             ignored
services/signal-data/data/raw/*.dbn.zst                 ignored
services/signal-data/data/fixtures/other.parquet        ignored
services/signal-data/data/fixtures/gc_ticks_1session.parquet   TRACKED
```

Checked with `git check-ignore`, not by reading the patterns. Nothing else under `data/` can be
committed by accident, so the month of billed binary stays out of history.

### ✅ LANDED 25 Aug — `14f5547`, cut by Prathamesh with `cut_s1_fixture.py`

746 KB, in git, on `main`. The blocker recorded earlier the same day (the source parquet living only
on Prathamesh's disk) was closed by him pushing the cut rather than the month.

**Verified independently after pulling, against this contract rather than against the filename:**

| Check | Result |
| :--- | :--- |
| Rows | **77,532** — this contract's number, exactly |
| Columns | all six, correct dtypes, **no extras**, zero nulls, timestamps monotonic |
| Contract | `GCQ6` only, one `instrument_id` — no roll contamination |
| Session window | `18:00:00.5 ET` → `16:59:57.8 ET` — the CME trading day |
| **Session delta** | **+1,842** — matches `DELTA_CVD_FINDINGS.md` §3's side-field figure to the unit |
| `size` dtype | `int64`, so the `uint32` negation trap below is already avoided |

That delta match is the strongest confirmation available that this is the right session, cut
correctly, with the aggressor mapping intact — it reproduces a number computed by a different script
on a different machine from the full month.

### ⚠️ PENDING AMENDMENT — `'N'` is real and this contract does not admit it

**Not applied. This is a frozen contract and it changes only by all three agreeing in standup.**
Found by Prathamesh while cutting, documented in `cut_s1_fixture.py`, and deliberately left for
the room rather than taken unilaterally. **Queued for Wednesday 26 Aug, which passed without it
being put; it goes to the Week 0 gate on Fri 28 Aug** — see
[`varad/2026-08-28-gate-note.md`](varad/2026-08-28-gate-note.md), where the vote is item 1 and the
421 duplicate rows below are item 2.

`aggressor_side` is declared `'B' | 'A'`. The real data carries a third value — **`'N'`, 1,811
trades, 2.34%, 2,271 contracts of volume** — where no aggressor was disseminated (auction, implied,
off-book). **This contract's own row count of 77,532 already includes them**, so the count and the
type as written cannot both be true.

**Those three numbers describe this fixture — one session, 2026-07-16 — and nothing wider.** The
rate is not a constant, and the first draft of the wording below generalised it to "~2.3% of
trades", which is false at month scale. Measured across **19 months, Jan 2025 – Jul 2026,
46,034,813 trades** (`services/signal-data/analysis/gc_data_manifest.md`):

| scope | `'N'` rate |
| :--- | ---: |
| this fixture, 2026-07-16 | 2.34% |
| July 2026, full month | **3.89%** |
| 19-month range | **1.15% – 5.23%** |
| roll months (two contracts), n=9 | mean **3.75%** |
| single-contract months, n=10 | mean **1.92%** |

**`'N'` concentrates in roll months at roughly double the mid-cycle rate.** The ranges overlap —
2025-08 at 3.63% and 2026-02 at 3.00% both clear the roll minimum of 2.68% — so this is a strong
tendency, not a separation. The plausible mechanism is **calendar-spread legs carrying no aggressor
side**, which is testable and has not been tested. July 2026 is itself a roll month (`GCQ6`→`GCZ6`)
and its 3.89% lands on the roll-month mean; it was not among the months that produced that mean, so
that is an out-of-sample fit rather than a fitted one.

**Why this matters more than the number:** unsigned rows contribute nothing to delta or CVD, so
**delta is least complete exactly when the active contract underneath it is switching.** A flat
"~2.3%, tolerable" reading hides that entirely.

Consequences if a consumer takes `'B' | 'A'` literally:

```
df["aggressor_side"].map({"B": 1, "A": -1})   ->  1,811 silent NaN
df.groupby("aggressor_side")                  ->  3 groups, not 2
```

**Drafted wording, so standup is a yes/no and not a discussion:**

> `aggressor_side   category  'B' | 'A' | 'N'` — `N` means no aggressor was disseminated (auction,
> implied, off-book). It **contributes 0 to delta** and its share is **not constant**: 1.15–5.23%
> across Jan 2025 – Jul 2026, averaging **3.75% in roll months against 1.92% in mid-cycle months**.
> Consumers must handle it explicitly; it is never silently dropped. **Any consumer reporting delta
> must report the `'N'` share alongside it**, because the months where delta is least complete are
> the months where the active contract changes.

Keeping the rows is the right resolution: dropping them would make volume stop reconciling and would
mean consumers never learn `N` exists until they hit live data.

**Still not applied — this remains a proposal, and the vote is unchanged.** What changed on 28 Aug is
the evidence behind it: the wording now carries a 19-month distribution instead of one session's
rate, and one sentence was added requiring consumers to report the `'N'` share next to delta. The
amendment itself is still Wednesday's yes/no.

### Three traps already found here, worth not re-discovering

The first two come from `8aece67`; the third was found verifying the fixture on 25 Aug.

1. **`to_df()` attaches its own `symbol` column** with `map_symbols=True`, so a definitions merge
   produces a 2-D `df["symbol"]` and `groupby` dies. Databento's copy is now `symbol_mapped` and
   agrees with the resolved symbol on 100.0000% of 1,769,563 rows.
2. **`size` is `uint32`, so `-df["size"]` wraps to ~4.29e9** instead of going negative. Cast to
   `int64` first. The fixture is already `int64`.
3. **The fixture contains 421 duplicate rows, and they are real.** 788 rows in 367 groups, up to 6
   identical copies, every one sharing an exact timestamp — the signature of one aggressor order
   sweeping several resting orders and being reported as separate trades with identical fields.
   **They are not errors and must not be cleaned.**

   ```
   session delta as-is         +1,842
   after df.drop_duplicates()  +1,989      <-  +8.0% drift, 453 contracts deleted
   ```

   A one-line `drop_duplicates()` that looks like hygiene moves session delta by **8%** — half the
   size of the ~15–20% method-dependence residual, introduced silently by a habit. Any code touching
   this fixture inherits all three.

**Two more things `cut_s1_fixture.py` establishes**, both worth knowing before writing a consumer:

- `pull_futures_trades.py` writes `buy_initiated` / `sell_initiated` / `unknown`, **not** `B`/`A` —
  so this contract's encoding was never what the pipeline emitted. The cut script reverses
  `SIDE_MAP` to produce the raw exchange encoding specified here.
- The parquet is written with `version="2.6"`. **Parquet 1.0 tops out at microseconds**, so writing
  under it silently downgrades the `datetime64[ns, UTC]` this contract pins. The script re-reads the
  written file and asserts dtypes on the file rather than on the in-memory frame — a dtype that only
  survives until the write is not a contract.

**Frozen:** W0D2. **Already real** — the full month (1,616,772 GC trades) was pulled on 24 Aug and
`pull_futures_trades.py` writes exactly these columns.

**Traps here are listed once, above** — see *"Three traps already found here"*. All three are
inherited by any code touching this fixture.

**Why it matters:** `aggressor_side` is the field a screenshot cannot contain. If its mapping is
inverted, every delta sign in the product is wrong and every chart still looks plausible. Validate
it against a real footprint chart before anything is built on top — Week 1 Day 2, Varad, and
Shreyas grades it independently.

---

## S2 · Engine IPC — Varad's engine ← Prathamesh's UI

**The seam that would otherwise block Prathamesh for three weeks.** He cannot build an Analyze
view against an engine that doesn't exist until Week 3 — unless the engine's shape exists on Day 1.

```ts
// apps/desktop/src/lib/engine/types.ts   ← frozen W1D1, owned jointly
export type Side = 'bid' | 'ask'

export type DeltaBar = {
  t: number          // bar open, epoch ms
  o: number; h: number; l: number; c: number
  volume: number
  delta: number      // askVol - bidVol, signed
  cvd: number        // running session total
  bidVol: number
  askVol: number
}

export type Outlier = {
  id: string
  t: number
  price: number
  size: number
  side: Side
  kind: 'absorption' | 'trapped' | 'cluster'
  clusterLow: number
  clusterHigh: number
  score: number      // 0-100, comparable across instruments
}

export type FeedStatus = {
  state: 'disconnected' | 'connecting' | 'live' | 'stale'
  vendor: string | null
  lastTickAt: number | null
  gapCount: number
}

export interface Engine {
  connect(creds: FeedCreds): Promise<FeedStatus>
  status(): Promise<FeedStatus>
  setContext(ctx: CaptureContext): Promise<void>
  onBar(cb: (b: DeltaBar) => void): () => void
  onOutlier(cb: (o: Outlier) => void): () => void
  onStatus(cb: (s: FeedStatus) => void): () => void
}
```

**Two implementations, one switch:**

- `engine/mock.ts` — replays `gc_ticks_1session.parquet` (exported to JSON) at 10x speed, fires
  plausible outliers, and can be told to go `stale`, to drop, and to emit a 7-digit CVD.
  **Prathamesh writes this, W1D2**, because he is the one who needs it to behave badly on demand.
- `engine/real.ts` — thin wrapper over Tauri `invoke` / `listen`. **Varad, W3D1.**
- `engine/index.ts` — picks one on `VITE_ENGINE=mock|real`. Default `mock` until W3.

**Consequence:** Prathamesh's entire Weeks 1–3 UI work is testable without a single tick of real
data, and Varad's entire engine work is testable without opening a window. They meet on W3D3.

---

## S3 · API key — Varad's backend ← Prathamesh's desktop and web

The artifact's "single wire between web and desktop". Keep it single.

```
POST /api/v1/keys/validate
Header: X-API-Key: ti_live_<32 chars>
200 → { "valid": true,  "tier": "core" | "core_journal",
        "expires_at": "2026-12-01T00:00:00Z" | null, "reason": null }
200 → { "valid": false, "tier": null, "expires_at": null,
        "reason": "expired" | "revoked" | "unknown" }
503 → { "detail": { "error": "..." } }        upstream down — see the analyze route's shape
```

Note `valid: false` is a **200, not a 401**. The desktop app must distinguish "your key is bad"
(show a message, keep working offline) from "we couldn't reach the server" (keep working, retry
quietly). A 401 conflates them.

**Fixture:** `services/api/tests/fixtures/keys_fake.py` — a FastAPI app returning all six branches,
runnable on port 8001. **Varad — landed early, 25 Aug.** Prathamesh points at it from W5D1 and never
knows the difference when the real one lands W5D3. The branch is selected by the key
(`ti_live_core…`, `journal`, `expired`, `revoked`, `down`; anything else is `unknown`), so all six
are reachable on demand rather than only when the server happens to be in that state. A missing
header is a 422 — the seventh case, and the one the desktop app should never produce.

**Frozen:** W0D3. *(This section previously read W1D1, which contradicted `week-00.md` and
`varad/README.md`; both put it on Fri 28. W0D3 is correct and the fixture is now ahead of it.)*

---

## S4 · Journal sync — local-first, Prathamesh owns from W6

```
POST /api/v1/journal      { "entries": JournalEntry[] }
200 → { "accepted": 12, "conflicts": [{ "id": "...", "server_updated_at": "..." }] }
GET  /api/v1/journal?since=<iso8601>
200 → { "entries": JournalEntry[], "server_time": "..." }
```

**Conflict rule: last-write-wins by `updated_at`, and the loser is kept.** A trader's journal entry
is not something you silently discard because two devices disagreed.

**The load-bearing property: the app never blocks on sync.** The journal is local storage first,
sync second. If the backend is down for a day, the user notices nothing except a "last synced"
timestamp going stale. This is what lets Prathamesh build the whole journal in Week 4 with no
backend in existence.

---

## S5 · Payment → key issuance

Prathamesh's website only needs the exit door:

```
GET /api/v1/keys/mine      (Clerk session cookie)
200 → { "key": "ti_live_...", "tier": "core", "created_at": "..." }
404 → no key yet — payment still settling, poll every 2s for 30s, then show support link
```

Everything upstream of that — the processor webhook, signature verification, idempotency on
`event_id`, replay handling — is Varad's and invisible to the web pages. **Webhooks arrive twice.
The handler is idempotent or it issues two keys and bills once.**

**Fixture:** a `POST /api/v1/dev/issue-key` route, dev-only, gated on a config flag. Prathamesh
builds and tests the full purchase→key→install flow in Week 6 without a payment processor being
connected. The flag is asserted `false` in the production config test.

---

## S6 · Capture context — Prathamesh → Varad's engine

The narrowest seam in the project, and it is narrow **on purpose**.

```ts
export type CaptureContext = {
  symbol: string          // 'GC' | free text if unrecognised — see below
  timeframe: string       // '1m' | '5m' | '15m' | ...
  levels: number[]        // price levels the trader has drawn
  confidence: number      // 0-100, how sure the extraction is
  capturedAt: number
}
```

`symbol` stays a free string rather than a `'GC'` literal on purpose: capture reads whatever chart
the trader has open, which is frequently **not** something we have a feed for. The unrecognised case
is a real state the UI must render honestly (Week 3 Thursday), not an error.

**Capture produces context. Capture never produces a number that appears in a signal.** Not delta,
not CVD, not volume, not an outlier. It is information-theoretically impossible — a rendered candle
has already thrown away which side was the aggressor, and two sessions with identical candles can
have opposite CVD.

Write this down here because it is the exact mistake that is easy to make in Week 8 under pressure,
when the vision model returns something that *looks* like volume and it would be so convenient.

**Enforcement:** `CaptureContext` has no numeric field other than `levels` and `confidence`. If
someone needs to add one, that is a contract change and needs all three in standup. The type is the
guardrail.

---

## Fixture ledger

Everything committed so both engineers can work offline, on a plane, at 2am, with the other one
asleep.

| Fixture | Owner | Lands | Unblocks |
| :--- | :--- | :--- | :--- |
| `data/fixtures/gc_ticks_1session.parquet` | ~~Varad~~ **Prathamesh** | ✅ **landed 25 Aug** (`14f5547`, was W0D2) | Every engine test, and the mock engine |
| `apps/desktop/src/lib/engine/mock.ts` | Prathamesh | W1D2 | All UI work, weeks 1–3 |
| `services/api/tests/fixtures/keys_fake.py` | Varad | ✅ **landed 25 Aug** (was W1D1/W0D3) | Desktop key flow, week 5 |
| `POST /api/v1/dev/issue-key` | Varad | W5D2 | Website purchase flow, week 6 |
| `docs/qa/reference-session.md` | Shreyas | W1D2 | Every "is the delta right" argument, forever |

## The dependency graph, after all this

```
Varad   W1 ── W2 ── W3 ── W4 ── W5 ── W6 ── W7 ── W8 ── W9 ── W12
                     │                │
                     └─ S2 real       └─ S3 real
                        swap-in          swap-in
                        (1 day)          (1 day)
Prath.  W1 ── W2 ── W3 ── W4 ── W5 ── W6 ── W7 ── W8 ── W9 ── W12
```

**Two one-day integration points in twelve weeks.** W3D3 and W5D3. Everywhere else the two lanes
are genuinely independent, because everywhere else each side is talking to a fake it controls.
