# Magnitude Expansion Implementation Plan — Fri 18 to Sun 20 Sep 2026

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish whether `mathematical.md`'s conditional-magnitude premise survives on spot XAUUSD, and build the feature engine and tuning harness needed to answer it honestly.

**Architecture:** Two lanes writing one frozen frame (`S13`). Varad owns the magnitude axis — volatility ensemble, Hurst, HMM, classifier, risk, tuner. Prathamesh owns the clock/structure/execution axis — data transport, sessions, news lockout, sweep detection, the state machine. Neither lane imports the other's modules; the scorer imports both. Day 1 is four experiments that can kill or resize the spec before any feature code exists.

**Tech Stack:** Python 3.12 only · pandas · numpy · pyarrow · **scipy (new)** · pytest · ruff · mypy · `uv`

**Spec:** [`docs/superpowers/specs/2026-09-18-magnitude-expansion-design.md`](../specs/2026-09-18-magnitude-expansion-design.md)

## Global Constraints

- **Python 3.12 only.** `requires-python = ">=3.12,<3.13"` in `services/signal-data/pyproject.toml` is load-bearing. Never widen it.
- **All commands run from `services/signal-data/`.** Tests: `uv run pytest -q`. Lint: `uv run ruff check .`. Types: `uv run mypy .`.
- **Baseline is 337 passing tests, ruff clean, mypy clean across 58 files.** Every task ends at or above that.
- **No quantity is ever expressed in ticks or pips.** USD per ounce and basis points only.
- **`XAUUSD.has_flow is False`.** Any flow feature must raise via `instruments.require_flow`. Never aggregate `bid_vol`/`ask_vol` as size.
- **Every reported result carries a cost sensitivity band at 0.9 / 1.9 / 4.0 bp.** A result quoted at one spread is not a result.
- **Pre-commitment before code.** An experiment's prediction and kill condition land in `plans/team/strategy-precommit.md` in a commit that precedes the first line of its implementation.
- **Both nulls, always:** side-shuffled and time-shifted. Mutation-test the guards — removing one must turn a test red.
- **Timestamps are tz-aware UTC.** Never naive. `datetime.now(UTC)`, never `utcnow()`.

---

# DAY 1 — Friday 18 September

Four experiments. Three can kill or resize the spec. No feature code today.

---

### Task 0: Freeze the S13 seam and commit the pre-commitments

**Both engineers, together, 09:00–10:30. Nothing else starts until this is committed.**

**Files:**
- Create: `services/signal-data/features/frame.py`
- Modify: `plans/team/contracts.md` (append S13)
- Modify: `plans/team/strategy-precommit.md` (append §13–§17)
- Test: `services/signal-data/tests/test_frame.py`

**Interfaces:**
- Consumes: `instruments.Instrument`
- Produces: `frame.FEATURES: tuple[str, ...]`, `frame.require(df: pd.DataFrame) -> None`, `frame.TradeCandidate` dataclass. Every later task writes into a frame satisfying `require`.

- [ ] **Step 1: Write the failing test**

```python
# services/signal-data/tests/test_frame.py
"""S13's contract, tested against the ways a lane can violate it silently."""
from __future__ import annotations

import pandas as pd
import pytest

from features import frame


def full() -> pd.DataFrame:
    return pd.DataFrame({c: [0.0] for c in frame.FEATURES})


def test_a_complete_frame_passes():
    frame.require(full())


def test_a_missing_column_is_named_not_just_rejected():
    df = full().drop(columns=["r_hat_60_bp"])
    with pytest.raises(ValueError, match="r_hat_60_bp"):
        frame.require(df)


def test_an_extra_column_is_rejected():
    # A lane that adds a column has changed the seam without saying so.
    df = full().assign(ofi_z=[0.0])
    with pytest.raises(ValueError, match="ofi_z"):
        frame.require(df)


def test_ticks_and_pips_are_refused_by_name():
    # The one unit rule the whole spec rests on, enforced mechanically.
    for bad in ("stop_ticks", "target_pips"):
        with pytest.raises(ValueError, match=bad):
            frame.require(full().assign(**{bad: [0.0]}))
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_frame.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'features.frame'`

- [ ] **Step 3: Write `features/frame.py`**

```python
"""S13 -- the one frame both lanes write and the scorer reads.

WHY A TUPLE AND NOT A DATACLASS. The lanes produce columns, not objects;
`require` is the whole contract. S9 froze the bars frame the same way, and
a dataclass here would mean converting a 100k-row frame into rows to check
a header.

WHY EXTRA COLUMNS ARE AN ERROR. A lane that adds a column has changed the
seam without the other lane knowing. S2's history is the argument: the
seams that held were the ones that failed loudly.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FEATURES: tuple[str, ...] = (
    "ts", "mid", "spread_bp",                              # frame identity  (Prathamesh)
    "r_hat_60_bp", "r_ratio",                              # §2 ensemble     (Varad)
    "sigma_yz_12", "sigma_yz_48", "sigma_yz_288", "sigma_garch",
    "h_dfa_15m", "h_vt_15m", "h_agree",                    # §6              (Varad)
    "p_build", "p_expand",                                 # §7 HMM          (Varad)
    "session", "phase", "news_lockout",                    # §1 §12          (Prathamesh)
    "swept_level", "reclaim_dt_s", "wick_w",               # §9              (Prathamesh)
)


def require(df: pd.DataFrame) -> None:
    """Exact column set. Missing and extra are both errors, and both name the column."""
    got, want = set(df.columns), set(FEATURES)
    if missing := sorted(want - got):
        raise ValueError(f"S13 frame is missing {missing}")
    if extra := sorted(got - want):
        raise ValueError(f"S13 frame has columns not in the seam: {extra}")


@dataclass(frozen=True, slots=True)
class TradeCandidate:
    """What the FSM emits and the risk engine consumes. Distances in USD/oz."""
    ts: pd.Timestamp
    side: int            # +1 long, -1 short
    p_e: float
    score: float
    entry: float
    stop: float
    target: float
    d_bp: float
    r_bp: float
    cost_bp: float
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `uv run pytest tests/test_frame.py -q`
Expected: 4 passed

- [ ] **Step 5: Register S13 in `contracts.md`**

Append to `plans/team/contracts.md`, matching the shape S8 and S9 use:

```markdown
## S13 · `ExpansionFeatures` — both lanes → the scorer

