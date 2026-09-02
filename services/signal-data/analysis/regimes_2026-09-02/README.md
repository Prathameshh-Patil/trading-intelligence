# Regenerated regime labels — 2026-09-02

Supersedes `analysis/regimes/` (26 Aug run), per `plans/team/week-01.md` §1 (Prathamesh's Friday
prep, item 2): that run was off a five-feature matrix `regimes.py` no longer has, and off the
straddling-window bug `d3c896f` fixed. **The old directory is left in place, untouched** — this is
a new run under a new name, not an overwrite, per §6.2's pre-commitment rule.

Command (unchanged from `analysis/regimes/README.md`):

```
uv run python regimes.py --parquet data/gc_trades.parquet \
    --bar-size 5min --window 12 --vol-window-min 30 \
    --level window --k 3 --split-date 2026-07-19 \
    --no-session-phase-in-clustering --out-dir analysis/regimes_2026-09-02
```

Same July 2026 month (`data/gc_trades.parquet`, 1,616,772 trades), four features
(`realized_vol`, `cvd_slope`, `cvd_persistence`, `price_efficiency`), k=3, dwell_lambda=0.5.

| | Old (`analysis/regimes/`, 26 Aug) | New (this run) |
| :--- | ---: | ---: |
| Features | 5 (`cvd_efficiency_specced` + `price_efficiency_asused` both kept, unresolved) | 4 (`price_efficiency` only) |
| `n_fit` | 3,493 | 3,373 |
| `n_labelled` | 6,243 | 6,023 |
| Straddle fix (`d3c896f`) | not applied | applied |

Regime split (window-level, 5min bars, k=3):

| regime | n | pct | realized_vol (med) | cvd_slope (med) | cvd_persistence (med) | price_efficiency (med) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 930 | 15.4% | 0.000357 | 27.566 | 0.612 | 0.540 |
| 1 | 1,296 | 21.5% | 0.000316 | -26.668 | 0.613 | 0.539 |
| 2 | 3,797 | 63.0% | 0.000275 | -0.199 | 0.206 | 0.341 |

Persistence: median run 7 bars (35 min), longest 68, regime changes on 9.5% of bars.

**Not yet reviewed against the plot or hand-checked per §6.2** — that review, and the decision on
whether to promote this over the stale directory as the canonical one, is still Varad/the room's,
not automated here. This directory exists so Week 1 D1 is not blocked on producing it from scratch.
