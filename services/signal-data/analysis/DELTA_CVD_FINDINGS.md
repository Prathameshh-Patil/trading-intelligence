# GC delta / CVD — findings

**Date:** 2026-08-24 · **Updated:** 2026-08-25 (§3 closed, §4 cut)
**Data:** `data/gc_trades.parquet` — GC, July 2026, 1,616,772 outright trades
**Scripts:** `compute_delta_cvd.py` · `pull_tbbo_validate.py` · `verify_settlement_close.py`

---

## 1. Aggressor-side convention — CONFIRMED

Databento's `trades` schema defines `side` as *the side that initiates the trade* — the
aggressor, not the resting side:

| `side` | Meaning | Delta |
| :--- | :--- | :--- |
| `B` (Bid) | **The aggressor was a buyer.** They lifted the offer. | `+size` |
| `A` (Ask) | **The aggressor was a seller.** They hit the bid. | `−size` |
| `N` (None) | No side disseminated — auction, implied, off-book. | `0` (excluded) |

**The trap:** `A`/"Ask" does *not* mean "printed at the ask". It means the resting order that
got taken was a *sell* order, which makes the trade seller-initiated. Reading it the
natural-language way inverts the sign and yields a mirror-image CVD that looks entirely
plausible.

`SIDE_MAP` in `pull_futures_trades.py` already matched this. It was correct as written — but it
had never been checked against real rows, so it was unverified rather than known-good.

### Three independent confirmations

Documentation alone is not proof, so the convention was tested against the data itself. A fourth
— the quote rule, which reclassifies every trade without reading `side` at all — landed the next
day and is in §3.

**(a) Aggressor balance** — a broken mapping usually shows as a lopsided split:

```
sell_initiated   781,227   48.32%
buy_initiated    772,661   47.79%
unknown           62,884    3.89%
```

Essentially symmetric. `unknown` is 12.15% across *all* prints but only 3.89% once spreads are
excluded — spread legs carry no aggressor side, which is one more reason dropping them is right.

**(b) Tick rule** — independent of Databento's docs entirely. A trade that lifts the offer
should print at or above the previous trade; one that hits the bid, at or below:

```
upticks    n=589,093    labelled buy_initiated : 82.89%
downticks  n=592,353    labelled sell_initiated: 83.08%
```

If the mapping were inverted these would read ~17%. The ~83% (rather than 100%) is expected —
the tick rule is a heuristic that mislabels same-price prints and multi-level sweeps.

**(c) Delta ↔ return correlation**, whole month, stable across resolutions:

| Bars | Pearson | Spearman | Sign agreement |
| :--- | ---: | ---: | ---: |
| 1-min | +0.5018 | +0.4993 | 64.9% |
| 5-min | +0.4979 | +0.5048 | 67.4% |
| 15-min | +0.4795 | +0.4921 | 68.1% |

A flipped sign would produce −0.50. **The delta sign convention is confirmed.**

---

## 2. What was computed

- **Per-trade delta** — `+size` buy-aggressor, `−size` sell-aggressor, `0` for `unknown`.
- **Continuous CVD** — trade-by-trade cumulative sum, **reset per session**. CVD is only
  meaningful relative to a start point; carrying it across the overnight break makes the level,
  not the shape, do the talking.
- **1-minute bars** — delta, volume, OHLC, and session CVD at each minute's close.
  31,306 bars → `gc_minute_bars_2026-07.csv`.
- **Price-level footprint** — net buy/sell volume at each traded price for one session.
  Full 0.1-tick resolution in `gc_footprint_2026-07-16.csv`; the plot rolls up to $1 bins.

**Session definition:** CME trading day, 18:00 ET → 17:00 ET (22:00 → 21:00 UTC in EDT).
Verified against the data — every gap >2h in the month falls exactly on a Friday 21:00 UTC
close / Sunday 22:00 UTC reopen. *This is EDT-specific; a month crossing the DST boundary needs
a real exchange calendar, not a fixed 2h offset.*

