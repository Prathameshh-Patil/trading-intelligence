# planfortoday.md — W0D2 → W0D3 (Thu Aug 27 → Fri Aug 28)

**Goal:** Build the first 70-tick capture signal on 5-minute GC data using the existing Python stack.  
**Horizon:** 5 minutes (confirmed by `horizon.py` analysis).  
**Target:** 70 ticks with 20-tick stop (3.5:1 R/R, break-even at 23% win rate).  
**Data:** `analysis/regimes/regime_labels_window_5min_k3.csv` (already carries OHLC + delta + volume + CVD + session).

---

## ✅ Prerequisites (already done)

| Item | Status | Location |
|------|--------|----------|
| Horizon decision | ✅ | `services/signal-data/horizon.py` — 5m wins |
| Leg truncation fix | ✅ | `services/signal-data/backtest.py:47` |
| Test suite | ✅ | 72 tests, ruff/mypy clean |
| Regime labels | ✅ | `analysis/regimes/regime_labels_window_5min_k3.csv` |
| Strategies scaffold | ✅ | `strategies.py`, 27 tests green |

---

## 🔴 Blockers before any signal code

### 1. Part B — Thresholds (`services/signal-data/thresholds_selector.md` §9)

**What:** Four rules in `strategies.py` have no defaults. The file raises `TypeError` until Part B exists.  
**Why it blocks:** You cannot run a backtest without threshold defaults.  
**Action today:**
- [ ] Open `services/signal-data/thresholds_selector.md`
- [ ] Author Part B: default thresholds for the four scaffolded rules
- [ ] Derive them from July 2026 data (not guessed)
- [ ] Commit with message: `feat(signal-data): Part B thresholds from July 2026 fixture`

> **Rule from §9 Q1:** A threshold picked by an assistant isn't a commitment by the person with the bias.  
> → Draft the numbers, flag them for standup review, but unblock the backtest.

### 2. Standup note (horizon + 'N' amendment)

**What:** Two decisions queued for Wednesday's standup:
1. **Horizon call** — 5 minutes is measured and recommended. Needs team yes/no.
2. **'N' amendment** — 1,811 trades (2.34%) carry aggressor_side 'N'. S1 declares third value 'B' | 'A'. Frozen contract needs all three signatures.

**Action today:**
- [ ] Draft standup note in `daily_updates/2026-08-27.md` covering both items
- [ ] Tag Shreyas and Prathamesh for review

---

## 🏗️ Layer 1: MARKET DATA (no new work — reuse existing)

**Source:** `analysis/regimes/regime_labels_window_5min_k3.csv`  
**Columns available:** `open`, `high`, `low`, `close`, `delta`, `volume`, `cvd`, `session`

**Action today:**
- [ ] Verify the CSV loads cleanly into Polars:
  ```python
  import polars as pl
  df = pl.read_csv("analysis/regimes/regime_labels_window_5min_k3.csv")
  assert set(df.columns) >= {"open","high","low","close","delta","volume","cvd","session","timestamp"}
  ```
- [ ] Add `timestamp` parsing if missing (the file may not have a parsed datetime column)

---

## 🏗️ Layer 2: REGIME FILTER (Stage 1 — kill gate)

**What:** Only trade when the 5-minute regime has ≥92% survival and volatility is elevated.

**Files to create:**
```
services/signal-data/
├── features/
│   ├── __init__.py
│   └── regime_filter.py
```

**Action today:**
- [ ] Create `features/regime_filter.py` with:
  - `regime_survival_5m` check (≥0.92) — already in CSV
  - `volatility_gate`: `ATR(14) > 15 ticks` AND `range > 1.2 × ATR`
  - `spread_filter`: skip first/last 5 minutes of session (open/close chaos)
  - `trend_alignment`: price vs 15-period EMA (trade with trend only)
- [ ] Write tests for each gate condition
- [ ] Run on July 2026 data and report: *"X of 6,276 bars pass the regime filter"*

---

## 🏗️ Layer 3: SIGNAL ENGINE (Stage 2 — 3-of-4 conditions)

**What:** Detect the *start* of a 70-tick impulse using order-flow microstructure.

**Files to create:**
```
services/signal-data/
├── features/
│   ├── orderflow.py      # delta, CVD, absorption, VWAP
│   └── expansion.py      # ATR, range, volatility regime
├── signals/
│   ├── __init__.py
│   └── engine.py         # 3-of-4 condition checker
```

### Condition A — Absorption
- Volume cluster > 2σ
- Body < 30% of range (indecision bar)
- Price at or near a key level (VWAP, prior session H/L)

### Condition B — Delta Divergence
- Price makes lower low, delta makes higher low (selling exhaustion)
- Delta slope turns positive

### Condition C — CVD Momentum Shift
- CVD slope breaks its 5-bar trend
- CVD EMA crosses above zero (long) or below (short)

### Condition D — Range Expansion
- Current bar range > 1.5 × ATR(14)
- Body > 60% of range (strong directional close)

**Action today:**
- [ ] Implement `features/orderflow.py` (delta, CVD, absorption, VWAP)
- [ ] Implement `features/expansion.py` (ATR, range, volatility)
- [ ] Implement `signals/engine.py` — requires 3 of 4 conditions + regime filter pass
- [ ] Write unit tests for each condition in isolation
- [ ] Run on July 2026 data and report:
  - Total signals generated
  - Breakdown by condition combination (A+B+C, B+C+D, etc.)
  - Signals per session (watch for clustering/bursting)

