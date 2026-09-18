# E0 — the S3 transport. **Verified: five years of XAUUSD ticks are reachable, and the validated hour reproduces to the quote.**

**Run 2026-09-18, 09:30–10:00 IST**, from Prathamesh's Mac, on a personal AWS account created that
morning. Spec: [`2026-09-18-magnitude-expansion-design.md`](../../../docs/superpowers/specs/2026-09-18-magnitude-expansion-design.md) §6.0.
Pre-commitment: `strategy-precommit.md` §13.

⚠️ **Order of events, honestly.** The plan puts this probe *after* §13 is committed. It ran first,
the previous evening, because its first step surfaced a decision only Prathamesh could make — the
bucket is requester-pays and needs an AWS account — and that decision had to be made before 09:00,
not discovered at it. §13 is written knowing what the probe found, and says so.

⚠️ **Key rotation outstanding.** The access key used for this run was pasted into a chat transcript
before it reached `~/.aws/credentials`. Prathamesh chose to proceed and rotate afterwards. **It is
read-only on one public bucket, on a personal account, and it must still be deleted and reissued
before this file's commit is pushed.** Row #0 is the reason this paragraph exists.

---

## 1. The bucket, verbatim

```
$ curl -sI https://cfg-public-proper-wallaby.s3.eu-west-1.amazonaws.com/XAUUSD/2021/00/04_ticks.bi5   (anonymous, 17 Sep 18:33 UTC)
HTTP 403  <Code>AccessDenied</Code><Message>Anonymous users cannot invoke requests against Requester Pays buckets. Please authenticate.</Message>

$ aws sts get-caller-identity                                                                          (18 Sep, after account creation)
arn:aws:iam::<account>:user/spot-pull        -- IAM user, s3:GetObject + s3:ListBucket on this bucket only; never root

$ aws s3 ls s3://cfg-public-proper-wallaby/XAUUSD/2021/00/ --request-payer requester --region eu-west-1
PRE 01/  PRE 02/  PRE 03/  PRE 04/  PRE 05/  ...                  -- day PREFIXES, not files
```

**The layout has one more level than the plan's snippet assumed, and the plan's key is still
right.** Under a month, each day is a prefix holding candles, and the day's ticks are a sibling
file at the month level:

```
XAUUSD/2025/05/18/BID_candles_min_1.bi5     16,674 B    1-minute bid candles, one day
XAUUSD/2025/05/18/ASK_candles_min_1.bi5     16,584 B
XAUUSD/2025/05/18_ticks.bi5                934,900 B    every quote of the day   <- day_key(...) + "_ticks.bi5"
XAUUSD/2025/05/BID_candles_hour_1.bi5                   one month of hourly candles
XAUUSD/2025/05/BID_candles_day_1.bi5                    one month of daily candles
XAUUSD/metadata/HistoryStart.bi5                64 B
```

**Month is zero-indexed** — `/2025/05/` is June. Same trap `test_dukascopy.py` already pins; pinned
again in `test_spot_s3.py`. Saturdays have no file; Sundays do (the 22:00 UTC open).

## 2. Coverage

```
XAUUSD/ years present:   1997 .. 2026        -- history begins 1997-07, not 2021
tick day-files 2021-2026:  1,776 files, 1.343 GB

  2021   310 files   205.0 MB
  2022   310 files   216.8 MB
  2023   309 files   140.1 MB
  2024   313 files   227.6 MB
  2025   312 files   284.7 MB
  2026   222 files   269.0 MB     (to 2026-09-17, i.e. yesterday -- the bucket updates daily)

earliest tick file:   XAUUSD/2021/00/03_ticks.bi5   (2021-01-03, Sunday open)   [2021+ indexed; 1997-2020 not listed]
latest tick file:     XAUUSD/2026/08/17_ticks.bi5   (2026-09-17)
zero-byte files:      0 of 1,776
```

Five years is **~1,300 day-files, as the plan estimated**, against ~43,800 hour-files over the
throttled HTTP path. The whole 2021–2026 span is 1.34 GB.

**2023 is markedly smaller than its neighbours (140 MB vs 205–285) — checked, and it is the market,
not the feed.** No month is missing days (24–27 files each); the size declines smoothly from late
2022 to a trough in 2023-09 (7.1 MB) and steps up in 2024-04. Two comparable Wednesdays, decoded:

```
2023-09-13   93,485 quotes   day range $10.08 ( 53 bp)   median spread 1.62 bp   9,275 quotes per $ of range
2024-09-11  259,562 quotes   day range $28.05 (112 bp)   median spread 1.59 bp   9,253 quotes per $ of range
```

