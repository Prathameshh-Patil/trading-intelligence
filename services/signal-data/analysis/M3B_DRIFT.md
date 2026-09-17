# M3b — there is no time-of-day drift, and the period's own drift does not cover a round trip

**Run 2026-09-17 · `m3b_drift.py` · 18,244 disjoint 30-minute windows, 19 months, GC**
**Pre-commitment: [`strategy-precommit.md`](../../../plans/team/strategy-precommit.md) §12, committed before the first line of code**

---

## 1. The verdict

**Outcome 1 fires. Zero of six phases clear the cost floor on the residual, and the pattern
`M3_CLOCK.md` §6 logged on 6 Sep is retired.** It is not a clock effect.

```
18,244 disjoint 30m windows, 19 months
POOLED drift   +0.1878 bp per window   <- the period's own drift, every phase inherits it
cost floor      0.3504 bp round trip

                n   mean_bp  resid_bp   se_bp   cost_bp      t   edge_lo  clears
Asia         6508    0.2909    0.1031  0.2621    0.3508   0.39   -0.4210   False
Asia-London   814    0.9794    0.7916  0.6423    0.3510   1.23   -0.4930   False
London       4070    0.2463    0.0585  0.3004    0.3498   0.19   -0.5423   False
London-NY    1223   -0.2992   -0.4870  0.8082    0.3502  -0.60   -1.1295   False
NY           3257   -0.2538   -0.4416  0.4887    0.3499  -0.90   -0.5359   False
NY-Asia      2372    0.3902    0.2024  0.3780    0.3504   0.54   -0.5536   False
```

**The core of §12's reasoning held, and it is the finding.** The entire unconditional drift of the
period — **+0.1878 bp per 30 minutes — is barely half the round-trip cost of 0.3504 bp.** Before any
phase is examined, the whole bull market cannot pay for the trade that would capture it. A phase's
*share* of that drift is smaller again, so there was never room for a clock effect to clear cost.

## 2. The signs replicate. The magnitudes do not.

⚠️ **This is the part worth reading carefully, because it is the one that could be over-read.**
M3's numbers imply `London-NY` negative and `Asia-London` positive. **Measured in plain forward
returns, that is exactly what comes back:**

| Phase | M3 implied | M3b measured | t |
| :--- | ---: | ---: | ---: |
| `London-NY` | ≈ −0.027 ATR | **−0.4870 bp** | −0.60 |
| `Asia-London` | ≈ +0.034 ATR | **+0.7916 bp** | +1.23 |

**The direction reproduces through a completely different instrument — no bracket, no barriers, no
`evaluate`.** That is not nothing, and a write-up that said "the pattern vanished" would be wrong.

**But no phase reaches even t = 1.25, and the largest residual's two-sigma lower bound is −0.49 bp**
— below zero, let alone below cost. **A sign that replicates at t < 1.3 over 19 months is what
noise looks like when you go looking for it in the direction you already expect.**

⚠️ **And the two phases M3 flagged are the two THINNEST in the table** — `Asia-London` at 814
windows and `London-NY` at 1,223, against `Asia`'s 6,508. They are the two **transition** phases,
which is the same thinness `REACH.md` found when both of them lost their entire CONTRACTING state
(16 of 28 dead cells). **The largest apparent effects sit exactly where the standard errors are
largest**, which is the ordinary way a thin cell produces an interesting-looking number.

## 3. A published number is wrong: gold rose 55.2%, not 84%

`M3_CLOCK.md` §6 describes *"a period when gold rose 84%"*, and §12 inherited that figure and built
its arithmetic on it. **Measured from the archive itself, first close to last:**

```
2025-01 first close   2,640.40
2026-07 last close    4,098.60        +55.2%   (log 0.4397)
```

**55.2%, not 84%.** The 84% is not this archive's span. §12's predicted 0.33 bp/window came from
dividing the wrong rise; the corrected figure is **0.241 bp/window**, which is much closer to the
0.1878 measured — **so the prediction's arithmetic was carrying someone else's error, and correcting
it moves the estimate toward the measurement rather than away.**

**The remaining difference is gaps, and excluding them is correct.** In-window drift totals log
0.3426 against the archive's log 0.4397, so **78% of the rise happened inside tradeable 30-minute
windows and 22% happened in the weekend and session-break gaps this file drops by construction.**
A 30-minute intraday window cannot capture a weekend jump, so counting it would price an untradeable
move into a tradeable claim.

## 4. What was built, and the two ways it refuses to lie

`m3b_drift.py`, 134 lines, six tests, no network.

- **Returns, not brackets.** A bracket confounds direction with volatility — the `atr_bp`
  quiet-hour artefact now found independently by `M1_SURFACE.md` §3, `M3_CLOCK.md` §2 and
  `REACH.md`. Asking a drift question through a bracket asks a bracket question again.
- **Disjoint windows, with an elapsed-time check.** `resample_bars` drops empty bars, so six bars is
  *not* always thirty minutes. A window whose ends are not exactly one horizon apart spans a weekend
  or a session break and is dropped. **Mutation-verified:** removing that filter turns two tests red.
- **The pooled mean is subtracted**, which is the null M3 said it did not have. **Mutation-verified:**
  a +5 bp drift applied to *every* phase must produce zero residual, and removing the subtraction
  turns that test red.

⚠️ **Honest limit on the standard errors.** They treat the windows as independent. Disjointness
removes the overlap, but volatility clustering and day-of-week effects are not controlled, so the
true errors are likely *larger* than these. **That direction makes "nothing clears" more robust, not
less** — a wider error bar cannot rescue a residual whose lower bound is already negative. The `se`
also treats the pooled mean as known, which is mildly conservative here (naive minus true variance
is `(2σ_p² − σ²)/N`, positive while phase variances are comparable).

## 5. What this closes and what it does not

✅ **Closes `M3_CLOCK.md` §6's open item.** *"It needs its own experiment and its own null"* — it has
both now, and the answer is that there is no time-of-day drift worth controlling for. **M3's
non-directional framing stands unchallenged**, and no strategy slot is owed.

❌ **Does not license a directional claim in either direction.** Outcome 2 did not fire.

❌ **Does not revisit `M3_CLOCK.md`'s per-side numbers.** Outcome 3 — the sign coming back *opposite*
to M3's, which would have meant the bracket produced the asymmetry — **did not fire**. The signs
agree, so nothing sends work backwards.

⚠️ **One instrument, one period, in sample.** `xauusd-regimes.md`'s standing warning applies: a
drift measured over a period gold rose 55% is a statement about that period. The cross-instrument
check is still route 2, and route 2 is still blocked on a vendor.

**`backtest.py`, `m3_profile.py`, `m1_sweep.py` and the served table are untouched.** M3b measures.
