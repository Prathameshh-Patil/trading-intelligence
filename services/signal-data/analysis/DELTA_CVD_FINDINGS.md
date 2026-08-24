# GC delta / CVD — findings

**Date:** 2026-08-24 · **Data:** `data/gc_trades.parquet` — GC, July 2026, 1,616,772 outright trades
**Script:** `services/signal-data/compute_delta_cvd.py`

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

Documentation alone is not proof, so the convention was tested against the data itself.

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

## 3. Reference-chart validation — **NOT DONE. GATE NOT MET.**

The Step 3 hard gate has **not** been cleared. Nothing downstream should be built on this yet.

Everything in §1 is *internal consistency* — the data agreeing with itself and with published
schema semantics. That is meaningfully stronger than an unchecked assumption, and it makes a
sign inversion very unlikely. It is **not** the same as the numbers matching an independent
platform's rendering of the same session, which is what was asked for and what would catch
errors these tests structurally cannot: a wrong contract, a timezone offset, a session-boundary
definition that differs from the reference, or a systematic magnitude problem.

**Why it could not be done here:**

- **ATAS and Sierra Chart are both Windows-only.** The target machine is an ARM MacBook Air.
  Neither runs natively; both would need Parallels/Wine plus a Windows licence.
- No Chrome extension is connected to this session, so a web-based reference could not be
  driven either.
- Network egress from both available sandboxes is allowlisted; market-data hosts are blocked.

**Practical options, in order of effort:**

1. **TradingView (web, works on macOS, free tier).** Chart `COMEX:GC1!`, 1-minute, add the
   built-in *Cumulative Volume Delta* indicator, set the session to 2026-07-16. Caveat worth
   knowing: TradingView derives delta from lower-timeframe bars using a tick-rule
   approximation, **not** true aggressor tags. Good for comparing direction, swings and turning
   points; not for tick-for-tick magnitude.
2. **Screenshot hand-off.** Open any footprint platform you already have and send the
   2026-07-16 GC session — the CVD line and a few price levels are enough to compare against
   `gc_cvd_2026-07-16.png` and `gc_footprint_2026-07-16.csv`.
3. **Enable computer use** on the Mac so a reference platform can be driven directly, if one
   gets installed.

**If it doesn't match, check in this order:** (1) the aggressor mapping — though it now has
three independent confirmations, so this is the least likely; (2) timezone — the data is UTC,
plots are rendered in America/New_York, and the session boundary is 18:00 ET; (3) contract —
July 2026 rolls GCQ6 → GCZ6 on Jul 29, and a reference charting a continuous front-month series
may splice differently.

---

## 4. GC vs spot XAUUSD — **NOT STARTED. BLOCKED.**

`dukascopy.com` and `datafeed.dukascopy.com` are unreachable from both available sandboxes
(DNS does not resolve; the egress proxy returns 403 on CONNECT). The download has to happen on
a machine with open network access.

Once a month of XAUUSD 1-minute bars for July 2026 exists locally, the remaining work —
UTC alignment, resampling, return correlation, basis distribution, dislocation flagging — is
offline and straightforward.

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
  **That key should be rotated** — it was also pasted into a chat transcript.
- **`uint32` negation trap.** `size` is `uint32`; `-df["size"]` wraps to ~4.29e9 instead of
  going negative. The script casts to `int64` first. Worth remembering for any future code
  touching this column.

---

## 6. Status

| Step | State |
| :--- | :--- |
| 1 · Aggressor convention | **Confirmed** — docs + three empirical checks |
| 2 · Delta, CVD, 1-min bars, footprint | **Done** |
| 3 · Reference-chart validation | **NOT DONE — hard gate open** |
| 4 · GC vs spot XAUUSD | **Blocked** — Dukascopy unreachable from here |
| NQ | Dropped per instruction; not pulled, ~$11.42 unspent |

Databento spend so far: **~$2.52** (GC only).
