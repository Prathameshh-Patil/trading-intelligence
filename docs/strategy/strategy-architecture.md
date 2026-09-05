# L1-Only Gold Trading System: Alternative Architecture

**Technical Specification v1.0**
**Date:** 2026-09-05 · **Constraint:** Spot XAUUSD + GC Futures · **Data:** L1 Only

---

## 1. Executive Verdict

The original four-strategy proposal ([`xauusd-regimes.md`](xauusd-regimes.md)) fails on three counts:

- Three strategies require order flow (unavailable on spot XAUUSD)
- Pattern recognition is statistically underpowered (~2,500 H4 bars)
- No pre-committed nulls → unfalsifiable claims

This alternative proposes four strategies that:

- Run entirely on L1 data (price, spread, quote rate, time)
- Predict magnitude distributions, not direction
- Are falsifiable with pre-committed thresholds and kill conditions
- Focus on avoiding negative EV rather than finding alpha

---

## 2. The Four Strategies: Complete Specification

### S1: Adverse Selection Filter (ASF)

**Core hypothesis:** When market makers widen spreads, they price in informed flow. Trading into wide spreads = adverse selection. Trading into tight spreads with elevated quote rate = liquidity surplus.

**Feature engineering:**

```python
# Portable L1 features
spread_z = (current_spread - rolling_median_spread) / rolling_std_spread
quote_rate_z = (quotes_per_minute - median_rate) / std_rate

# Composite liquidity score
liquidity_score = (1 / spread_z) * max(0, quote_rate_z)
```

**Entry conditions (pre-committed):**

| Parameter | Value | Rationale |
| :--- | ---: | :--- |
| `spread_z_max` | 1.5 | Top ~7% of spreads filtered |
| `spread_z_min` | 0.3 | Avoid stale quotes |
| `quote_rate_z_min` | -0.5 | Must have some activity |
| `liquidity_score_threshold` | 0.8 | Composite filter |

**Signal generation:**

```
IF spread_z < 1.5 AND spread_z > 0.3
   AND quote_rate_z > -0.5
   AND liquidity_score > 0.8:
    SIGNAL = ALLOW_TRADE
ELSE:
    SIGNAL = BLOCK_TRADE
```

**Edge cases & handling:**

| Edge case | Detection | Action |
| :--- | :--- | :--- |
| Spread spike at news | `spread_z > 3.0` in 1 bar | Block for 10 minutes |
| Quote rate collapse | `quote_rate_z < -2.0` | Block, flag feed issue |
| Spread compression (tightening) | `spread_z < 0.2` | Block (stale quote risk) |
| Weekend/rollover | Time-based | Auto-block, manual override |
| Cross-instrument divergence | GC spread ↑, spot spread ↓ | Prefer GC, flag arb |

**Kill condition:** if `p_target | ALLOW ≤ p_target | BLOCK + MDE(null, n_allow)`, drop S1 and report negative result.

### S2: Volatility Momentum (VM)

**Core hypothesis:** Volatility clusters (GARCH effect). Realized vol slope predicts future move magnitude better than static ATR.

**Feature engineering:**

```python
# Realized volatility (Parkinson, 5-minute)
rv_5m = sqrt((1/(4*N*ln(2))) * sum((ln(high_i/low_i))^2))

# Volatility trend (3-bar slope)
rv_slope = (rv_5m[t] - rv_5m[t-3]) / 3

# Vol regime classification
if rv_slope > 0.3 * rv_5m:   regime = "EXPANDING"
elif rv_slope < -0.3 * rv_5m: regime = "CONTRACTING"
else:                         regime = "STABLE"
```

**Conditional bracket sizing:**

| Vol regime | ATR bucket | Recommended bracket | Rationale |
| :--- | :--- | :--- | :--- |
| EXPANDING | 30–40bp | (100, 25, 45m) | Vol underestimates |
| EXPANDING | 40–50bp | (120, 30, 60m) | Large moves likely |
| STABLE | 30–40bp | (70, 20, 30m) | Base case |
| STABLE | 40–50bp | (90, 25, 40m) | Moderate extension |
| CONTRACTING | Any | NO TRADE | Vol overestimates |

**Magnitude prediction output:**

