# M3 — the clock profile, measured. And what four wrong answers cost.

**Run 2026-09-06 by `m3_profile.py`, on all 19 months.** Step 3 of
[`docs/strategy/ARCHITECTURE.md`](../../../docs/strategy/ARCHITECTURE.md) §6; the clock lane of
[`plans/team/strategy-split.md`](../../../plans/team/strategy-split.md). Pre-commitments in
[`prathamesh/clock-lane.md`](../../../plans/team/prathamesh/clock-lane.md) and
[`strategy-precommit.md`](../../../plans/team/strategy-precommit.md) §4–§7, all committed before
any of this ran.

```sh
PYTHONPATH=. uv run python m3_profile.py                       # long,  stop 1.0x ATR
PYTHONPATH=. uv run python m3_profile.py --side -1             # short
PYTHONPATH=. uv run python m3_profile.py --stop-atr 1.5        # and at 1.5x
```

**107,359 legs · 19 months · Jan 2025 – Jul 2026 · both sides · both halves of the split.**
Bracket **3.0× / 1.0× ATR at 30m**, both points on Varad's committed M1 grid (`strategy-precommit.md`
§1). Buckets are `ATR_BP_EDGES = (0, 7, 10, 14, ∞)`, Varad's committed edges, imported not chosen.

---

## 1. The verdict

**The clock conditions volatility. It does not produce edge. No phase clears cost.**