**Frozen 2026-09-18.** `services/signal-data/features/frame.py`.

`FEATURES` is the exact column set; `require()` rejects missing *and* extra columns, naming them.
Varad's lane writes the magnitude columns, Prathamesh's writes identity, clock and structure.
The scorer imports both lanes; neither lane imports the scorer or the other lane.

**The unit rule is part of the contract:** no column name may contain `tick` or `pip`. Distances
are USD/oz, rates are basis points. A pip is a broker's opinion.
```

- [ ] **Step 6: Write the pre-commitments — before any experiment code exists**

Append §13–§17 to `plans/team/strategy-precommit.md`. Each carries **the numbers, the reasoning, and the kill condition**, following §11 and §12's shape. Copy the kill conditions verbatim from spec §6.0–§6.4. For each, write the honest prediction *before* the run — that is the entire point of the file.

- [ ] **Step 7: Commit — pre-commitments and seam, one commit, before any experiment**

```bash
git add services/signal-data/features/frame.py services/signal-data/tests/test_frame.py \
        plans/team/contracts.md plans/team/strategy-precommit.md
git commit -m "feat(seam): S13 frozen, and E0-E4 pre-committed before their code exists"
```

---

### Task 1: E0 — verify the S3 transport *(Prathamesh)*

**This is the critical path. Everything on Days 2–3 assumes it.**

**Files:**
- Create: `services/signal-data/spot_s3.py`
- Create: `services/signal-data/analysis/E0_TRANSPORT.md`
- Test: `services/signal-data/tests/test_spot_s3.py`

**Interfaces:**
- Consumes: `dukascopy.decode_bi5`, `dukascopy.POINTS`
- Produces: `spot_s3.day_key(symbol, day) -> str`, `spot_s3.fetch_day(symbol, day) -> pd.DataFrame`

- [ ] **Step 1: Probe the bucket by hand before writing any code**

```bash
# Requester-pays: you pay, so credentials must exist and be valid.
aws s3 ls s3://cfg-public-proper-wallaby/XAUUSD/2021/00/ \
  --request-payer requester --region eu-west-1 | head
```

Record verbatim in `analysis/E0_TRANSPORT.md` — including a failure. **If this errors, do not
work around it silently.** Note the exact error, then go to Step 2's fallback.

- [ ] **Step 2: If S3 is unavailable, fall back to the daily-candle endpoint**

The fallback is already proven in `Quant_Trading/scripts/fetch_dukascopy.py`. One file per day:

```python
url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
# 24-byte big-endian records: >IIIIIf = offset_sec, open, close, low, high, volume
```

**The month is zero-indexed** — June 2025 is `/2025/05/`. An off-by-one returns a real file for
the wrong month; it downloads, decodes and looks fine. `test_dukascopy.py` already pins this for
the tick path; pin it here too.

- [ ] **Step 3: Write the failing test**

```python
# services/signal-data/tests/test_spot_s3.py
"""The transport, tested on the two ways it silently returns wrong data."""
from __future__ import annotations

from datetime import date

import pytest

import spot_s3


def test_the_month_in_the_key_is_zero_indexed():
    # June 2025 lives under /05/. An off-by-one returns May and looks fine.
    assert spot_s3.day_key("XAUUSD", date(2025, 6, 18)) == "XAUUSD/2025/05/18"


def test_january_is_month_zero_not_twelve():
    assert spot_s3.day_key("XAUUSD", date(2025, 1, 2)) == "XAUUSD/2025/00/02"


def test_an_unknown_symbol_refuses_rather_than_guessing_a_scale():
    # dukascopy.POINTS' rule: a guessed point scale is a 10x price error.
    with pytest.raises(ValueError, match="EURJPY"):
        spot_s3.fetch_day("EURJPY", date(2025, 6, 18))
```

- [ ] **Step 4: Run it and watch it fail**

Run: `uv run pytest tests/test_spot_s3.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'spot_s3'`

- [ ] **Step 5: Write `spot_s3.py`**

```python
"""Route 2's bulk transport. Reuses dukascopy.py's decoder; only the fetch differs.

WHY THIS EXISTS AND spot.py's pull() DOES NOT SUFFICE. Measured 2026-09-17:
the HTTP datafeed serves ~2 requests from a three-day rest and then returns
HTTP 429 -- an explicit rate limit, not the IP ban SPOT_FEED_CHECK.md
recorded. Its own error body points at Dukascopy's data-export docs, which
document this bucket. Five years is ~1,300 day-files here against ~43,800
hour-files over HTTP.

NOTHING ABOUT THE DECODER CHANGES. `dukascopy.decode_bi5` and
`dukascopy.POINTS` are imported, not reimplemented -- two decoders is how
two files quietly disagree about a price scale.
"""
from __future__ import annotations

from datetime import date

import boto3
import pandas as pd

import dukascopy as dk

BUCKET = "cfg-public-proper-wallaby"
REGION = "eu-west-1"


def day_key(symbol: str, day: date) -> str:
    """Dukascopy's layout. **The month is zero-indexed** -- June is 05."""
    return f"{symbol}/{day.year}/{day.month - 1:02d}/{day.day:02d}"


def fetch_day(symbol: str, day: date) -> pd.DataFrame:
    """One day of ticks. Refuses a symbol with no declared point scale."""
    if symbol not in dk.POINTS:
        raise ValueError(f"no point scale for {symbol}; add it to dukascopy.POINTS deliberately")
    obj = boto3.client("s3", region_name=REGION).get_object(
        Bucket=BUCKET, Key=f"{day_key(symbol, day)}_ticks.bi5", RequestPayer="requester")
    return dk.decode_bi5(obj["Body"].read(), symbol, pd.Timestamp(day, tz="UTC"))