```python
def predict_reach_table(rv_slope, atr_bucket, session_phase):
    """
    Returns P(reach T before S) for all (T,S) pairs
    Conditioned on vol momentum, not just static vol
    """
    base_table = get_base_rates(atr_bucket)
    vol_multiplier = 1.0 + (rv_slope / rv_5m) * 0.3  # Pre-committed

    return adjust_table(base_table, vol_multiplier)
```

**Edge cases:**

| Edge case | Detection | Action |
| :--- | :--- | :--- |
| Vol spike without continuation | `rv_slope` reverses in 2 bars | Revert to base bracket |
| News-induced vol | Time-of-day check (08:30) | Widen stops, reduce size |
| Vol collapse | `rv_5m < 5bp` for 10 bars | Block, wait for expansion |
| Cross-instrument vol arb | GC rv ↑, spot rv ↓ | Trade GC only |

**Kill condition:** if vol regime adds <3 points to `p_target` vs. ATR-only conditioning at 80% power, drop VM and use static ATR bucketing only.

### S3: Session Microstructure Edge (SME)

**Core hypothesis:** Gold's three-session structure (Asia, London, NY) creates predictable liquidity and volatility patterns. Session handoffs = regime changes.

**Session phase definition:**

| Phase | Time (ET) | Characteristics | Edge type |
| :--- | :--- | :--- | :--- |
| Asia | 18:00–02:00 | Low liquidity, mean reversion | Avoid |
| Asia-London | 02:00–03:00 | Handoff, vol compression | Setup for London |
| London | 03:00–08:00 | Rising liquidity, trend setup | Favorable |
| London-NY | 08:00–09:30 | Peak liquidity, breakouts | Most favorable |
| NY | 09:30–13:30 | High vol, news-driven | Conditional |
| NY-Asia | 13:30–18:00 | Position squaring, chop | Avoid |

**Conditional base rates:**

```python
SESSION_MULTIPLIER = {
    'Asia': 0.85,           # Lower hit rates
    'Asia-London': 0.90,    # Transition
    'London': 1.05,         # Slight lift
    'London-NY': 1.15,      # Best phase
    'NY': 1.00,             # Base
    'NY-Asia': 0.80         # Worst phase
}

def get_session_adjusted_rate(base_rate, phase):
    return min(0.95, base_rate * SESSION_MULTIPLIER[phase])
```

**Event overlay (calendar conditioning):**

| Event | Window | Action | Expected vol shift |
| :--- | :--- | :--- | ---: |
| NFP | 08:25–08:40 | Block or widen 3x | +400% |
| CPI | 08:25–08:40 | Block or widen 3x | +350% |
| FOMC | 14:00–14:30 | Block | +300% |
| London Fix | 10:00–10:30 | Tighten, reduce size | +50% |
| NY Open | 09:28–09:35 | Widen stops | +150% |

**Edge cases:**

| Edge case | Detection | Action |
| :--- | :--- | :--- |
| Holiday-thinned session | Calendar + quote rate ↓ | Block or reduce size 50% |
| DST transition | Date check | Adjust phase boundaries |
| Early close | Exchange calendar | Block after 13:00 |
| Unscheduled news | Spread spike + vol spike | Emergency block |

**Kill condition:** if session-phase lift <5 points over ATR-only base rate across the 2025/2026 split, drop SME and use time-agnostic bucketing.

### S4: Path-Dependent Dynamic Exit (PDE)

**Core hypothesis:** Fixed brackets are suboptimal. Realized price path contains information about future trajectory. Dynamic adjustment improves EV.

**Path metrics (computed in real-time):**

```python
class PathState:
    def __init__(self, entry_price, entry_atr):
        self.mfe = 0  # Max favorable excursion
        self.mae = 0  # Max adverse excursion
        self.speed_to_mfe = 0  # Bars to reach 50% of ATR
        self.retracement = 0  # Current drawdown from MFE

    def update(self, current_price):
        self.mfe = max(self.mfe, abs(current_price - entry))
        self.mae = max(self.mae, abs(entry - current_price))
        self.retracement = self.mfe - (current_price - entry)
```

**Dynamic rules (pre-committed):**

| Path condition | Action | Rationale |
| :--- | :--- | :--- |
| `speed_to_mfe < 5 bars AND mfe > 1.5 * ATR` | Move stop to BE + 0.5 ATR | Momentum confirmed |
| `mfe > 2.0 * ATR in 10 bars` | Extend target to 3.0 ATR | Strong trend |
| `retracement > 0.8 * mfe` after MFE | Exit early | Reversal likely |
| `mae > 0.6 * stop` in first 5 bars | Cut loss early | Wrong immediately |
| `mfe < 0.3 * ATR` for 20 bars | Exit, take small loss | Dead trade |