Quotes per dollar of range are identical to within 0.3%, and spreads match. Dukascopy quoted 2023
at the same density; gold simply moved half as much. **This matters more for the strategy than for
the transport**: 2023 is a low-magnitude year in exactly the sense `mathematical.md` conditions on,
so E1's base rate will differ sharply between 2023 and 2024–25, and §7.1's split should not put all
of one regime on one side by accident.

## 3. Cost — priced, not yet billed

Requester-pays charges the caller for requests and data transfer out of `eu-west-1`:

```
GET requests          $0.0004 / 1,000    1,776 files  ->  $0.0007
data transfer out     $0.09 / GB         1.343 GB     ->  $0.12      (first 100 GB/month free on the account's free tier)
listing (this file)   ~40 LIST calls                  ->  < $0.001
```

**Five years of ticks costs about twelve cents, and probably nothing.** A one-month pull
(2021-09, key `/2021/08/`: 26 files, 16.8 MB) is a fraction of a cent. The number that was
actually spent this session — one 935 KB object plus listings — will appear on the account's
first bill; this file should be amended with the billed figure when it does.

## 4. Cross-check against the validated hour — exact

`SPOT_FEED_CHECK.md` §1 validated **2025-06-18 14:00 UTC** over HTTP: 20,654 quotes, median spread
1.91 bp, mid 3373.861 … 3392.471. The same hour, cut from the S3 day file with `dukascopy.decode_bi5`
(base timestamp = midnight, since a day file's offsets run from 00:00):

```
day file        228,269 quotes   2025-06-18 00:00:00.100 -> 23:59:59.561 UTC
14:00 hour       20,654 quotes                        expected 20,654     EXACT
mid             3373.862 .. 3392.471                  expected 3373.861 .. 3392.471   (rounding, 1e-3)
median spread     1.91 bp                             expected 1.91       EXACT
```

**The decoder is unchanged and shared.** `decode_bi5` and `POINTS` are imported by `spot_s3.py`,
not reimplemented; the only difference between the two transports is the base timestamp passed in.

Repeated through the module once it existed, not just by hand:

```
spot_s3.fetch_day('XAUUSD', date(2025,6,18))  ->  14:00 hour 20,654 quotes · 1.91 bp · 3373.862 .. 3392.471
spot_s3.fetch_day('XAUUSD', date(2025,6,14))  ->  Saturday: NoSuchKey -> empty frame, S1 columns   (not an exception)
```

`tests/test_spot_s3.py`: 9 tests — Varad's six offline ones, plus the tick object's position beside the day
prefix, the midnight base for day files, and the missing-day-is-empty rule.

## 5. Verdict

**E0 passes. The kill condition (§6.0: "no S3 and no working daily-candle path") does not fire —
both paths work.** The daily-candle fallback was also verified (one file, 1,440 candles, 14:00 hour
envelope consistent) but is not needed. `mathematical.md`'s five-year premise is testable, and
§14's fine-tuning split has its data. Day 2's spot bar loader (Task 5) reads this transport.

**Not measured:** throughput of a bulk pull (how many objects/second before anything throttles —
S3 does not rate-limit like the HTTP datafeed, but it has not been shown here), and whether
1997–2020 ticks exist or only candles. Neither blocks the plan.

---

## 6. The HTTP tick path, re-measured 2026-09-19 — the 429 lifted, and it is still not a bulk transport

**Why this section exists.** §5 chose S3 and left the HTTP datafeed behind because it served ~2
requests from a three-day rest and then returned **429**, unlifted after 40 minutes. Track C's
build then stopped on `NoCredentialsError` with `~/.aws/` absent. Before accepting that as a wall,
the premise was re-measured.

**It has lifted.** Four hours of 2026-08-03 returned 11,001 / 20,758 / 16,728 / 13,814 quotes in
6–15s each. A full day of 2026-08-05, sequential and paced 1s apart, returned **20 of 24 hours**.

| What was tried | Result |
| :--- | :--- |
| 8 workers, `retries=1` | **12 of 24 hours**, rest `ConnectionError` |
| 4 workers, `retries=3` | **12 of 24 hours**, rest **HTTP 503** |
| sequential, 1s pacing, `retries=1` | **20 of 24** — 1 timeout, 1 reset, and hours 21–23 503 |

**Concurrency is what provokes the throttle**, and the identical 12/24 at two worker counts is the
signature of a budget rather than of flakiness. So `dukascopy.fetch_day` is sequential by
construction and paced, and the pacing is a documented argument rather than a constant.

**The throttle is a function of recent volume, not a fixed window — and this is the finding that
matters.** From a light load a 503 cleared after **~15s** of rest, which is what set
`fetch_day`'s `retries=5` (a 31s backoff against `fetch_hour`'s default 3, which waits 7s and gives
up just short). After ~150 requests across the session, **a mid-session hour with certain data
503'd through all five attempts** and aborted the day. A 10-minute rest did not visibly restore it.
**§5's 429 was very likely this same mechanism seen from a tired feed**, not a hard 2-request quota.