```

- [ ] **Step 6: Run the tests and watch them pass**

Run: `uv run pytest tests/test_spot_s3.py -q`
Expected: 3 passed

- [ ] **Step 7: Cross-check one hour against the already-validated sample**

The 2025-06-18 14:00 UTC hour is validated in `SPOT_FEED_CHECK.md` §1: **20,654 quotes, median
spread 1.91 bp, mid 3373.861 … 3392.471.** Pull the same hour through S3 and compare.

```bash
uv run python -c "
import spot_s3, pandas as pd
from datetime import date
d = spot_s3.fetch_day('XAUUSD', date(2025,6,18))
h = d[(d.timestamp >= '2025-06-18T14:00Z') & (d.timestamp < '2025-06-18T15:00Z')]
print(len(h), h.bid.min(), h.ask.max())"
```

**If the count is not 20,654, stop and find out why before pulling anything else.** A transport
that returns a different number for a known hour is not a transport.

- [ ] **Step 8: Record the verdict and commit**

`analysis/E0_TRANSPORT.md` states: earliest XAUUSD date available, total files and bytes for five
years, measured cost of a one-month pull, and the cross-check result. **If E0 failed, say so in the
first line** — the rest of the plan degrades by spec §7.1's stated rule, not by improvisation.

```bash
git add services/signal-data/spot_s3.py services/signal-data/tests/test_spot_s3.py \
        services/signal-data/analysis/E0_TRANSPORT.md services/signal-data/pyproject.toml
git commit -m "feat(data): E0 -- S3 transport verified, five years of XAUUSD reachable"
```

---

### Task 2: E1 — is §Objective's own filter ever satisfied? *(Varad)*

**Files:**
- Create: `services/signal-data/e1_magnitude.py`
- Create: `services/signal-data/analysis/E1_MAGNITUDE_BASE.md`
- Test: `services/signal-data/tests/test_e1_magnitude.py`

**Interfaces:**
- Consumes: `reach.py`, `analysis/reach_table.csv`, `instruments.GC`
- Produces: `e1_magnitude.base_rate(bars, horizon_min, threshold_usd) -> pd.DataFrame`

- [ ] **Step 1: Write the failing test**

```python
# services/signal-data/tests/test_e1_magnitude.py
"""E1's estimand, tested against the ways a base rate can flatter itself."""
from __future__ import annotations

import numpy as np
import pandas as pd

import e1_magnitude as e1


def ramp(n: int, step: float) -> pd.DataFrame:
    ts = pd.date_range("2025-06-02", periods=n, freq="1min", tz="UTC")
    close = 3000.0 + np.arange(n) * step
    return pd.DataFrame({"close": close, "cell": "x"}, index=ts)


def test_a_known_move_is_counted_exactly():
    # $0.25/min for 60 min = $15.00 -- exactly the threshold, and >= includes it.
    out = e1.base_rate(ramp(400, 0.25), horizon_min=60, threshold_usd=15.0)
    assert out.loc["x", "p"] == 1.0


def test_a_move_one_cent_short_is_not_counted():
    out = e1.base_rate(ramp(400, 0.2490), horizon_min=60, threshold_usd=15.0)
    assert out.loc["x", "p"] == 0.0


def test_windows_do_not_overlap():
    # Overlapping windows inflate n ~60x and manufacture confidence from
    # autocorrelation -- the same defect m3b_drift.py's elapsed filter guards.
    out = e1.base_rate(ramp(400, 0.25), horizon_min=60, threshold_usd=15.0)
    assert out.loc["x", "n"] == 400 // 60


def test_magnitude_is_absolute_so_a_fall_counts_as_much_as_a_rise():
    out = e1.base_rate(ramp(400, -0.25), horizon_min=60, threshold_usd=15.0)
    assert out.loc["x", "p"] == 1.0
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_e1_magnitude.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'e1_magnitude'`

- [ ] **Step 3: Write `e1_magnitude.py`**

```python
"""E1 -- P(|dP_h| >= threshold), which is mathematical.md's own minimum filter.

WHY THIS IS NOT A NEW MEASUREMENT. §Objective's gate is
`P(M_{t,60} >= 150 ticks) >= 0.60`, and `reach.py` has been computing
"does price reach X within H" for 19 months since 9 Sep. This restates that
quantity in USD/oz and reports it per conditioning cell.

DISJOINT WINDOWS, NOT ROLLING. 60-minute windows stepped by 1 minute share
59/60 of their bars; n inflates ~60x and every confidence interval built on
it is a lie. m3b_drift.py's elapsed-time filter exists for the same reason.
"""
from __future__ import annotations

import pandas as pd


def base_rate(bars: pd.DataFrame, *, horizon_min: int, threshold_usd: float) -> pd.DataFrame:
    """Per cell: n disjoint windows, and the share whose |move| clears threshold."""
    step = bars.iloc[::horizon_min]
    move = step["close"].diff().abs().shift(-1).dropna()
    hit = (move >= threshold_usd).rename("hit")
    cell = step["cell"].reindex(hit.index)
    g = hit.groupby(cell)
    return pd.DataFrame({"n": g.size(), "p": g.mean()})
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_e1_magnitude.py -q`
Expected: 4 passed

- [ ] **Step 5: Run it against the 19-month GC archive**

```bash
uv run python e1_magnitude.py --threshold 15.00 --horizon 60 \
  --out analysis/E1_MAGNITUDE_BASE.md
```

Report `p` unconditionally and per regime cell, with `n` beside every `p`. **A cell with n < 400
is reported and not interpreted** — `strategy-precommit.md` §3 derived that floor; reuse it.

- [ ] **Step 6: Score the pre-commitment**

Append a `### Scored, 2026-09-18` block to `strategy-precommit.md` §14. **If no cell reaches 0.60,
the kill condition fires** — say so plainly and move the threshold before Day 2 builds on it.

- [ ] **Step 7: Commit**

```bash
git add services/signal-data/e1_magnitude.py services/signal-data/tests/test_e1_magnitude.py \
        services/signal-data/analysis/E1_MAGNITUDE_BASE.md plans/team/strategy-precommit.md
git commit -m "feat(strategy): E1 -- the spec's own 150-tick filter, measured in USD/oz"
```

---

### Task 3: E2 — does the funnel produce a testable number of events? *(Varad — delegated by Prathamesh 2026-09-18)*

