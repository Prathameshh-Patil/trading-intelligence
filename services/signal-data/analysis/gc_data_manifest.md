# GC parquet manifest — what the numbers were computed on

Generated 2026-08-28. **19 months, 46,034,813 trades, 419 sessions,
Jan 2025 – Jul 2026 contiguous.** `data/` is gitignored, so this file is the only tracked record that
a given month's parquet is the one a result came from. **Re-pulling from Databento and getting a
different `sha256` means the data moved, not the code.**

```sh
cd services/signal-data
shasum -a 256 data/2026-01/gc_trades.parquet   # compare against the table below
```

Backup: parquets only, `~/Library/Mobile Documents/com~apple~CloudDocs/trading-intelligence-data/gc-parquet/`,
all 19 verified by `sha256` against source on 2026-08-28. The raw DBN cache is **not** backed up —
it exists only to avoid re-billing, and the data is re-purchasable.

| month | rows | sessions | `unknown` | contracts | bytes | sha256 (first 16) |
| :--- | ---: | ---: | ---: | :--- | ---: | :--- |
| 2025-01 | 1,600,148 | 22 | 3.29% | `GCG5·GCJ5` | 13,483,050 | `1d84c0b8c7ab884d` |
| 2025-02 | 1,795,877 | 20 | 1.49% | `GCJ5` | 15,058,803 | `01bbd6aa78722341` |
| 2025-03 | 1,777,751 | 22 | 3.00% | `GCJ5·GCM5` | 14,831,490 | `7f4b7330067fd051` |
| 2025-04 | 3,217,204 | 22 | 1.27% | `GCM5` | 26,315,790 | `88c0edb86d59a461` |
| 2025-05 | 2,728,392 | 22 | 2.68% | `GCM5·GCQ5` | 22,466,926 | `12db1e02f6767c99` |
| 2025-06 | 2,234,997 | 22 | 1.15% | `GCQ5` | 18,710,281 | `dc21ffb308001ef4` |
| 2025-07 | 2,056,630 | 24 | 3.69% | `GCQ5·GCZ5` | 17,117,777 | `47cda468ef5e4510` |
| 2025-08 | 1,956,251 | 22 | 3.63% | `GCZ5` | 16,296,828 | `10c3b831d0f87eec` |
| 2025-09 | 2,716,034 | 23 | 2.17% | `GCZ5` | 22,664,487 | `2848652fc56e2cac` |
| 2025-10 | 4,843,145 | 23 | 1.25% | `GCZ5` | 39,365,515 | `d4aa690ce55640f9` |
| 2025-11 | 2,580,956 | 21 | 3.53% | `GCZ5·GCG6` | 21,372,606 | `8d0f5dc2f2985db0` |
| 2025-12 | 2,802,584 | 22 | 1.76% | `GCG6` | 23,356,728 | `9e501ec49fdd7b40` |
| 2026-01 | 3,531,687 | 21 | 5.23% | `GCG6·GCJ6` | 29,061,344 | `620d0f2fd6f31869` |
| 2026-02 | 2,146,721 | 20 | 3.00% | `GCJ6` | 17,955,063 | `d442ba7d228f61ef` |
| 2026-03 | 2,739,204 | 23 | 5.02% | `GCJ6·GCM6` | 22,718,860 | `b13aca31e813628c` |
| 2026-04 | 1,958,866 | 22 | 1.70% | `GCM6` | 16,037,939 | `88316030271c759d` |
| 2026-05 | 1,721,952 | 22 | 3.40% | `GCM6·GCQ6` | 14,318,823 | `9f936b97febdecd6` |
| 2026-06 | 2,009,642 | 23 | 1.74% | `GCQ6` | 16,845,857 | `45601f125a3722f8` |
| 2026-07 | 1,616,772 | 23 | 3.89% | `GCQ6·GCZ6` | 13,574,092 | `45947e88eb20f414` |
| **total** | **46,034,813** | **419** | | | | |

## The roll chain

Unbroken across every handoff. GC's active cycle is Feb/Apr/Jun/Aug/Dec — it skips V and X, which is
why `GCZ5` spans four months and is the least-exercised path through `collapse_to_active_contract`.

```
GCG5 → GCJ5 → GCM5 → GCQ5 → GCZ5 → GCG6 → GCJ6 → GCM6 → GCQ6 → GCZ6
```

Roll months carry two contracts, mid-cycle months one, and each month's closing contract opens the
next.

## `unknown` aggressor side is a roll-month artifact

Roll months (n=9) mean **3.75%**; single-contract months (n=10) mean **1.92%**.
Full range 1.15–5.23%. The ranges overlap, so this is a tendency, not a
separation. Plausible mechanism: **calendar-spread legs carry no aggressor side** — testable, untested.
Those rows cannot be signed and contribute nothing to delta or CVD, so **delta is least complete
exactly when the active contract is switching.**

~~**The `contracts.md` amendment for `'N'` is drafted against the wrong number.**~~ **Fixed 28 Aug
(`99fac6b`), and the gate note that quotes it fixed 3 Sep.** The amendment now carries the 19-month
distribution and the roll/mid-cycle split rather than the fixture's 2.34% / 1,811 trades.

**Volume shares, measured 3 Sep** — the trade-count column above only bounds delta damage if
unsigned trades are ordinary-sized, which was assumed and is now measured: pooled **2.73% of trades
against 2.68% of contracts**, tracking within 0.2 pp in every one of the 19 months. Roll months mean
3.73% of volume, mid-cycle 1.90%, range 1.21–5.06%.

⚠️ **These parquets spell it `unknown`, not `'N'`** — `buy_initiated` / `sell_initiated` /
`unknown`, per `pull_futures_trades.py`'s map. `'B'/'A'/'N'` is the S1 *fixture's* encoding.
Filtering a month file for `'N'` returns zero rows, which reads as "the amendment is about nothing."
It is the same field.

## Provenance note

July 2026 was pulled twice: 24 Aug on Prathamesh's machine, and 28 Aug here. **Both produced
1,616,772 rows with a 48.32 / 47.79 aggressor split** — identical on different hardware, days apart.
That is an independent reproduction of the month every validated delta number references.