### Validation session: 2026-07-16 (GCQ6)

Chosen for directional cleanliness — 0.90 efficiency (|close−open| ÷ range), the highest in the
month — and because it sits mid-month on a single contract, clear of both the Jul 29 GCQ6→GCZ6
roll and Jul 30, which Databento flagged as `degraded` quality.

```
trades              77,532
volume             110,817 contracts
UTC window         2026-07-15 22:00:00Z -> 2026-07-16 20:59:57Z
America/New_York   2026-07-15 18:00 ET  -> 2026-07-16 16:59 ET
price              open 4068.9  high 4071.9  low 3973.4  close 3979.9   (−89.0)
session CVD close  +1,842
CVD high / low     +2,479 / −360
```

**Note the divergence: price fell 89 points while CVD closed +1,842.** The 08:00 ET hour is the
sharpest instance — delta +1,083 while price dropped 47.7 points. This was treated as a
suspected sign inversion and investigated; the three checks above rule that out. It is genuine
absorption: buyers repeatedly aggressing into heavy resting supply, price falling anyway. That
is a real and well-known order-flow signature — and it is *also* precisely what a flipped sign
would look like, which is why it was worth chasing rather than accepting.

---

## 3. Reference validation — **CLOSED 24 Aug** (`c504e50`)

Closed by an independent **method**, not an independent platform. The blocker below was never
about the numbers — ATAS and Sierra Chart are Windows-only and the machine is an ARM MacBook Air —
so the gate was cleared by re-deriving the aggressor side from data the pipeline does not use,
which sidesteps the platform problem entirely.

### `pull_tbbo_validate.py` — the quote rule

Every trade in the 2026-07-16 GCQ6 session reclassified by price against the bid/ask immediately
before the trade, using the `side` field **not at all**.

| Check | Result |
| :--- | :--- |
| Agreement with `SIDE_MAP` | **99.65%** across 75,578 comparable trades |
| Confusion matrix | near-symmetric — 96 vs 165 disagreements, so no directional bias |
| Hourly delta sign | **0 of 23 hours** disagree |
| The disputed 08:00–09:00 ET window | **+1,103** quote rule · +1,083 pipeline · +1,093 side field |
| Footprint cross-check | **980/980** common price levels · volume **r=1.0000** · delta **r=0.9870** · 96.91% sign agreement |

That last row is against `gc_footprint_quoterule_2026-07-15.csv`. **The name is a trap, not a
different day** — `pull_tbbo_validate.py` names its output from the *start of the pull window*
(`2026-07-15T22:00` UTC) while `compute_delta_cvd.py` names by the CME session day. Same session;
volume r=1.0000 over 980 shared levels would be impossible otherwise.

The 08:00–09:00 window is the one that mattered: §2 chased it precisely because absorption and a
flipped sign look identical, and it now reproduces under a method that cannot inherit the flip.

### `verify_settlement_close.py` — the one external reference

Free, no API call. Resolves the 12.2-point gap between our daily close (3979.9, last trade) and
TradingView's reported close (3992.1) as **settlement-window vs last-trade**, not a data bug —
VWAP over the CME closing range matches within 0.25 points.

Small, and it carries more than its size. The quote rule runs on the same venue's data, so it
**cannot** catch a wrong contract or a timezone offset — it definitively catches an inverted
mapping, which is what it was aimed at. The settlement check is the only comparison here against
a number computed by somebody else, so it is what covers contract and timezone.

### The residual — carry this downstream

**Session-total delta is method-dependent at ~15–20%:** side field **+1,842** vs quote rule
**+2,216**. Direction and shape are robust; **absolute magnitude needs an error bar**, and every
threshold derived from this data inherits it.

Still not covered: an independent *rendering* of the session. Nothing here draws the chart a
second way. That is the honest cost of closing the gate by method, and it is the residual a
reference platform would have removed.