**Files:**
- Create: `services/signal-data/e2_funnel.py`
- Create: `services/signal-data/analysis/E2_FUNNEL.md`
- Test: `services/signal-data/tests/test_e2_funnel.py`

**Interfaces:**
- Consumes: `calendars.load`, `features.portable.session_phase`
- Produces: `e2_funnel.count(bars, stages) -> pd.DataFrame` with columns `stage, survivors, pct_of_prior`

- [ ] **Step 1: Write the failing test**

```python
# services/signal-data/tests/test_e2_funnel.py
"""E2 counts. It must never trade, and must never lose a stage silently."""
from __future__ import annotations

import numpy as np
import pandas as pd

import e2_funnel


def bars(n: int = 1000) -> pd.DataFrame:
    ts = pd.date_range("2025-06-02", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"close": 3000.0 + np.arange(n) * 0.01}, index=ts)


def test_every_stage_appears_even_when_it_kills_everything():
    # A stage that removes all rows must still be a row in the table. A funnel
    # that stops printing where it stops passing hides where it died.
    stages = [("always", lambda d: d.index == d.index), ("never", lambda d: d.index != d.index)]
    out = e2_funnel.count(bars(), stages)
    assert list(out["stage"]) == ["total", "always", "never"]
    assert out.iloc[-1]["survivors"] == 0


def test_survivors_are_monotone_non_increasing():
    stages = [("half", lambda d: np.arange(len(d)) % 2 == 0),
              ("quarter", lambda d: np.arange(len(d)) % 4 == 0)]
    out = e2_funnel.count(bars(), stages)
    assert (out["survivors"].diff().dropna() <= 0).all()


def test_it_returns_counts_and_never_a_position():
    out = e2_funnel.count(bars(), [("all", lambda d: d.index == d.index)])
    assert set(out.columns) == {"stage", "survivors", "pct_of_prior"}
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_e2_funnel.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'e2_funnel'`

- [ ] **Step 3: Write `e2_funnel.py`**

```python
"""E2 -- §9's sixteen conditions as an attrition table. No P&L, ever.

WHY COUNT BEFORE BUILDING. §9 stacks sixteen conditions. If fewer than 100
candidates survive to stage 12 over the whole archive, no parameter setting
makes the spec testable, and every hour spent on §2's ensemble before
knowing that is an hour spent on a strategy with no sample.

WHY A STAGE THAT KILLS EVERYTHING STILL PRINTS. A funnel that stops
printing where it stops passing hides which condition did the killing --
which is the single number this experiment exists to produce.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd

Stage = tuple[str, Callable[[pd.DataFrame], np.ndarray]]


def count(bars: pd.DataFrame, stages: Sequence[Stage]) -> pd.DataFrame:
    """Survivors after each stage, applied in order. Stages are ANDed cumulatively."""
    mask = np.ones(len(bars), dtype=bool)
    rows = [("total", int(mask.sum()))]
    for name, pred in stages:
        mask = mask & np.asarray(pred(bars), dtype=bool)
        rows.append((name, int(mask.sum())))
    out = pd.DataFrame(rows, columns=["stage", "survivors"])
    prior = out["survivors"].shift(1)
    out["pct_of_prior"] = (out["survivors"] / prior * 100).round(1)
    return out
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_e2_funnel.py -q`
Expected: 3 passed

- [ ] **Step 5: Define §9's sixteen stages in order**

Stages 1–7 and 11–13 are implementable today from bars and the calendar. **Stages 8, 9, 10 and 14
are the dead flow conditions** — record them in the table as `SKIPPED (no tape)` rather than
dropping them, so the attrition table stays sixteen rows and the reader sees what was not tested.

- [ ] **Step 6: Run over the longest archive available and record**

`analysis/E2_FUNNEL.md` carries the sixteen-row table. **The number that matters is survivors at
stage 12.** Under 100 and the kill condition fires.

- [ ] **Step 7: Score the pre-commitment and commit**

```bash
git add services/signal-data/e2_funnel.py services/signal-data/tests/test_e2_funnel.py \
        services/signal-data/analysis/E2_FUNNEL.md plans/team/strategy-precommit.md
git commit -m "feat(strategy): E2 -- §9's funnel counted, not traded"
```

---

### Task 4: E3 — the cost floor and where §10's stop range starts *(Varad)*

**Files:**
- Create: `services/signal-data/e3_cost.py`
- Create: `services/signal-data/analysis/E3_COST.md`
- Test: `services/signal-data/tests/test_e3_cost.py`

**Interfaces:**
- Produces: `e3_cost.breakeven(d_bp, r_bp, cost_bp) -> float`, `e3_cost.ev_bp(p, d_bp, r_bp, cost_bp) -> float`, `e3_cost.surface(d_usd, r_usd, price, cost_bp, p) -> pd.DataFrame`

- [ ] **Step 1: Write the failing test**

```python
# services/signal-data/tests/test_e3_cost.py
"""The cost arithmetic, pinned. This is where an order-of-magnitude slip hides."""
from __future__ import annotations

import pytest

import e3_cost


def test_thirty_cents_at_3400_is_under_one_basis_point():
    # The check that catches a 10x slip: 0.30/3400 = 0.88 bp, not 8.8.
    assert e3_cost.to_bp(0.30, 3400.0) == pytest.approx(0.882, abs=0.001)


def test_one_gc_tick_at_3400_is_the_m3b_floor():
    assert e3_cost.to_bp(0.10, 3400.0) == pytest.approx(0.294, abs=0.001)


def test_breakeven_win_rate_at_the_spec_parameters():
    # D=$5.00, R=$12.50 at 3400 -> 14.71 / 36.76 bp. At the venue's 0.88 bp.
    p = e3_cost.breakeven(d_bp=14.71, r_bp=36.76, cost_bp=0.88)
    assert p == pytest.approx(0.303, abs=0.002)


def test_ev_is_positive_at_forty_two_percent_at_every_venue_considered():
    for c in (0.35, 0.88, 1.91):
        assert e3_cost.ev_bp(p=0.42, d_bp=14.71, r_bp=36.76, cost_bp=c) > 0


def test_cost_enters_ev_once_not_twice():
    # A round trip is one full spread. Charging it on entry and exit is the
    # classic double-count and it halves a real edge into a fake loss.
    a = e3_cost.ev_bp(p=0.42, d_bp=14.71, r_bp=36.76, cost_bp=0.0)
    b = e3_cost.ev_bp(p=0.42, d_bp=14.71, r_bp=36.76, cost_bp=2.0)
    assert a - b == pytest.approx(2.0)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_e3_cost.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'e3_cost'`

