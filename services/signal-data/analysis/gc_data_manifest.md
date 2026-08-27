# GC parquet manifest — what the numbers were computed on

Generated 2026-08-28. `data/` is gitignored, so this file is the only
tracked record that a given month's parquet is the one a result came from. **Re-pulling from
Databento and getting a different `sha256` means the data moved, not the code.** Verify with:

```sh
cd services/signal-data
shasum -a 256 data/2026-01/gc_trades.parquet   # compare against the table below
```

Backup: parquets only, `~/Library/Mobile Documents/com~apple~CloudDocs/trading-intelligence-data/gc-parquet/`,
all 18 verified by `sha256` against source on 2026-08-28. The raw DBN cache is **not** backed up —
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
| **total** | **44,418,041** | **396** | | | | |

## Full digests

```
1d84c0b8c7ab884d5b4ff1fd2c89c86982ac5ac1caa5751d790a925752ccd413  data/2025-01/gc_trades.parquet
01bbd6aa7872234113f031d977611750b4e6bc6cffa1bd795bb5ce7e868734ee  data/2025-02/gc_trades.parquet
7f4b7330067fd051ce74dcfa0761f526b13bee1ea26e5a02fc6356c08feb5e37  data/2025-03/gc_trades.parquet
88c0edb86d59a461f00150b23d27570cc8c967488adf065bd8a557c1f5fd84c1  data/2025-04/gc_trades.parquet
12db1e02f6767c9970e5b203bc70c2b3ca5f95d7d3112c77a5fabab80dc3b76c  data/2025-05/gc_trades.parquet
dc21ffb308001ef491115d86e3dbc59cfcc92369bcd9653767b56c5a653eb81d  data/2025-06/gc_trades.parquet
47cda468ef5e4510e84b63d33acb198a7de93635f5f73243c99adcfae58879d3  data/2025-07/gc_trades.parquet
10c3b831d0f87eec8a21e3f47773abc4196b950ac2bf4831101289719d0764ef  data/2025-08/gc_trades.parquet
2848652fc56e2cacb8171d2523b8618cbfe5fb7423ecfff6465f877ed4105687  data/2025-09/gc_trades.parquet
d4aa690ce55640f92f2ead4cc8ed65cb3c97721d28e3a7ec3363598bf4da891e  data/2025-10/gc_trades.parquet
8d0f5dc2f2985db0a60602a486cbb99410f81773158c3ec23e8b3184bf2b6b8b  data/2025-11/gc_trades.parquet
9e501ec49fdd7b40d30cf64547d45e504087726f1f540d721a647362bd137051  data/2025-12/gc_trades.parquet
620d0f2fd6f318698724969d24c39dd66276c7608565bed04dc56dabeb217c80  data/2026-01/gc_trades.parquet
d442ba7d228f61ef0b667924be89c466a418c591547588b98e9befb71db8e015  data/2026-02/gc_trades.parquet
b13aca31e813628ce4b6b6d6a75079f21b9225a903860392ffd71604807990c7  data/2026-03/gc_trades.parquet
88316030271c759d6f311228fd875dbc120f4c2e42199062551e3a8b636f523c  data/2026-04/gc_trades.parquet
9f936b97febdecd698a720a13679faf93378962aa77755559de856556c7567fd  data/2026-05/gc_trades.parquet
45601f125a3722f877f36c461875809563cf8f9b9fb14503ac0729a0ed481d8e  data/2026-06/gc_trades.parquet
```

## Not in this table

**July 2026** — 1,616,772 rows, pulled 24 Aug on Prathamesh's machine and never copied here. It is
the month every validated delta number references, and it is the one gap in an otherwise contiguous
Jan 2025 – Jun 2026 local set. Re-pulling it here costs $2.52 and would independently reproduce a
row count computed on different hardware.