EV per leg, `+3.0` on target, `−1.0` on stop, and **the realized move at the horizon on neither**
(§4 — getting that wrong is what produced this file's second wrong answer). `sym` is the mean of the
two sides, which is the only figure M3 is entitled to quote: it is a non-directional strategy.
Cost is 1.40 ticks round trip, `FAMILIES.md`'s convention. 1 ATR = **38.89 ticks** at the archive's
median price of $4,029.60.

| phase | n | p_tgt L | p_stp L | p_nei L | EV L | EV S | **sym** | sym ticks | **EV−cost** |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Asia` | 36,956 | 0.0709 | 0.4958 | 0.4334 | +0.0162 | +0.0132 | **+0.0147** | +0.572t | **−0.828t** |
| `Asia-London` | 4,884 | 0.0706 | 0.5070 | 0.4224 | +0.0359 | −0.0313 | **+0.0023** | +0.089t | **−1.311t** |
| `London` | 24,420 | 0.0705 | 0.5162 | 0.4133 | −0.0143 | +0.0038 | **−0.0052** | −0.204t | **−1.604t** |
| `London-NY` | 7,333 | 0.1049 | 0.5989 | 0.2962 | −0.0182 | +0.0352 | **+0.0085** | +0.331t | **−1.069t** |
| `NY` | 19,539 | 0.0503 | 0.4795 | 0.4702 | −0.0058 | −0.0012 | **−0.0035** | −0.137t | **−1.537t** |
| `NY-Asia` | 14,227 | 0.0474 | 0.4360 | 0.5166 | +0.0099 | +0.0087 | **+0.0093** | +0.362t | **−1.038t** |
| **all** | **107,359** | | | | +0.0030 | +0.0073 | **+0.0051** | +0.200t | **−1.200t** |

The best cell on the board is `Asia` at **+0.572 ticks against a 1.40-tick cost**. It clears 41% of
its own cost. **Varad's written prediction — "no cell clears the cost floor" — holds.**

Aggregate EV of +0.0051 ATR is a rounding error from zero, which is what `horizon.py` measured GC to
be and what `ohlcv_edge.py` reproduced on spot to within 0.4%.

### 1.1 A wider stop makes it worse

| | mean `p_target` | mean `p_stop` | EV long | EV short |
| :--- | ---: | ---: | ---: | ---: |
| stop **1.0×** | 0.0691 | 0.5056 | +0.0030 | +0.0073 |
| stop **1.5×** | 0.0755 | 0.3396 | +0.0010 | +0.0052 |

`p_stop` falls by a third; `p_target` barely moves; each stop now costs 1.5×. **The binding
constraint is the target, not the stop** — 3× ATR over 30 minutes is ~1.2σ of expected displacement,
and loosening the stop does not make it reachable. Every symmetric phase number shrinks.

---

## 2. What the phase axis actually measures

The reach lift is real and it does not convert.

`London-NY` has the **highest `p_target` on both sides** (0.105 long / 0.141 short) and the **worst
long EV on the board** (−0.0182). Because it also has the highest `p_stop` (0.599) and the lowest
`p_neither` (0.296). Both barriers get hit more. Nothing favours a direction — **the bracket simply
resolves faster.**

The mechanism is `atr_bp`'s window, which is **trailing** 60 minutes:

- At 08:00 ET that window covers quiet late-London, so a bracket sized off it is **too small** for
  the 08:30 release and the 09:30 NY open that follow. Everything resolves. `p_neither` collapses.
- At 13:30 ET the window covers the busy NY session, so the bracket is **too big** for the fading
  afternoon. `NY-Asia` carries the highest `p_neither` on the board, 0.517.

**So the phase profile is one statement: trailing ATR systematically mis-estimates forward
volatility in a time-of-day-dependent way.** That is volatility seasonality, not edge. It explains
why the effect is symmetric across sides, why it survives the split, and why it yields no EV.

**This is a positive result for the architecture and a negative one for the strategy.** `reach.py`'s
bucket key is `(instrument × atr_bp × phase × vol_state × side)`, and this is the measurement that
says *why* `phase` has to be in there: `atr_bp` alone mis-predicts forward volatility, in a stable,
direction-free, split-surviving way. M3 is a **bracket-conditioning input for stage 7, not an entry
filter.**

## 3. The reach profile, for the record

Lift vs the ATR- and side-matched null, ✓ = clears its own `mde_rate`.

**`London-NY` — positive in 15 of 16 cells, clearing MDE in 14.** The one negative is an n=50 cell
whose MDE is 0.128, so it has no power to see anything, and its short-side twin is positive.

| bucket | n (train/held) | L train | L held | S train | S held |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `<7` | 441 / 50 | **+0.0868** ✓ | −0.0294 | **+0.1376** ✓ | +0.0697 |
| `7–10` | 1175 / 537 | **+0.0697** ✓ | **+0.0908** ✓ | **+0.0723** ✓ | **+0.0697** ✓ |
| `10–14` | 1031 / 1316 | **+0.0347** ✓ | **+0.0614** ✓ | **+0.0536** ✓ | **+0.0768** ✓ |
| `14+` | 827 / 1956 | **+0.0270** ✓ | **+0.0164** ✓ | **+0.0435** ✓ | **+0.0384** ✓ |

`NY-Asia` mirrors it — negative in 15 of 16, visible in 11. `Asia`, `Asia-London` and `London` flip
sign between halves and are dead. `NY` is weakly negative (13/16) with 4 visible cells.

**⚠️ Read every MDE here as a floor, and the margin is thinner than the ✓s suggest.** Entries are
every bar, so at 5-minute bars with a 30-minute horizon **six consecutive legs overlap** and the
effective sample is well below `n` — `horizon.mde_rate`'s own docstring says so. Under a ~6×
effective-N haircut (MDE × ~2.45), `London-NY` still survives in `7–10` and `10–14` on both sides;
**`NY-Asia` mostly does not** and should be read as suggestive.

### 3.1 The event arm

`±15m` around a BLS or FOMC release is **positive in 14 of 16 cells**, visible in 6, including the
held half's two best-powered cells on both sides (n=56: +0.2403 long; n=100: +0.0923 long /
+0.1637 short). Same mechanism as `London-NY`, in its purest form: ATR is measured *before* a
scheduled release, so the bracket is sized to pre-release calm. **Mechanically guaranteed, not an
edge.** Cell counts are 27–100, so nothing here is strong on its own.

### 3.2 The tie band is empty **at this bracket, and only at this bracket**

Every table above was computed under **both** tie conventions, `reach_table`'s rule — report the
pair, never the midpoint. Bands came out **0.001–0.010 ATR wide, and zero on most single months.**

**⚠️ Corrected 2026-09-06, same day, after Varad's `1024b46`.** This section first said the result
"removes the tie-resolution argument for tick replay" and that step 5's case rests on M4 alone.
**That was an overstatement drawn from one bracket, and it is wrong.** A same-bar tie needs one bar
spanning `target + stop`, so its frequency is a property of the *bracket*, not of the tape. Measured
on 2026-07, 6,161 bars, median bar range 0.90 ATR:

| bracket | width | bars that could tie |
| :--- | ---: | ---: |
| 0.75× / 0.5× | 1.25 ATR | **20.45%** |
| 1.0× / 0.5× | 1.50 ATR | 10.79% |
| 1.5× / 0.75× | 2.25 ATR | 1.79% |
| 2.0× / 1.0× | 3.00 ATR | 0.44% |
| **3.0× / 1.0×** *(M3's)* | 4.00 ATR | **0.13%** |
| 4.0× / 1.5× | 5.50 ATR | 0.03% |

**M3 sits at the far end where ties are negligible. M1's committed grid spans the near end, where
one bar in five can tie** — which is why `strategy-precommit.md` §1 keeps the ×2 tie-band pass, and
it is right to.

So the honest statement: **the tie band is empty for a 3:1 bracket and is the dominant uncertainty
for a 1.5:1 one.** `first_touch`'s docstring — the band is widest "where the stop is tight relative
to the bar range" — is confirmed rather than retired, and **the tie-resolution argument for
`replay.py` stands** for the tight half of M1's grid. Step 5's budget should not be shrunk on the
strength of M3's geometry.

---

## 4. The run history — four answers, three of them wrong

Recorded because the corrections are more instructive than the result, and because anyone reading
the earlier three in the daily update needs to know they are void.

| # | Config | Why it ran | What I concluded |
| :--- | :--- | :--- | :--- |
| 1 | long, **70/20 ticks** | first run | "`NY-Asia` is the finding; `London-NY` fails; event arm dead" ❌ |
| 2 | short, 70/20 ticks | **planned** — a long-only `p_target` cannot support a non-directional claim | "`NY-Asia` negative both sides" ❌ |
| 3–4 | both sides, **3.0×/1.0× ATR** | **bug: bracket units** | "`London-NY` is the finding; event arm alive" ✅ reach, ❌ EV |
| 5–8 | both sides × stop 1.0×/1.5×, with tie band | **bug: EV of an unresolved leg**, + stop sensitivity | **this file** |

### The numbers, so the claims above can be checked rather than believed

**Bug 1 was visible in run 1's own output.** The bucket null should mean the same thing in both
halves of the split. Under a fixed tick bracket it does not; under an ATR bracket it does:

| bucket | run 1 train | run 1 held | | run 3 train | run 3 held |
| :--- | ---: | ---: | :-- | ---: | ---: |
| `<7` | 0.0360 | **0.1088** | ← 3.0× | 0.0833 | 0.0894 |
| `7–10` | 0.0825 | **0.1624** | ← 2.0× | 0.0614 | 0.0731 |
| `10–14` | 0.1316 | **0.1874** | ← 1.4× | 0.0458 | 0.0632 |
| `14+` | 0.1935 | 0.1992 | | 0.0419 | 0.0577 |

**And here is what actually changed between the runs, which is less than §4 first said.** Cells of 8
(4 buckets × 2 halves), per run:

| phase | | run 1 (L, ticks) | run 2 (S, ticks) | run 3 (L, ATR) | run 4 (S, ATR) |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `London-NY` | sign positive | 6/8 | 7/8 | 7/8 | **8/8** |
| | clears MDE | 3/8 | 4/8 | **7/8** | **7/8** |
| `NY-Asia` | sign negative | 7/8 | 8/8 | 7/8 | **8/8** |
| | clears MDE | 4/8 | 3/8 | 5/8 | 6/8 |

**⚠️ Correction to this section's own framing, 2026-09-06.** It first said fixing the bracket
"inverted which phase was the finding". **The table says otherwise, and it is the better witness.**
Both phases held their sign in *every* run — `NY-Asia` negative in 7–8 of 8 throughout,
`London-NY` positive in 6–8 of 8 throughout. What the fix changed is **statistical visibility**:
`London-NY` went from 3/8 and 4/8 cells clearing MDE to 7/8 and 7/8, overtaking `NY-Asia`, which
barely moved.

So the inversion was **in my reading, not in the data.** The underlying profile was stable across
all four runs; a mis-scaled bracket suppressed the power to see the larger of the two effects, and I
reported whichever looked significant at the time as "the finding". That is a worse error than a
number changing, because nothing in the run-1 output looked wrong — the direction was already right.

**Reproducing runs 1–4:** `git checkout b6f3c68~1 -- services/signal-data/m3_profile.py` for the
fixed-tick version, or pass `--stop-atr`/`--target-atr` for the geometry. Raw stdout from the
superseded runs was session-local and is not in the repo; the tables above are the extract that
mattered.

### Bug 1 — bucketing in basis points, bracketing in fixed ticks

Runs 1–2 bucketed by `atr_bp` while passing a fixed **70/20 tick** bracket to `first_touch`. Gold
ran 2,624.60 → 5,626.80 over the archive, so 70 ticks meant ~25.6 bp at the start and ~13.9 bp at
the end: **the target got mechanically easier as the archive ran.**

It was visible in the output and misread as a market fact — the `<7` bucket's null moved
**0.0360 → 0.1088** across the split halves. Same bucket label, 3× the reach rate.

**This is ARCHITECTURE §4.6's error exactly**, committed in the file whose job is to prevent it:
*"a mis-scaled bucket silently pools two different populations and reports the average as a base
rate."*

**What it changed:** everything. Fixing it **inverted which phase was the finding** (`NY-Asia` →
`London-NY`) and moved the event arm from dead to alive. A fixed target made high-ATR bars trivially
reachable and low-ATR bars nearly unreachable, so the ATR bucket dominated the outcome and the phase
signal was distorted through it. With an ATR-relative target the null flattens to ~0.06–0.09 in every
bucket, and what is left is the phase effect.

**Fix:** the bracket is resolved from ATR, once per (month × bucket). Per-bucket and not per-trade
because `first_touch` takes one scalar bracket and giving it a per-trade array is a shared-spine
change — Varad's, `strategy-split.md` §2. Inside one bucket in one month the ATR is near-constant by
construction.

### Bug 2 — pricing an unresolved leg at zero

Runs 3–4's EV counted `+3` on a target and `−1` on a stop and **0 on `neither`**. `neither` is 43%
of all legs and it is not neutral: **a leg that survived 30 minutes without touching a stop one ATR
away survived *because* it drifted the right way.** Pricing those at zero charges the strategy for
every stop and credits it for no part of the paths that quietly worked.

**What it changed:** EV went from **−0.28 ATR to +0.05 ATR** — from "every phase loses badly" to
"roughly zero, slightly positive". The conclusion reversed completely.

`evaluate` had already computed the realized move at the horizon. It simply was not carried.

**The check that would have caught it immediately:** `horizon.py` measured GC as a random walk and
`ohlcv_edge.py` reproduced that on spot to within 0.4%, so **EV must come out ≈ 0**. −0.28 ATR per
leg contradicted a result this repo already had. That is now the first thing to check on any number
this pipeline produces.

### The common root

Both bugs are the same shape: **every component correct in isolation, wrong in composition.**
`atr_bp` returns bp; `first_touch` takes ticks; `first_touch` returns `0` for an open position.
None of that is wrong, and nothing forced the three to agree.

The decision underneath was writing a new driver instead of extending `base_rates.py`, which already
had bucket and bracket **in the same unit** (ticks with tick edges). Switching the bucket to bp and
leaving the bracket in ticks broke an invariant that file had been holding silently.

**Cost:** ~25 minutes of local compute, **$0** — no data re-pulled, nothing committed, no wrong
number reached a plan file. The expensive part was four conclusions delivered in sequence.

---

## 5. Kill condition, answered

`strategy-precommit.md` §4 pre-committed what would make the phase axis dead:

> No phase's `p_target` separates from the ATR-matched, side-matched null by more than that cell's
> own `mde_rate`, on both halves of the split.

**By that test the phase axis is NOT dead.** `London-NY` clears MDE in 14 of 16 cells across both
halves and both sides, and survives an overlap haircut in the middle buckets.

**But the pre-committed test turns out to have been the wrong test**, and that is worth recording
rather than quietly upgrading. It asks whether the clock moves `p_target`. It does. It does not ask
whether the movement is *worth anything*, and it is not: `London-NY`'s reach lift is paid for
exactly by its stop rate.

**A kill condition for the next thing in this lane must be stated in EV net of cost, not in
`p_target` against a null.** Reach is a property of the bracket; EV is the property of the trade.

## 6. What is still open

- **M1's sweep decides whether any geometry has positive EV at all.** Everything here is one point,
  3.0×/1.0× at 30m. A conditioning axis is only worth having on top of a bracket that makes money.
- **A directional pattern this run is not entitled to claim.** `London-NY` runs −0.018 long /
  +0.035 short and `Asia-London` runs +0.036 long / −0.031 short — large, opposite, and *growing*
  with a wider stop. That is the shape of an intraday drift pattern over a period when gold rose
  84%. **M3 is non-directional and its null controls for side but not for time-of-day drift.** It
  needs its own experiment and its own null; it is not a finding from this one.
- **The second instrument.** Every feature used here is portable by construction, so the whole
  profile re-runs on spot XAUUSD the day a vendor exists. That is the strongest available check on
  all of the above, and it is still step 6.
