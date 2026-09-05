# Two engines instead of one — the D4 measurement

**Gate 1, option (c), chosen by Varad 2026-09-05.** Measured the same day by `families.py`.

`signals/engine.py`'s 3-of-4 checker fires **0 signals on 3,516 training bars**, and the reason is not
sparsity: A and B read *exhaustion*, C and D read *continuation*, and B and D co-fire on 26 bars while
agreeing on direction on **zero** of them. So the families are not combined. Each runs as its own arm.

```sh
PYTHONPATH=. uv run python families.py
```

**Training half only** — 3,516 bars, 13 sessions, ≤ 2026-07-19. **The held-out half was not read.**
No number in `families.py` was authored there; every threshold is transcribed from where it was
committed, and two tests assert the transcription against `daily_updates/2026-09-04.md`'s recorded
values.

---

## 1. The result

70-tick target / 20-tick stop at 30 minutes, against a **mix- and side-matched** archive null (§3).

| arm | signals | legs | p_target | null | lift | needs | EV | EV − cost |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| exhaustion `A∨B` | 405 | 393 | 0.1578 | 0.1635 | **−0.0058** | 0.2176 | −4.02 | −5.42 |
| continuation `C∨D` | 562 | 545 | 0.1651 | 0.1655 | **−0.0003** | 0.2114 | −3.78 | −5.18 |
| continuation `C∧D` | 29 | 27 | 0.1111 | 0.1755 | −0.0644 | 0.3983 | −9.26 | −10.66 |
| 3-of-4 *(reference)* | 0 | 0 | — | — | — | — | — | — |
| exhaustion `A∨B` **filtered** | 79 | 77 | 0.2078 | 0.1894 | **+0.0184** | 0.3217 | −0.78 | −2.18 |
| continuation `C∨D` **filtered** | 47 | 47 | 0.1702 | 0.1933 | −0.0231 | 0.3653 | −4.26 | −5.66 |
| continuation `C∧D` **filtered** | 0 | 0 | — | — | — | — | — | — |

`needs` is `horizon.mde_rate(null, legs)` — the `p_target` this arm's own N could separate from its own
matched null at 80% power. EV is in ticks; cost is `horizon.py`'s 1.4-tick round trip ($14.00).

**With A a stub, `A∨B` is B alone.** Stated so nobody reads the exhaustion arm as two conditions.

---

## 2. What it says, and why this one counts

**The two arms with enough N landed on their own null.** `C∨D` is **−0.0003** on 545 legs — dead on
the base rate to four decimal places. `A∨B` is **−0.0058** on 393.

**And this is a powered null, not an underpowered one.** Both arms' `needs` is ~0.21 against a null of
~0.164, so a lift of about **+0.05 — a 30% relative improvement — would have been detected at 80%
power.** They produced +0.000 and −0.006. That is the difference between *"we could not tell"* and
*"we looked, and there is nothing there"*, and it is why this measurement settles something where
option (a)'s 46 signals could not have.

**No arm is profitable.** The best is the filtered exhaustion arm at −0.78 ticks per trade, −2.18
after cost. Every other arm is worse than −3.7.

**The one positive number, stated at its true weight.** Filtered exhaustion shows **+0.0184** on 77
legs — an 11% relative lift on a null of 0.1894. Proving it needs **n ≈ 3,636**. At the filtered arm's
observed rate of 79 signals per 13 sessions, that is roughly **600 sessions, or about 2.5 years of
tape.** It is not evidence. It is the only direction in the table pointing up, and it is the arm that
Gate 1's option (b) — restoring condition A — would add to rather than dilute.

**`C∧D` at 27 legs was not measured.** Below `MIN_SAMPLES`, `needs` 0.398. Reported, not read.

---

## 3. Why the null is mix- and side-matched

Both halves were load-bearing and neither is obvious.

**Mix.** `BASE_RATES.md` §3 found the monthly base rate swings 5.6× almost entirely through the ATR
*mix* rather than the buckets moving — the 50+ bucket held at 0.2000 → 0.1989 across a regime change
that moved the headline by 2.2×. So an arm that fires mostly in high-ATR bars, compared against a
pooled rate, would show a lift that is **entirely its own ATR mix**. Each arm here is weighted onto the
archive rates by its own (side, bucket) distribution. The filtered arms' nulls rise to 0.189–0.193
precisely because the ATR gate pushes them into higher buckets — and that rise is exactly the credit
they must not be given.

**Side.** Gold trended over the archive, and shorts did marginally better in every bucket:

| | <30 | 30–40 | 40–50 | 50+ |
| :--- | ---: | ---: | ---: | ---: |
| long | 0.0563 | 0.1370 | 0.1688 | 0.1990 |
| short | 0.0609 | 0.1514 | 0.1874 | 0.2025 |

Scoring a two-sided arm against a long-only null would have understated the null in every bucket, and
credited each arm with a few tenths of a point it had not earned.

Nulls: `base_rates_70_20_30m.csv` and `base_rates_short_70_20_30m.csv`, 107,359 legs each.

---

## 4. A bug that looked exactly like a finding

The first run reported **zero filtered signals in every arm** — 0 of 405, 0 of 29, 0 of 562. That reads
as a real and dramatic result about the regime filter being anti-correlated with the conditions, which
the 2026-09-04 entry had already half-predicted (`cvd_persistence ≥ 0.40` passes 41.1% of all bars and
6.5% of signal bars).

**It was the wrong number.** `KAPPA_HORIZON_BARS` had been *derived* from the trade horizon — 30
minutes ÷ 5-minute bars = 6 — rather than transcribed. At 6 bars ahead every regime's kappa falls to
~0.30, all three fail the 0.75 gate, and the filter passes **0 of 3,516 bars**.

The recorded value is **1 bar**: `daily_updates/2026-09-04.md` has P(stay) 0.866 / 0.875 / 0.927
against shares 15.4% / 21.5% / 63.0%, giving kappa 0.842 / 0.833 / 0.798 — and E[run] of 7.5 bars puts
P(stay one bar) at 1 − 1/7.5 = 0.867, which is the first of those to three decimals.

**What caught it** was the other four gates reproducing the 2026-09-04 record exactly — persistence
41.1%, ATR 59.2%, EMA 66.4%, interior 99.3% — while kappa alone read 0.0%. Four out of five matching
is what makes the fifth a bug rather than a result.

`tests/test_families.py` now asserts both the kappa values and the four fire counts against that
entry. Neither existed before, and the second would have caught this in the same second.

---

## 5. What this does and does not settle

**Does:**

- **The two families, as currently specified, carry no directional edge over their own matched base
  rate** — measured at a sample size that could have seen a 30% relative lift.
- Option (c) is executed. The split was the right diagnosis of *why* 3-of-4 was empty, and it produced
  a real measurement where the combined engine produced none.
- The regime filter is not removing everything, contrary to the first run: it keeps 79 of 405 and 47
  of 562.

**Does not:**

- **Say the conditions are wrong in principle** — only that these four, at these thresholds, on this
  half of this month, do not beat their null.
- Touch the held-out half, or any of the other 18 months.
- Settle the filtered exhaustion arm, which needs ~2.5 years of tape to call either way.
- Choose anything about Gate 1's option (b). Restoring condition A remains open and would land in the
  one arm whose sign is positive.