**Implementation:**

```python
def dynamic_exit(path_state, current_bar):
    # Check early exit conditions first
    if early_exit_triggered(path_state):
        return EXIT_MARKET

    # Check target extension
    if path_state.mfe > 2.0 * path_state.entry_atr:
        return EXTEND_TARGET(new_target=3.0 * atr)

    # Check stop adjustment
    if path_state.mfe > 1.5 * path_state.entry_atr:
        return ADJUST_STOP(new_stop=entry + 0.5 * atr)

    return HOLD
```

**Edge cases:**

| Edge case | Detection | Action |
| :--- | :--- | :--- |
| Gap through stop | Price beyond stop on open | Execute at open, flag slippage |
| Gap through target | Price beyond target on open | Take profit, flag |
| Whipsaw (MFE then MAE) | Oscillation detection | Tighten stops, reduce size |
| Illiquid exit | Quote rate ↓ at exit time | Partial fill logic |

**Kill condition:** if PDE improves EV by <10% vs. fixed brackets at 80% power, drop and use static brackets.

---

## 3. Regime Detection Framework

### Multi-factor regime classifier

**Input features (L1-only):**

```python
REGIME_FEATURES = {
    'volatility': {
        'atr_bp': 'ATR in basis points',
        'rv_short': '5m realized vol',
        'rv_long': '60m realized vol',
        'vol_regime': 'EXPANDING/CONTRACTING/STABLE'
    },
    'liquidity': {
        'spread_z': 'Normalized spread',
        'quote_rate_z': 'Normalized quote rate',
        'liquidity_score': 'Composite (S1)'
    },
    'temporal': {
        'session_phase': 'Asia/London/NY/etc.',
        'minute_of_day': '0-1439',
        'day_of_week': '0-6',
        'event_proximity': 'Minutes to next event'
    },
    'microstructure': {
        'efficiency_ratio': 'Trend vs noise',
        'fractal_dimension': 'Roughness of price path'
    }
}
```

**Regime clustering (K-means on portable features):**

| Regime | Vol | Liquidity | Temporal | Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| R1: Quiet | Low | High | Asia | Mean reversion, avoid |
| R2: Setup | Contracting | Normal | Pre-London | Compression, prepare |
| R3: Trending | Expanding | High | London-NY | Momentum, widen brackets |
| R4: News | Spike | Low | Event window | Chaos, block |
| R5: Chop | Stable | Normal | NY afternoon | Noise, avoid |

**Regime transition logic:**

```python
def regime_transition(current, features):
    # Hysteresis to avoid flickering
    if features['vol_regime'] == 'EXPANDING' and \
       features['liquidity_score'] > 1.2:
        return R3  # Trending

    elif features['spread_z'] > 2.0:
        return R4  # News

    elif features['session_phase'] == 'Asia':
        return R1  # Quiet

    # ... etc

    return current  # Stay in current regime
```

---

