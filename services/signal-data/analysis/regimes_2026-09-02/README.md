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

**Reviewed against the plot 2026-09-04** — see below. Not yet hand-checked per §6.2 — that review, and the decision on
whether to promote this over the stale directory as the canonical one, is still Varad/the room's,
not automated here. This directory exists so Week 1 D1 is not blocked on producing it from scratch.


---

## Reviewed against the plot — 2026-09-04

D1 gated on `regime survival >= 0.92`, which on these labels keeps **regime 2 alone**. Reviewing the
plot before accepting that showed the threshold was measuring the wrong thing.

**Raw survival is confounded by base rate.** A regime holding 63% of bars scores 0.63 by shuffling
alone. Normalising for that — `kappa = (P(stay) - share) / (1 - share)`, Cohen's kappa against a
shuffled-label null — **inverts the ranking**:

| regime | share | P(stay), 1 bar | vs chance | **kappa** | E[run] |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 15.4% | 0.866 | **5.61×** | **0.842** | 7.5 bars |
| 1 | 21.5% | 0.875 | **4.07×** | **0.833** | 8.0 bars |
| 2 | 63.0% | 0.927 | 1.47× | 0.798 | 13.7 bars |

**The two flow regimes are the more persistent ones**, once you stop rewarding a regime for being
common.

**They are not unstable, and the transition matrix is what proves it:**

| from \ to | 0 | 1 | 2 |
| ---: | ---: | ---: | ---: |
| **0** | 0.8664 | **0.0043** | 0.1293 |
| **1** | **0.0023** | 0.8753 | 0.1224 |
| **2** | 0.0323 | 0.0407 | 0.9270 |

`0 → 1` and `1 → 0` are ~0.3%. **The directional regimes essentially never flip into each other** —
they decay into 2 and come back. There is no churn between opposite flows, which is the specific
instability that would have justified excluding them.

**Nor are they high-variance.** Within-regime spread on the clustering's own features:

| feature | r0 sd | r1 sd | r2 sd |
| :--- | ---: | ---: | ---: |
| `price_efficiency` | 0.243 | 0.233 | 0.230 |
| `cvd_persistence` | 0.200 | 0.191 | 0.153 |
| `realized_vol` | 0.0004 | 0.0002 | 0.0001 |

`price_efficiency` is identical across all three. Regimes 0 and 1 are no noisier than 2.

**Regime 2 is the residual bucket.** `cvd_persistence` median 0.206 against 0.61; `price_efficiency`
0.341 against 0.54; `cvd_slope` −0.199 with sd 11.4, which is noise around zero. It is the "nothing
coherent is happening" state, and `survival >= 0.92` kept it and nothing else.

### Consequences

- **The 0.92 threshold is retired.** It came from Stage 2's 5-minute survival figure and does not
  survive contact with these labels. `regime_filter.py` gates on **kappa** instead.
- **On this labelling the regime dimension carries no filtering information** — all three regimes clear
  `kappa >= 0.75` (0.842 / 0.833 / 0.798 on the training half). That is the honest result, not a
  failure: it says the clustering separates *what the market is doing* but not *whether the label will
  hold*, and the filtering has to come from somewhere else.
- **Still not hand-checked per §6.2**, and still not promoted over `analysis/regimes/`. This review
  covered the plot and the transition structure; whether these labels are the canonical ones remains
  Varad's and the room's call.