- [ ] **Step 3: Write `e3_cost.py`**

```python
"""E3 -- what a trade costs, and which (D, R) pairs survive it.

THE UNIT TRAP THIS MODULE EXISTS TO PIN. One basis point is 1e-4. A $0.30
spread on $3,400 gold is 0.88 bp, not 8.8 -- and the 10x version turns a
+6 bp expectancy into a -2 bp one, i.e. it reverses the decision. Every
conversion goes through `to_bp` and `to_bp` is tested against two known
values.

COST IS CHARGED ONCE. A round trip crosses one full spread. Charging half
on entry and half on exit is the same number; charging a full spread twice
is the classic double-count.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def to_bp(usd_per_oz: float, price: float) -> float:
    return usd_per_oz / price * 1e4


def ev_bp(*, p: float, d_bp: float, r_bp: float, cost_bp: float) -> float:
    """Expectancy per trade, net. p is the win rate, D and R are distances."""
    return p * r_bp - (1.0 - p) * d_bp - cost_bp


def breakeven(*, d_bp: float, r_bp: float, cost_bp: float) -> float:
    """Win rate at which `ev_bp` is zero: (D + c) / (R + D)."""
    return (d_bp + cost_bp) / (r_bp + d_bp)


def surface(*, price: float, cost_bp: float, p: float,
            d_usd: np.ndarray, r_mult: np.ndarray) -> pd.DataFrame:
    """EV over §10's (D, R) rectangle, with §13's slippage exclusion applied.

    §13 rejects a trade whose slippage estimate exceeds 25% of intended risk.
    Spread alone is charged against that budget, so the D floor is c / 0.25.
    """
    rows = []
    for d in d_usd:
        d_bp = to_bp(d, price)
        for m in r_mult:
            r_bp = to_bp(max(m * d, 10.0), price)
            rows.append({
                "d_usd": d, "r_mult": m, "d_bp": d_bp, "r_bp": r_bp,
                "ev_bp": ev_bp(p=p, d_bp=d_bp, r_bp=r_bp, cost_bp=cost_bp),
                "breakeven_p": breakeven(d_bp=d_bp, r_bp=r_bp, cost_bp=cost_bp),
                "excluded_by_s13": cost_bp / d_bp > 0.25,
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_e3_cost.py -q`
Expected: 5 passed

- [ ] **Step 5: Measure the realised spread distribution, by session**

The 1.91 bp figure is **one London–NY hour**. Asian spreads are wider and that changes the D floor.
Compute `spread_bp` percentiles per session phase from whatever spot ticks E0 delivered.

- [ ] **Step 6: Write `analysis/E3_COST.md`**

Three outputs: the per-session spread table, the `(D, R)` EV surface at 0.9 / 1.9 / 4.0 bp, and
**the D floor at which §13's exclusion stops firing.** Spec §4 predicts $2.60/oz at 1.91 bp —
report the measured number and whether it matches.

- [ ] **Step 7: Score the pre-commitment and commit**

```bash
git add services/signal-data/e3_cost.py services/signal-data/tests/test_e3_cost.py \
        services/signal-data/analysis/E3_COST.md plans/team/strategy-precommit.md
git commit -m "feat(strategy): E3 -- cost floor measured, §10's stop range re-derived"
```

- [ ] **Step 8: Both — read Day 1's four results together, 30 minutes**

Four numbers decide whether Day 2 proceeds as written: E0's span, E1's best `p`, E2's stage-12
survivors, E3's viable `(D, R)` region. **If any kill condition fired, Day 2 is re-scoped now** —
not on Sunday.

---

# DAY 2 — Saturday 19 September

The two feature lanes, built against the frozen seam.

---

### Task 5: The spot bar loader *(Prathamesh)*