**If a future comparison disagrees, check in this order** — inverted from the usual advice, because
the mapping now has four independent confirmations and is the *least* likely culprit: (1) timezone —
data is UTC, plots render in America/New_York, session boundary is 18:00 ET; (2) contract — July
2026 rolls GCQ6 → GCZ6 on 29 Jul, and a continuous front-month series may splice differently;
(3) the aggressor mapping, last.

---

## 4. GC vs spot XAUUSD — **CUT 25 Aug. Do not hunt for a mirror.**

This was recorded as blocked on `dukascopy.com` and `datafeed.dukascopy.com` being unreachable
from both available sandboxes (DNS does not resolve; the egress proxy returns 403 on CONNECT).
That is accurate and it is **not** why the work stopped.

**Spot gold has no centralised volume** — which is exactly why `real_volume` comes back empty on
MT5 — so there is no aggressor side, no delta, and nothing to correlate the product's core number
against. A working download mirror would not change that. The study was scoping spot XAUUSD as a
launch instrument, and that scope is gone: GC is the launch instrument (see `plans/current.md`).

It returns in the Week 12 quarter-two discussion as a **context-only** mode — rules, journal and
capture work on MT5, delta does not, and we never claim it does.

---

## 5. Also fixed along the way

- **`pull_futures_trades.py` crashed on the real pull.** `to_df()` runs `map_symbols=True` by
  default and already attaches a `symbol` column; the definitions merge added a second, so
  `df["symbol"]` returned a 2-D frame and `groupby` failed with *"Grouper for 'symbol' not
  1-dimensional"*. Databento's copy is now renamed to `symbol_mapped` and kept as a
  cross-check — it agrees with the independently-resolved definition symbol on
  **100.0000%** of 1,769,563 outright rows.
  *This was not a pandas 3.0 issue; it would have failed identically on pandas 2.x. A synthetic
  dry-run could never have caught it, because hand-built frames don't carry that column.*
- **Raw DBN caching.** Every billed `get_range()` now writes its DBN to `data/raw/` before any
  pandas touches it, so a processing failure never costs a second download. This paid for
  itself immediately — the crash above happened after GC had downloaded, and reprocessing was
  free.
- **`--estimate-only` didn't exist** despite being documented in the script's own USAGE block.
- **`.gitignore`** now covers `data/`, `*.parquet`, `*.dbn`, `*.dbn.zst`.
- **A real API key was sitting in the git-tracked `.env.example`.** Uncommitted, and confirmed
  absent from all branch history, but one `git add -A` from being pushed. Placeholder restored.
  **That key should be revoked** — it was also pasted into a chat transcript. *Rotate* was the
  original wording, from when a hosted backend was still being chosen; the analysis backend
  decision on 25 Aug is to build our own model, so nothing depends on that key and there is no
  replacement to issue. A live key serving no purpose is strictly worse than no key.
- **`uint32` negation trap.** `size` is `uint32`; `-df["size"]` wraps to ~4.29e9 instead of
  going negative. The script casts to `int64` first. Worth remembering for any future code
  touching this column.

---

## 6. Status

| Step | State |
| :--- | :--- |
| 1 · Aggressor convention | **Confirmed** — docs + three empirical checks, plus the quote rule below |
| 2 · Delta, CVD, 1-min bars, footprint | **Done** |
| 3 · Reference validation | **Closed 24 Aug** (`c504e50`) — quote rule + settlement close. Residual: session-total delta is method-dependent at ~15–20% |
| 4 · GC vs spot XAUUSD | **Cut 25 Aug** — spot gold has no centralised volume, so there is nothing to correlate. Not a download problem |
| NQ | Dropped 25 Aug; never pulled, ~$11.42 unspent. A quarter-two candidate, not a flag flip |

Databento spend so far: **~$2.52** (GC) plus the one TBBO session pull behind §3.

**The one number to carry out of this file:** direction and shape of delta are trustworthy;
**absolute magnitude carries a ~15–20% method-dependence** and every threshold derived downstream
inherits it.