---

## 🏗️ Layer 4: RISK & EXECUTION (MFE/MAE tracker)

**What:** Don't backtest with fixed exits. Ask: *"After entry, did price ever reach +70 ticks before hitting -20 ticks?"*

**Files to create:**
```
services/signal-data/
├── analysis/
│   └── mfe_mae.py        # "Did it hit 70 ticks?" tracker
```

**Exit rules for measurement:**
- Stop: 20 ticks (hard)
- Target 1: 35 ticks (50% position)
- Target 2: 70 ticks (50% position, trail stop -10 ticks after 35)
- Time stop: 15 minutes (3 bars)

**Action today:**
- [ ] Implement `analysis/mfe_mae.py`:
  - For each signal, look forward 30 bars (30 minutes max hold)
  - Track MFE (max favorable excursion in ticks)
  - Track MAE (max adverse excursion in ticks)
  - Record `hit_70` boolean
  - Record `time_to_70` (how many bars)
- [ ] Run on July 2026 signals and report:
  - `hit_70_rate` (% of signals that reached 70 ticks)
  - `avg_mfe` / `avg_mae`
  - `avg_mfe_mae_ratio`
  - Distribution of `time_to_70` (most hit in 1–3 bars? 10+?)

**Decision gate:**
- If `hit_70_rate` ≥ 25% → proceed to Layer 5 (threshold tuning)
- If `hit_70_rate` < 20% → tighten conditions or add a 5th filter
- If `hit_70_rate` < 15% → revisit signal logic (conditions may be wrong)

---

## 🏗️ Layer 5: POST-TRADE FEEDBACK (threshold tuning)

**What:** Use MFE/MAE results to pick thresholds that maximize `hit_70_rate` per signal, not per bar.

**Files to modify:**
```
services/signal-data/
├── thresholds_selector.md   # Part B completion
```

**Action today (if Layer 4 shows promise):**
- [ ] Grid-search thresholds for each of the 4 conditions
- [ ] Optimize for: `hit_70_rate × signals_per_month` (not just win rate)
- [ ] Record the delta error bar (~15–20% from your document) — thresholds inherit this uncertainty
- [ ] Write results to `daily_updates/2026-08-28.md`

---

## 📋 Today's Commit Checklist

```bash
# 1. Start from clean tree
git status  # should be clean after yesterday's d458434

# 2. Create feature files
git add services/signal-data/features/
git add services/signal-data/signals/
git add services/signal-data/analysis/

# 3. Update tests
git add tests/test_regime_filter.py
git add tests/test_signals_engine.py
git add tests/test_mfe_mae.py

# 4. Update docs
git add services/signal-data/thresholds_selector.md
git add daily_updates/2026-08-27.md
git add daily_updates/2026-08-28.md

# 5. Commit
git commit -m "feat(signal-data): 70-tick signal engine, regime filter, MFE/MAE tracker

- Layer 2: regime filter (5m survival ≥92%, ATR gate, spread filter)
- Layer 3: 3-of-4 signal engine (absorption, delta div, CVD shift, range exp)
- Layer 4: MFE/MAE analysis for 70-tick target, 20-tick stop
- Part B thresholds drafted from July 2026 fixture
- 72 + N tests, ruff/mypy clean"
```

---

## ⚠️ Hard Constraints (do not violate)

| Constraint | Rule |
|------------|------|
| **No n8n agents** | Trading logic stays in Python. n8n is for Slack alerts only. |
| **No Lyzr** | Zero external agent orchestration. Pure Polars + sklearn. |
| **No LLM reasoning** | Thresholds come from data, not from a model's guess. |
| **5m only** | 30m is rejected. Do not add 30m logic. |
| **One month, one instrument** | July 2026 GC only. Do not generalize yet. |
| **Delta error bar** | Carry the ~15–20% session-total delta uncertainty into threshold selection. |

---

## 🎯 Definition of Done for Today

- [ ] Part B thresholds drafted and unblocking `strategies.py`
- [ ] `features/regime_filter.py` + tests passing
- [ ] `features/orderflow.py` + `features/expansion.py` implemented
- [ ] `signals/engine.py` generating signals from July 2026 data
- [ ] `analysis/mfe_mae.py` reporting `hit_70_rate` and `avg_mfe_mae_ratio`
- [ ] Standup note drafted (horizon + 'N' amendment)
- [ ] `daily_updates/2026-08-28.md` written with today's numbers
- [ ] All code committed to main (or PR if team requires review)

---

## 📊 Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| `hit_70_rate` | ≥ 25% | At 3.5:1 R/R, 25% win rate = +12.5% expectancy per trade |
| `avg_mfe_mae_ratio` | ≥ 2.0 | Structural edge even if win rate is noisy |
| Signals per month | 50–150 | Enough for statistical power, not so many that overlap kills you |
| Regime filter pass rate | 15–25% of bars | If >50%, filter is too loose. If <5%, too tight. |

---

## 📝 Notes

- The 421 duplicate rows (identical timestamps, up to 6 copies) are **not** today's problem. They are a hygiene decision for standup. Do not let them block signal development.
- The 'N' amendment is a contract issue, not a code issue. Flag it, don't fix it unilaterally.
- Prathamesh's parquet is **not needed** for today's work. The CSV has everything.
- If you get stuck on a condition (e.g., absorption detection), stub it with `return False` and move on. Come back with MFE/MAE data to see if it mattered.