**Files:**
- Modify: `services/signal-data/spot.py` (swap `pull()`'s transport to `spot_s3`)
- Test: `services/signal-data/tests/test_spot.py` (extend)

**Interfaces:**
- Consumes: `spot_s3.fetch_day`, `spot.minute_bars`, `spot.resample`
- Produces: `spot.load_bars(symbol, months, bar_size) -> pd.DataFrame` with `open/high/low/close/ticks/spread_bp/session`

- [ ] **Step 1: Write the failing test**

```python
def test_a_day_with_holes_is_never_written_as_a_quiet_day():
    # spot.pull()'s existing invariant, and it must survive the transport swap:
    # a day with any lost hour is not written at all, because a hole on disk
    # looks exactly like a calm session to atr_bp and rv_slope.
    ...


def test_ticks_is_never_summed_into_a_column_named_volume():
    bars = spot.load_bars("XAUUSD", ["2025-06"], "5min")
    assert "volume" not in bars.columns
    assert "ticks" in bars.columns
```

- [ ] **Step 2: Run and watch it fail. Step 3: swap the transport. Step 4: run and watch it pass.**

`minute_bars` and `resample` are unchanged — **only `pull()`'s fetch changes.** If anything else
needs changing, the S9 bars-frame seam leaked and that must be said loudly.

- [ ] **Step 5: Pull the archive and write a sha256 manifest**

Follow `analysis/gc_data_manifest.md`'s shape exactly. **The manifest is what makes "the holdout
was untouched" provable later** rather than asserted.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(data): spot bars from S3, day-completeness invariant intact"
```

---

### Task 6: Yang-Zhang realised volatility *(Varad)*

**Files:**
- Modify: `services/signal-data/features/expansion.py`
- Test: `services/signal-data/tests/test_features.py` (extend)

**Interfaces:**
- Produces: `expansion.yang_zhang(bars, n) -> pd.Series` — σ per bar over an `n`-bar window

- [ ] **Step 1: Write the failing test**

```python
def test_k_matches_the_published_constant():
    # k = 0.34 / (1.34 + (n+1)/(n-1)). At n=12 that is 0.2088...
    assert expansion._yz_k(12) == pytest.approx(0.20880, abs=1e-5)


def test_zero_variance_bars_give_zero_volatility():
    flat = bars_at(close=3000.0, n=60)  # O=H=L=C throughout
    assert expansion.yang_zhang(flat, n=12).dropna().eq(0.0).all()


def test_it_is_drift_independent():
    # Yang-Zhang's whole claim. A pure ramp with identical bar shapes must
    # return the same sigma as the same shapes with no ramp.
    ...


def test_a_window_shorter_than_n_is_nan_not_a_partial_estimate():
    out = expansion.yang_zhang(bars_at(close=3000.0, n=60), n=12)
    assert out.iloc[:11].isna().all()
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `uv run pytest tests/test_features.py -k yang_zhang -q`

- [ ] **Step 3: Implement**

```python
def _yz_k(n: int) -> float:
    return 0.34 / (1.34 + (n + 1) / (n - 1))


def yang_zhang(bars: pd.DataFrame, *, n: int) -> pd.Series:
    """§2's estimator. Drift-independent, which is why it beats close-to-close here.

    NaN until n bars exist. A partial-window estimate is a smaller number
    that looks like calm, and `r_ratio` divides by it.
    """
    o, h, l, c = (np.log(bars[x]) for x in ("open", "high", "low", "close"))
    ro = o - c.shift(1)
    rc = c - o
    rs = (h - o) * (h - c) + (l - o) * (l - c)
    k = _yz_k(n)
    var = (ro.rolling(n).var(ddof=1)
           + k * rc.rolling(n).var(ddof=1)
           + (1 - k) * rs.rolling(n).mean())
    return np.sqrt(var.clip(lower=0.0))
```

- [ ] **Step 4: Run and watch it pass. Step 5: commit.**

```bash
git commit -am "feat(vol): Yang-Zhang sigma at 12/48/288 bars"
```

---

### Task 7: GARCH(1,1) with Student-t innovations *(Varad)*

**Dependency decision, settled:** hand-rolled, with `scipy` added explicitly to `pyproject.toml`.
The MLE is ~50 lines given an optimizer, which is under the write-it-yourself threshold; `arch`
would drag in statsmodels for one estimator. **The `scipy` line is a lockfile change and earns its
own commit**, per this repo's convention.

**Files:**
- Modify: `services/signal-data/pyproject.toml` (add `scipy>=1.14`)
- Modify: `services/signal-data/features/expansion.py`
- Test: `services/signal-data/tests/test_features.py` (extend)

**Interfaces:**
- Produces: `expansion.garch_fit(r) -> tuple[float, float, float, float]` returning `(omega, alpha, beta, nu)`; `expansion.garch_forecast(r, params, m) -> float`

- [ ] **Step 1: Commit the dependency on its own**

```bash
uv add "scipy>=1.14"
git add pyproject.toml uv.lock
git commit -m "build: scipy, for the GARCH MLE -- one estimator, not statsmodels"
```

- [ ] **Step 2: Write the failing test**

```python
def test_it_recovers_known_parameters_from_a_simulated_series():
    # The only honest test of an estimator: simulate from known omega/alpha/beta,
    # fit, and check recovery. Seeded, so it never flakes.
    ...


def test_a_non_stationary_fit_is_refused_not_returned():
    # alpha + beta >= 1 means the variance forecast diverges. Returning it
    # quietly puts an infinite r_hat_60 into the trade filter.
    with pytest.raises(ValueError, match="stationar"):
        ...


def test_the_m_step_forecast_reverts_toward_the_unconditional_variance():
    # sigma^2_bar + (alpha+beta)^m (sigma_t^2 - sigma^2_bar): as m grows the
    # forecast must approach the unconditional level, not the current one.
    ...
```

- [ ] **Step 3: Run and watch it fail. Step 4: implement the MLE and the m-step forecast.**

```python
def garch_forecast(sigma2_t: float, params: tuple[float, ...], m: int) -> float:
    """§2's m-step variance. m is the count of 5-minute bars in the horizon."""
    omega, alpha, beta, _ = params
    persist = alpha + beta
    if persist >= 1.0:
        raise ValueError(f"non-stationary fit: alpha+beta={persist:.4f}")
    bar = omega / (1.0 - persist)
    return bar + persist**m * (sigma2_t - bar)
```

- [ ] **Step 5: Run and watch it pass. Step 6: commit.**

**Overrun budget: 3 hours.** If the MLE is not converging by then, **ship `garch_forecast` against a
fixed `(omega, alpha, beta)` fitted once offline**, label it as fixed-parameter in the frame's
docstring, and move on. The ensemble weight can carry the uncertainty.

---

### Task 8: The ensemble forecast and §2's two filters *(Varad)*

**Interfaces:**
- Consumes: `expansion.yang_zhang`, `expansion.garch_forecast`
- Produces: `expansion.r_hat_60(bars, w_yz, w_g) -> pd.Series` in USD/oz; `expansion.r_ratio(r_hat) -> pd.Series`

- [ ] **Step 1: Write the failing test**

```python
def test_weights_must_sum_to_one():
    with pytest.raises(ValueError, match="sum to 1"):
        expansion.r_hat_60(bars, w_yz=0.5, w_g=0.7)


def test_r_ratio_uses_a_trailing_median_not_a_full_sample_one():
    # A full-sample median is lookahead: it knows the future's volatility.
    # This is the single easiest way to fake §2's 1.20 quality filter.
    ...


def test_r_hat_is_in_usd_per_ounce_not_log_units():
    # sigma is a log return; R_hat must be sigma * price. Forgetting the
    # multiply gives a number ~3400x too small that still passes a > filter
    # by never passing it.
    ...
```

- [ ] **Steps 2–5: fail, implement, pass, commit.**

---

### Task 9: Hurst by two estimators *(Varad)*

**Interfaces:**
- Produces: `expansion.hurst_dfa(x, scales) -> float`, `expansion.hurst_vt(x, scales) -> float`, `expansion.hurst_agree(h1, h2, tol=0.05) -> bool`

- [ ] **Step 1: Write the failing test**

```python
def test_both_estimators_return_half_for_a_random_walk():
    rng = np.random.default_rng(0)
    x = np.cumsum(rng.standard_normal(20_000))
    assert expansion.hurst_dfa(x) == pytest.approx(0.5, abs=0.05)
    assert expansion.hurst_vt(x) == pytest.approx(0.5, abs=0.05)


def test_both_exceed_half_for_a_persistent_series():
    ...


def test_they_are_required_to_agree_before_either_is_used():
    # mathematical.md §6: "Do not trade from one noisy Hurst estimate."
    # That sentence becomes a test or it becomes nothing.
    assert not expansion.hurst_agree(0.52, 0.61)
    assert expansion.hurst_agree(0.57, 0.59)


def test_too_few_points_returns_nan_rather_than_a_confident_wrong_number():
    assert np.isnan(expansion.hurst_dfa(np.arange(10.0)))
```

- [ ] **Steps 2–5: fail, implement, pass, commit.**

`hurst_vt` is the cheap one — regress `log Var(ΔX_τ)` on `log τ`, slope is `2H`. `hurst_dfa` is the
independent check. **`h_agree` is the column the scorer reads**, not either estimate alone.

---

### Task 10: Sessions and the news lockout *(Prathamesh)*

**Interfaces:**
- Consumes: `calendars.load`, `features.portable.session_phase`
- Produces: `structure.in_window(ts, inst) -> pd.Series`, `structure.news_lockout(ts, events, minutes=5) -> pd.Series`

- [ ] **Step 1: Write the failing test**

```python
def test_the_two_active_windows_are_new_york_time_not_utc():
    # §1: 08:00-11:30 and 13:30-15:30 New York. Under DST, NY is UTC-4 in
    # June and UTC-5 in December. A UTC constant is wrong for half the year
    # and the error is exactly one hour, which looks like a boundary bug.
    ...


def test_the_lockout_is_symmetric_around_the_release():
    # §12: [t-5m, t+5m]. An asymmetric window silently allows entries into
    # the release.
    ...


def test_a_release_at_a_window_edge_locks_out_rather_than_squeaking_in():
    ...
```

- [ ] **Steps 2–5: fail, implement, pass, commit.**

---

### Task 11: The sweep-and-reclaim detector *(Prathamesh)*

**Interfaces:**
- Produces: `structure.sweeps(ticks, level, *, side, max_reclaim_s=30, atr_10s) -> pd.DataFrame` with `swept_level, reclaim_dt_s, wick_w`

- [ ] **Step 1: Write the failing test**

```python
def test_delta_is_the_max_of_two_ticks_and_five_percent_of_atr():
    # §9: delta = max(2 ticks, 0.05 * ATR_10s). On spot, "2 ticks" is a
    # broker quantum -- XAUUSD.tick is Dukascopy's 0.001 price quantum and
    # instruments.py says in terms it must not be used for costing. Use the
    # ATR leg and a configured floor.
    ...


def test_price_staying_below_the_level_for_over_thirty_seconds_is_acceptance():
    # §9: "The sweep must not be accepted if price remains below the level
    # for more than 30 seconds. That is more likely acceptance than
    # rejection." The 31st second must not produce a candidate.
    ...


def test_the_reclaim_must_clear_the_level_by_delta_not_merely_touch_it():
    ...


def test_wick_w_is_measured_from_the_sweep_extreme_not_the_bar_low():
    # §9's limit sits at P_s + 0.50W. Measuring W from the wrong point moves
    # every entry price in the backtest.
    ...
```

- [ ] **Steps 2–5: fail, implement, pass, commit.**

**Overrun budget: 3 hours.** This is the day's second risk after GARCH. If it overruns, ship the
sweep detection without the reclaim-timing leg and record `reclaim_dt_s` as NaN — E2 already told
you how many candidates that costs.

---

# DAY 3 — Sunday 20 September

The tuning protocol, and the first honest fold.

---

### Task 12: E4 — is a 3-state HMM identifiable on 5 observations? *(Varad)*

**Interfaces:**
- Produces: `expansion.hmm_fit(X, k) -> tuple[np.ndarray, np.ndarray]` returning `(transition, means)`; `expansion.p_build_expand(X, model) -> pd.DataFrame`

- [ ] **Step 1: Write the failing test**

```python
def test_three_states_on_five_observations_is_reported_not_assumed():
    # E4's whole question. The test asserts the diagnostic exists and is
    # returned, not that it passes -- a failing identifiability check is a
    # finding, not a broken test.
    diag = expansion.hmm_diagnostics(X, k=3)
    assert {"state_persistence", "transition_condition", "loglik_vs_k2"} <= set(diag)


def test_a_degenerate_state_is_refused_rather_than_returned():
    # A state that captures <2% of observations is not a regime, it is an
    # outlier bucket, and P(B_t) > 0.60 on it means nothing.
    with pytest.raises(ValueError, match="degenerate"):
        ...
```

- [ ] **Steps 2–5: fail, implement, pass, commit. Then score the pre-commitment.**

**If E4's kill fires, drop §7 entirely** and let `r_hat_60_bp` carry the regime signal alone.
`p_build` and `p_expand` stay in the frame as NaN — removing a column is a seam change.

---

### Task 13: The trade score and the execution state machine *(Prathamesh)*

**Interfaces:**
- Consumes: `frame.FEATURES`, `frame.TradeCandidate`
- Produces: `fsm.score(row, weights) -> float`, `fsm.step(state, row) -> tuple[State, TradeCandidate | None]`

- [ ] **Step 1: Write the failing test**

```python
def test_a_hard_exclusion_overrides_a_passing_score():
    # §13 lists eight exclusions that override the score. A 0.95 score with
    # news lockout active must not produce a candidate.
    ...


def test_an_unfilled_limit_never_becomes_a_market_order():
    # §15's forbidden transition, and the one most likely to be added later
    # "just to catch the move".
    ...


def test_the_third_trade_of_a_day_is_refused():
    # §11: two trades per day, maximum.
    ...


def test_a_stop_is_never_widened():
    ...


def test_the_dead_flow_components_are_excluded_from_the_score_not_zeroed():
    # S_OFI, S_CVD and S_Hawkes are dead on spot. Scoring them as 0.0 with
    # their weights intact silently lowers every score by the sum of three
    # weights and makes the 0.72 threshold mean something different.
    ...
```

- [ ] **Steps 2–5: fail, implement, pass, commit.**

That last test is the subtle one: **§13's weights must be renormalised over the surviving six
components**, not left in place with three terms pinned to zero.

---

### Task 14: The purged, embargoed walk-forward tuner *(Varad)*

**Interfaces:**
- Produces: `tuning.folds(index, train_m, val_m, roll_m, label_minutes, embargo_days) -> list[tuple[Index, Index]]`; `tuning.Counter` (trial count); `tuning.deflated_sharpe(sr, n_trials, n_obs) -> float`

- [ ] **Step 1: Write the failing test**

```python
def test_a_label_crossing_a_fold_boundary_is_purged_from_training():
    # The leak §14 does not mention and which dominates here: a 90-minute
    # label opened at 15:00 on the last training day resolves inside
    # validation. Mutation-test it -- deleting the purge must turn this red.
    ...


def test_the_embargo_removes_a_further_trading_day():
    ...


def test_the_holdout_never_appears_in_any_fold():
    folds = tuning.folds(idx, train_m=24, val_m=6, roll_m=3, ...)
    for tr, va in folds:
        assert tr.max() < HOLDOUT_START and va.max() < HOLDOUT_START


def test_the_trial_counter_cannot_be_reset_by_the_caller():
    # The haircut is only honest if the count is. A counter the summary
    # writer can zero is not a guard.
    ...


def test_deflated_sharpe_falls_as_trials_rise():
    assert tuning.deflated_sharpe(1.2, n_trials=1, n_obs=500) > \
           tuning.deflated_sharpe(1.2, n_trials=200, n_obs=500)
```

- [ ] **Steps 2–5: fail, implement, pass, commit.**

- [ ] **Step 6: Seal the holdout with a sha256 manifest, committed before fold 1 runs**

```bash
uv run python -c "..." > analysis/HOLDOUT_MANIFEST.md
git add analysis/HOLDOUT_MANIFEST.md
git commit -m "chore(data): holdout sealed and hashed before the first fold"
```

**This commit must precede the fold-1 commit in history.** That ordering is the proof.

---

### Task 15: Run fold 1 and report it honestly *(Both)*

- [ ] **Step 1: Run fold 1 with the tuned set capped at three parameters**

Before searching, **write down the expected direction of each parameter's effect.** A profile that
comes back jagged and non-monotone is fitting noise — freeze that parameter at the spec's stated
value and record it.

- [ ] **Step 2: Report calibration, not just discrimination**

Brier score and a reliability diagram for `p_E`. **If the `[0.60, 0.64]` bucket does not fire near
62%, §8's threshold is void** and must be said to be.

- [ ] **Step 3: Report at all three costs, and both nulls**

No single-spread number appears anywhere in the write-up.

- [ ] **Step 4: Apply the deploy gate**

OOS Sharpe ≥ 0.5 × IS · OOS PF ≥ 1.0 · OOS win rate within 10pp of IS · **positive EV at 4.0 bp.**

- [ ] **Step 5: Write `analysis/FOLD1.md` and commit.**

*(Not `E5_…` — spec §6.5 already owns `E5` for the deferred GC order-flow control.)*

---

### Task 16: Close the three days *(Both)*

- [ ] **Step 1: Write `daily_updates/2026-09-20.md`**

Every claim carries its evidence. Include the two corrections spec §9 names: `SPOT_FEED_CHECK.md`'s
superseded verdict, and `Quant_Trading`'s `XAUUSD → GC=F` basis error.

- [ ] **Step 2: Update `plans/current.md`**

- [ ] **Step 3: Record the three suspended items as missed, by name**

`gates.md`'s rule, applied: **a missed date is recorded as missed and keeps the next slot.** The
MT5 desktop install, R7's depth check and the `vitest` add were suspended for these three days.
Write that down; do not let them quietly reappear.

- [ ] **Step 4: Full verification before the final commit**

```bash
uv run pytest -q && uv run ruff check . && uv run mypy .
```

Expected: **≥ 337 passed**, ruff clean, mypy clean. Paste the real output into the daily update —
`verification-before-completion`'s rule: evidence before assertions.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "docs: the 18-20 Sep block, and what it settled"
```

---

## Self-review — spec coverage

| Spec § | Covered by |
| :--- | :--- |
| §1 supersession and priors | Task 0 Step 6 (pre-commitments cite M1/M2/M3b) |
| §2 units, USD/oz | Task 0 (name rule in `require`), Task 4 (`to_bp`), Task 8 |
| §3.1 transport | Task 1 |
| §3.2–3.3 what dies | Task 3 Step 5 (SKIPPED rows), Task 13 (weight renormalisation) |
| §3.4 GC control (E5) | **Not scheduled.** Spec marks it optional; three days do not fit it. Recorded as deferred, not dropped |
| §4 cost model | Task 4 |
| §5.1 S13 seam | Task 0 |
| §5.2 lane split | Task ownership throughout |
| §5.3 model stack | Tasks 6–9, 12, 13 |
| §6.0–6.4 experiments | Tasks 1, 2, 3, 4, 12 |
| §7.1 split and holdout | Task 14 Step 6 |
| §7.2 purge and embargo | Task 14 |
| §7.3 parameter tiers | Task 15 Step 1 |
| §7.4 haircut | Task 14 |
| §7.5 calibration | Task 15 Step 2 |
| §7.6 costs and nulls | Task 15 Step 3 |
| §7.7 deploy gate | Task 15 Step 4 |
| §9 corrections | Task 16 Step 1 |

**One gap, named rather than hidden:** spec §3.4's E5 (the GC order-flow control) has no task. It is
optional in the spec and three days do not hold it. It is deferred to the first block after this one.