## 4. Architecture: Detailed Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         L1 DATA INGESTION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  GC Futures (Databento)          │  Spot XAUUSD (Broker)                     │
│  - MBP-1 (top of book)            │  - Bid/ask quotes                         │
│  - Trade tape (aggressor)         │  - Timestamp                              │
│  - Full depth (L2)                │  - Synthetic size (maybe)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FEATURE EXTRACTION (Portable)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  Module: features/portable.py                                                │
│  ─────────────────────────────                                                │
│  • mid_price() → (bid + ask) / 2                                            │
│  • spread_bp() → (ask - bid) / mid * 10000                                    │
│  • quote_rate() → updates per minute (z-scored per instrument)              │
│  • atr_bp() → ATR in basis points (normalized)                              │
│  • rv_parkinson() → 5m realized volatility                                    │
│  • session_phase() → Asia/London/NY/etc.                                    │
│  • event_proximity() → minutes to next high-impact event                      │
│  • efficiency_ratio() → directional movement / total movement                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REGIME CLASSIFICATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Input: All portable features                                                  │
│  Output: Current regime (R1-R5) + confidence                                  │
│                                                                               │
│  Rules:                                                                       │
│  • Regime must persist for ≥3 bars to trigger strategy switch               │
│  • Regime transitions logged with timestamp + feature snapshot              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRATEGY ENGINE                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │     S1      │  │     S2      │  │     S3      │  │     S4      │        │
│  │   ASF       │  │    VM       │  │    SME      │  │    PDE      │        │
│  │  (Filter)   │  │ (Magnitude) │  │ (Calendar)  │  │ (Dynamic)   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                 │
│         ▼                ▼                ▼                ▼                 │
│    Binary:           Continuous:      Continuous:      Path-based:          │
│    ALLOW/BLOCK       Bracket size    Time adj.        Exit rules            │
│    per trade         per regime      per session                            │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SIGNAL AGGREGATION                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Composite Score = S1 * S2 * S3 * S4 (multiplicative)                        │
│                                                                               │
│  IF S1 == BLOCK:                                                             │
│      SIGNAL = NO_TRADE                                                       │
│  ELSE:                                                                       │
│      bracket = S2.get_bracket(regime)                                       │
│      time_adj = S3.get_adjustment(session)                                    │
│      exit_rules = S4.get_rules()                                             │
│      SIGNAL = TRADE(side, bracket, time_adj, exit_rules)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RISK MANAGEMENT                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  Pre-Trade Checks:                                                            │
│  • Max daily loss limit ($X)                                                  │
│  • Max concurrent positions (1)                                              │
│  • Correlation check (if GC and spot both signal, pick best)                │
│  • Spread sanity check (current spread < 3x median)                          │
│                                                                               │
│  Position Sizing:                                                             │
│  • Volatility-adjusted: size ∝ 1 / ATR                                        │
│  • Regime-adjusted: reduce size in R4 (news)                                   │
│  • Kelly fraction: f = (p*b - q) / b, capped at 0.025 (2.5%)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXECUTION                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Limit orders at calculated entry                                           │
│  • OCO bracket (target + stop) attached                                       │
│  • Dynamic monitoring: S4 rules adjust stops/targets in-flight              │
│  • Fill logging: timestamp, slippage, partial fill flag                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKTEST & VALIDATION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Walk-forward analysis (train 2025, test 2026)                             │
│  • Regime-stability test (does edge persist across volatility regimes?)      │
│  • Cross-instrument validation (GC edge → spot edge?)                        │
│  • MDE calculations for every reported lift                                  │
│  • Calibration analysis (does 60% forecast happen 60% of time?)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Week 1)

| Day | Task | Deliverable |
| :--- | :--- | :--- |
| 1 | `instruments.py` abstraction | Portable instrument definitions |
| 2 | `features/portable.py` | All L1 features in bp |
| 3 | S1 (ASF) implementation | Binary filter with kill condition |
| 4 | S4 (PDE) implementation | Dynamic exit rules |
| 5 | Integration + testing | End-to-end pipeline |
| 6–7 | GC backtest (19 months) | S1 + S4 results vs. base |

### Phase 2: Conditioning (Week 2)

| Day | Task | Deliverable |
| :--- | :--- | :--- |
| 8 | S2 (VM) implementation | Vol momentum + dynamic brackets |
| 9 | S3 (SME) implementation | Session phases + calendar |
| 10 | Regime classifier | Multi-factor regime detection |
| 11 | Integration + GC backtest | Full system results |
| 12 | Spot XAUUSD feed integration | Cross-instrument validation |
| 13 | Stability testing | 2025/2026 split analysis |
| 14 | Documentation + deployment | Production-ready system |

---

## 6. Risk Management & Edge Cases

### Kill conditions (pre-committed)

| Strategy | Kill condition | Action on kill |
| :--- | :--- | :--- |
| S1 | `p_target｜ALLOW ≤ p_target｜BLOCK + MDE` at 80% power | Report negative result |
| S2 | Vol regime lift < 3 points at 80% power | Use static ATR buckets |
| S3 | Session lift < 5 points across 2025/2026 | Use time-agnostic rates |
| S4 | EV improvement < 10% vs. fixed | Use static brackets |

### Catastrophic scenarios

| Scenario | Detection | Response |
| :--- | :--- | :--- |
| Flash crash | Price ↓ 5% in 1 minute | Emergency flatten, halt |
| Feed outage | No quotes for 30 seconds | Halt, alert operator |
| Spread blowout | Spread > 10x normal | Block trading, flag |
| Cross-instrument arb | GC/spot divergence > $2 | Alert, manual review |
| Model degradation | Calibration drift > 10% | Reduce size 50%, alert |

