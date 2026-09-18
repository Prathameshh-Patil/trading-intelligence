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
