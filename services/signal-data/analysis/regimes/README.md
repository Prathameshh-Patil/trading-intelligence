# ⚠️ These outputs are stale — regenerate before `select.py` reads them

**Written 2026-08-26.** The files in this directory were produced by `regimes.py` on a **five-feature**
matrix. `regimes.py` now has four.

| | |
| :--- | :--- |
| Produced by | `70b5ac4`, run at 09:23 UTC on 2026-08-26 |
| Feature set then | `realized_vol`, `cvd_slope`, `cvd_persistence`, **`cvd_efficiency_specced`**, `price_efficiency_asused` |
| Feature set now | `realized_vol`, `cvd_slope`, `cvd_persistence`, `price_efficiency` |

`cvd_efficiency_specced` — §2's literal `abs(CVD)/range` — was dropped on 26 Aug. It correlated with
`cvd_persistence` at **r = 0.803** across these very labels, so a Euclidean KMeans was counting CVD
directionality twice; and `price_efficiency_asused` was renamed to `price_efficiency`, the suffix
having only ever named a contrast that no longer exists. See the §2 deviation note in `regimes.py`'s
module docstring.

**So every number here is off a matrix that no longer exists.** The cluster centres have five
coordinates, the scaler has five, `regime_summary` carries a `cvd_eff_specced_med` column, and the
labels themselves would move under the current features. Nothing has been deleted, because these
files are the §6.2 pre-commitment and rewriting history is exactly what §6.2 exists to prevent — but
**they are a record of a superseded run, not a definition anything may be selected against.**

## To regenerate

Needs `data/gc_trades.parquet`, which is gitignored and lives on Prathamesh's machine only.

```
uv sync                      # scikit-learn was undeclared until f7e411e
python regimes.py --parquet data/gc_trades.parquet \
    --bar-size 5min --window 12 --vol-window-min 30 \
    --level window --k 3 --split-date 2026-07-19 \
    --no-session-phase-in-clustering --out-dir analysis/regimes
```

Two things to settle while re-running, both recorded in `plans/current.md` under Day 4 (evening):

- **`k`.** The stale run committed `k=3` while its own silhouette preferred `k=2` (0.299 vs 0.239).
  Under §6.2 the reason belongs in the artefact.
- **Whether these are regimes at all.** In the stale labels the median run was **2 bars — ten
  minutes** — and the label changed on **28.9%** of bars. Dropping a redundant feature will move
  that number; it is unlikely to fix it.

The walk-forward split was also fixed in `dcbde04` — it cuts on the session now, not the ET calendar
date. That does not move *these* labels (2026-07-19 is a Sunday), but it would move any weekday
split by 72 bars.
