# The unconditional reach baseline — 19 months, 107,359 legs

**Measured 2026-09-05** by `base_rates.py`, over the whole Databento archive (Jan 2025 – Jul 2026).
Counts in [`base_rates_70_20_30m.csv`](base_rates_70_20_30m.csv). Reproduce with:

```sh
PYTHONPATH=. uv run python base_rates.py --out analysis/base_rates_70_20_30m.csv
```

Entry on **every bar, long, no filter** — 5-minute bars, 70-tick target, 20-tick stop, 30-minute
horizon, ATR over a 60-minute window. **This is the null.** Nothing here selects, tunes or fits, so
running it over every month costs no out-of-sample data — it is the population being measured, the
same class of statistic as `horizon.py`'s sigma.

Same-bar ties resolve to the stop (`backtest.first_touch`), so every `p_target` here is a **lower
bound** and every `p_stop` an upper one.

---

## 1. The headline

| ATR bucket | n | p_target | p_stop | breakeven | EV |
| :--- | ---: | ---: | ---: | ---: | ---: |
| <30 | 38,573 | 0.0563 | 0.5179 | 0.1480 | **−6.42 ticks** |
| 30–40 | 18,509 | 0.1370 | 0.6919 | 0.1977 | **−4.25** |
| 40–50 | 14,854 | 0.1688 | 0.7393 | 0.2112 | **−2.97** |
| 50+ | 35,423 | 0.1990 | 0.7828 | 0.2237 | **−1.73** |

`breakeven` is the `p_target` at which a 70/20 bracket stops losing money, `p_stop × 20/70`.

**No bucket clears it.** The gap narrows monotonically with ATR — −0.092, −0.061, −0.042, −0.025 —
and never closes. That is the right shape for a series `horizon.py` measured as a random walk, and
the value here is that the null is now a measured number in the units the product would quote rather
than an assumption.

Pooling is a **sum of counts, never a mean of rates.** Months differ in leg count by ~20% and in
bucket *mix* by 6×, so averaging monthly rates would weight a thin cell like a fat one.

---

## 2. Correction — `p_stop` is not flat, and that was a one-month artefact

`daily_updates/2026-09-05.md` and `plans/current.md` recorded, from July 2026 alone:

> `p_stop` is flat at 0.73–0.77 across every ATR bucket, so a 70/20 bracket breaks even at
> `0.75 × 20/70 = 0.214`.

**Over 19 months `p_stop` is monotone in ATR, not flat:**

| | <30 | 30–40 | 40–50 | 50+ |
| :--- | ---: | ---: | ---: | ---: |
| July 2026 only | 0.728 | 0.752 | 0.772 | 0.762 |
| 19 months | **0.518** | **0.692** | **0.739** | **0.783** |

So **breakeven is per-bucket — 0.148, 0.198, 0.211, 0.224 — not a single 0.214.** July's flatness came
from being a high-volatility month in which the low-ATR bucket held only 1,013 of 6,023 legs and did
not look like the low-ATR bucket of a quiet month.

**The conclusion that rested on it is unchanged.** `horizon.py`'s rate power says n=46 cannot separate
anything below `p_target = 0.329`, and the highest per-bucket breakeven in the archive is **0.224**.
The band between them is still a profitable strategy that 46 signals would report as nothing, so
**Gate 1's option (a) stays closed.** What moves is the supporting number, not the finding.

---

## 3. The monthly swing is mix, not the buckets moving

The headline monthly `p_target` runs **0.0345 (2025-01) to 0.1916 (2026-02)** — a 5.6× range, and it
steps rather than drifts:

```
2025-01 .. 2025-09   0.035 0.055 0.055 0.167 0.132 0.087 0.048 0.063 0.102    mean 0.082
2025-10 .. 2026-07   0.179 0.182 0.148 0.185 0.192 0.187 0.188 0.185 0.175 0.164    mean 0.178
```

**A spread in that line is not evidence that any bucket's rate moved.** A quiet month spends its bars
in the low-ATR buckets and a violent one in the high, so the pooled monthly number moves with the mix
even if every bucket is constant. Split the archive at the step:

| ATR bucket | 2025-01 – 2025-09 | 2025-10 – 2026-07 | change |
| :--- | ---: | ---: | ---: |
| <30 | 0.0485 | 0.1090 | +0.061 |
| 30–40 | 0.1177 | 0.1541 | +0.036 |
| 40–50 | 0.1607 | 0.1719 | +0.011 |
| **50+** | **0.2000** | **0.1989** | **−0.001** |

And the mix, as a share of each period's legs in the 50+ bucket: **8.9% → 54.7%.**

**The 50+ bucket's rate is stable to one part in two hundred across a regime change that moved the
headline by 2.2×.** The market moved into higher ATR; the buckets themselves largely held. That is
the strongest evidence available that ATR is a real conditioner rather than a label.

---

## 4. Within-bucket stability, and the trap in reading it

Raw max−min of monthly `p_target` per bucket looks alarming for the low bucket:

| bucket | spread, all 19 cells | spread, cells with n ≥ 200 | cells kept |
| :--- | ---: | ---: | ---: |
| <30 | 0.475 | **0.116** | 17/19 |
| 30–40 | 0.162 | **0.162** | 19/19 |
| 40–50 | 0.122 | **0.070** | 17/19 |
| 50+ | 0.137 | **0.057** | 14/19 |

**The 0.475 is two cells: 2026-02 with n=14 and 2026-03 with n=24.** Those are months so volatile
that almost nothing sat below ATR 30, and a rate off fourteen legs is not a rate. Filtered at n ≥ 200
the spread collapses by a factor of four.

Read against the headline spread of **0.157**:

- **40–50 (0.070) and 50+ (0.057) are well inside it.** ATR is doing the work there, and a forecast
  conditioned on it inherits a modest error.
- **30–40 (0.162) is as wide as the headline itself.** That bucket is not stabilised by ATR alone and
  should not be quoted as though it were. It is also the bucket sitting closest to the middle of the
  distribution, so it will not be rare.

---

## 5. What this does and does not license

**Does:**

- The archive supplies **107,359 unconditional legs**, against `horizon.py`'s requirement of ~454 to
  prove a move off the base rate. The sample is no longer the constraint for the *null*.
- The 50+ and 40–50 buckets can carry a quoted probability with a small stated error.
- The Oct-2025 step is a **mix** shift. Do not model it as a rate change without re-checking §3.

**Does not:**

- **No signal set exists yet.** Every number here is unconditional. Gate 1 is still open, and nothing
  in this file chooses between its two remaining options.
- **No threshold is committed and no pass line is set** — that stays `thresholds_selector.md` §6.1's,
  and Varad's.
- **The 30–40 bucket is not yet a usable conditioner.** Something other than ATR is moving it.
- **Nothing here is out-of-sample for a strategy**, because no strategy has been fitted. The moment
  one is, this file's months become the population it must be held out from.