**The real pull did not complete.** `spot.pull("XAUUSD", ["2026-08"], fetch=dukascopy.fetch_day)`
cached 2026-08-01 (Saturday, empty) and 2026-08-02 (Sunday, 9,651 ticks, hours 22–23 only) and then
**aborted on 2026-08-03 at hour 04**. `fetch_day` raises rather than writing a short day: a day with
a hole is indistinguishable from a quiet session once it is on disk.

**A weekend needed stating rather than inferring.** **503 is returned both by the throttle and by
hours the venue was shut**, and the two cannot be separated by status code. `dukascopy.SHUT` /
`BOUNDARY` therefore carry the week as the *intersection* of the EDT and EST regimes — Saturday
entire, Sunday 00:00–21:59, Friday 22:00–23:59 are never requested; the daily break and the two
weekly boundaries accept a persistent 503 as "no object"; **everywhere else it still aborts.**
Confirmed against the two days pulled: Saturday empty at **zero requests**, Sunday hours 22–23 only,
and no day carries ticks in an hour `SHUT` calls shut.

**Arithmetic, and the verdict.** ~3–5 minutes a day against one S3 object: a month in an hour, and
**five years in ~120 hours** — before counting the passes the throttle forces. **The HTTP tick path
is a bounded-window transport for a machine with no AWS account. It is not an archive transport,
and §5's choice of S3 stands.**

**⚠️ §5's other sentence is now the interesting one.** *"The daily-candle fallback was also verified
(one file, 1,440 candles, 14:00 hour envelope consistent) but is not needed."* It is **one request
per day** against the tick path's 24, Dukascopy pads shut hours with flat zero-volume candles rather
than withholding the file (so `SHUT`/`BOUNDARY` would not be needed at all), and BID and ASK are
separate files — **2 requests a day, ~3,552 for five years.** What it cannot carry is `ticks`, the
quote count: a candle holds Dukascopy's *indicative volume*, a different quantity, and Track C
weights S3's session VWAP with `ticks` and percentile-ranks it as `ticks_pct`. **That is a
substitution this repo has written down twice as a way to be wrong** (`AllTick/GOLD.md`,
`spot.py`), so it is a decision for the room and not a fallback to take quietly.


---

## 7. ⭐ The day object is served over HTTP too — and that is the finding, not §6

**§6 concluded the HTTP path was a bounded-window transport. That conclusion is superseded, and by
one request.** §1 of this document recorded the bucket layout: the day's ticks are a **sibling
object at month level**, `XAUUSD/2026/07/03_ticks.bi5`, beside the day *directory* of hour files.
§6 walked the 24 hour files because that is what `dukascopy.py` had always done. **Nobody had asked
whether the datafeed serves the sibling.**

It does.

```
GET /datafeed/XAUUSD/2026/07/03_ticks.bi5      HTTP 200   840,688 bytes
  -> 204,368 quotes, 2026-08-03 00:00:00.064 .. 23:59:59.437
```

| | Hour files | **Day object** |
| :--- | :--- | :--- |
| Requests per day | 24 | **1** |
| Five years | ~43,800 | **1,776** |
| A shut day | 24 x ambiguous 503 | **HTTP 200, zero bytes** |

**Verified identical, not assumed.** Hour 13 of 2026-08-03 taken from the day object and from
`13h_ticks.bi5` agree on **20,758 quotes, row for row**, on `timestamp`, `bid` and `ask`. And the
day object for Sunday 2026-08-02 returns **9,651 quotes** — exactly what §6's hour-by-hour pull had
already cached for that day, from a different code path.

**A shut day answers for itself.** Saturday 2026-08-01 returns **HTTP 200 with a zero-byte body**,
which `decode_bi5` has always turned into an empty frame with the columns intact. So absence needs
no interpretation: **200-and-empty is the venue shut, and a 503 is the throttle.** §6 needed a table
of shut hours (`SHUT` / `BOUNDARY`, an EDT/EST intersection) purely because 24 hour files could not
distinguish those two. **One request removed the ambiguity, and the table was deleted with it** —
`dukascopy.py` is *shorter* after this change than before it.

**What remains true from §6:** the throttle is real and is a function of recent request volume. A
pull cached **46 days in one pass** before 2026-06-22 returned 503 through five attempts. It is
resumable by design, so the answer is pacing and passes, not concurrency.

**Verdict, revised.** The HTTP tick path is **an archive transport**, at full tick resolution, with
no AWS account and no candle substitution — so `ticks` and `spread_bp` keep their exact meanings and
§6's closing warning about indicative volume does not arise. **S3 is still cheaper in wall-clock and
still the right answer where credentials exist**; what has changed is that their absence no longer
blocks Track C.