### Data quality checks

```python
def validate_l1_data(quote):
    assert quote.bid < quote.ask, "Crossed market"
    assert quote.spread_bp < 100, "Insane spread"
    assert quote.timestamp > last_timestamp, "Stale data"
    assert quote.quote_rate > 0, "No activity"
```

---

## 7. Validation Framework

### Statistical tests

| Test | Method | Pass criteria |
| :--- | :--- | :--- |
| Strategy lift | vs. mix/side-matched null | > MDE at 80% power |
| Regime stability | 2025 vs 2026 split | Lift persists across break |
| Cross-instrument | GC edge → spot edge | Correlation > 0.7 |
| Calibration | Reliability diagram | Within 5% of perfect |
| Overfitting | Walk-forward | Train ≈ Test performance |

### Reporting

```python
class StrategyReport:
    strategy_name: str
    n_trades: int
    p_target: float
    p_target_null: float
    lift: float
    mde: float
    ev_per_trade: float
    sharpe: float
    max_dd: float
    calibration_score: float
    kill_triggered: bool
```

---

## 8. Key Differences from Original Proposal

| Aspect | Original | This alternative |
| :--- | :--- | :--- |
| Directional bets | 1 (S3: anchor reversion) | 0 |
| Volume required | 2 strategies (VWAP, breakout) | 0 strategies |
| Pattern recognition | Yes (H&S, triangles) | No (underpowered) |
| Focus | Find alpha | Avoid negative EV |
| Magnitude prediction | Static brackets | Dynamic, conditional |
| Regime detection | ADX-based | Multi-factor (vol, liq, time) |
| Kill conditions | None specified | Pre-committed for all |
| Cross-instrument | Partial | Full portability |

---

## 9. Expected Outcomes

### Base rate (unconditional)

- `p_target` (70/20/30m): 0.199
- EV per trade: −1.73 ticks

### With S1–S4 conditioning

- Expected `p_target`: 0.22–0.25 (10–25% lift)
- Expected EV: −0.5 to +0.5 ticks (breakeven to slightly positive)
- After costs: −0.5 to 0 ticks (survivable, not thrilling)

### The honest truth

This system won't make you rich. It might not lose money, which is better than 95% of retail gold strategies. The real value is calibrated forecasts — when the model says "22% chance," it actually happens 22% of the time.

---

## 10. Appendix: Code Skeleton

```python
# instruments.py
@dataclass(frozen=True)
class Instrument:
    name: str
    tick: float
    tick_value: Optional[float]
    session: SessionCalendar
    has_flow: bool

# features/portable.py
def compute_features(bar: L1Bar) -> PortableFeatures:
    return PortableFeatures(
        mid=(bar.bid + bar.ask) / 2,
        spread_bp=(bar.ask - bar.bid) / mid * 10000,
        quote_rate_z=compute_quote_rate_z(bar),
        atr_bp=compute_atr_bp(bar, lookback=20),
        rv_short=realized_volatility(bar, window=5),
        session_phase=get_session_phase(bar.timestamp),
        event_proximity=get_event_proximity(bar.timestamp)
    )

# strategies/asf.py (S1)
class AdverseSelectionFilter:
    def allow_trade(self, features: PortableFeatures) -> bool:
        return (features.spread_z < 1.5 and
                features.spread_z > 0.3 and
                features.quote_rate_z > -0.5)

# strategies/vm.py (S2)
class VolatilityMomentum:
    def get_bracket(self, features: PortableFeatures) -> Bracket:
        if features.vol_regime == "EXPANDING":
            return Bracket(target=100, stop=25, horizon=45)
        return Bracket(target=70, stop=20, horizon=30)
```

**Document status:** Draft for review.
**Next steps:** Approve architecture → begin Phase 1 implementation.

---

**Note:** This proposal's S1–S4 (Adverse Selection Filter, Volatility Momentum, Session
Microstructure Edge, Path-Dependent Dynamic Exit) are a separate, independently-arrived-at
four-strategy set from [`four-l1-strategies.md`](four-l1-strategies.md)'s S1–S4 (Bracket
geometry frontier, Compression → expansion, Anchor-distance reversion, Clock/event
conditioning). Both target the same L1-only constraint; neither has been reconciled against
this repo's committed measurements (`BASE_RATES.md`, `FAMILIES.md`) yet, and nothing in either
document is built.
