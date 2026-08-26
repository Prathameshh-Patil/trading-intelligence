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

## There is a second reason these are stale, and it is a bug

`d3c896f` fixed `window_features` letting a trailing window straddle the session CVD reset. `cvd`
restarts at ~0 each session, so such a window reads the reset as a move — **the eight largest
`cvd_slope` values in these very labels sit at `bar_in_session` 2–8 and read positive, up to +505, on
bars whose CVD was negative.** 253 bars, 4.0%, and they were the month's extremes, so after
`StandardScaler` they pulled a cluster centre. Re-running picks this up along with the feature drop:

| | median run | flips | silhouette | 30min survival |
| :--- | ---: | ---: | ---: | ---: |
| these files | 2 bars | 29.1% | 0.256 | 18.9% |
| after the fix | 4 bars | 13.7% | 0.305 | 46.2% |

**`k` no longer needs settling.** These files committed `k=3` while the silhouette appeared to prefer
`k=2`, which looked like an open question this morning. It was the bug: with the straddling bars out,
k=3 wins on every measure (silhouette 0.305 vs 0.247, median run 4 bars vs 2). Keep `k=3` and write
that reason into the artefact, which is what §6.2 wanted all along.

What remains genuinely open is whether to add a **causal dwell penalty**, and it is a decision rather
than a fix — see `plans/current.md` under Day 4 (evening). Do not add one without deciding it first;
§6.2 exists so that this kind of choice is made before anyone looks at per-strategy performance.

The walk-forward split was also fixed in `dcbde04` — it cuts on the session now, not the ET calendar
date. That does not move *these* labels (2026-07-19 is a Sunday), but it would move any weekday
split by 72 bars.
