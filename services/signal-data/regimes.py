#!/usr/bin/env python3
"""
Stage 2 of the GC strategy selector -- regime features, clustering, labels.

See docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md
    §2  "Two stages, and the first one can kill the second" (Stage 2)
    §6  Guardrails 2 and 4

WHAT THIS DOES
    Cluster minute-bar state into 2-3 regimes on features derived only from
    price and order flow -- never from a strategy's entries, exits, or
    returns -- and write the labels plus a committable record of exactly how
    they were produced.

STATE ONLY, NEVER OUTCOME (§2's leakage rule)
    Every feature is computed from a TRAILING window ending at each bar's own
    close. None of them may see the bar's forward return or any strategy's
    result -- if one ever does, the design leaks and every regime label after
    it is fiction. This file has no import of, and no dependency on,
    backtest.py or strategies/gc.py, and it must never gain one: that
    boundary is what keeps this module honest. All `rolling()` calls below
    are backward-looking by construction (pandas default); none may become
    `center=True`.

WHAT THIS DELIBERATELY DOES NOT DO
    - Does not measure per-strategy performance inside regimes -- that is
      select.py, and it does not exist yet (Stage 1 -- the strategies
      themselves -- is undecided per §9 Q1).
    - Does not pick a strategy. Regimes are unsupervised over state alone.
    - Does not decide bar size or window-vs-session granularity for you.
      §9 Q2 and Q3 are recorded as open questions ("cheap to test, so test
      rather than assume") -- --bar-size and --level make both cheap to try
      instead of silently defaulting.

GUARDRAIL §6.2 -- READ BEFORE RUNNING THIS AGAINST REAL STRATEGIES
    "Pre-commit the regime definitions. Clustering fitted, labelled,
    committed -- before anyone looks at per-strategy performance inside
    those regimes." Commit this run's --out-dir output (the labels CSV and
    regime_definitions.json) to git before select.py ever reads it. The json
    records the exact bar size, window, level, k, split date and random seed
    so the run is reproducible, which is what makes "committed before
    results" mean anything.

GUARDRAIL §6.4 -- WALK-FORWARD, NEVER IN-SAMPLE
    "Fit regimes on the first half, test selection on the second." Pass
    --split-date so the KMeans model is FIT only on bars/sessions before that
    date; every bar in range still gets LABELLED (via .predict), but nothing
    after the split contributes to where the cluster boundaries sit. Omit
    --split-date and this script still runs, but it prints a loud warning and
    the labels it writes are not walk-forward-safe -- fine for a first look
    at whether clusters look like anything, not fine as the committed
    definitions in §6.2.

A KNOWN SPEC DISCREPANCY -- FLAGGED, NOT SILENTLY RESOLVED
    §2's feature table defines "Directional efficiency" as
    `abs(CVD) / price range` and cites 2026-07-16's 0.90 as the number that
    validates the feature. But that 0.90 was actually produced by
    compute_delta_cvd.py's session auto-select using
    `abs(close - open) / range` on PRICE ALONE -- no CVD anywhere in it. The
    two formulas are not the same quantity: abs(CVD)/range mixes contracts
    against price units and is unbounded; abs(close-open)/range is
    dimensionless and bounded in [0, 1] (a Kaufman-style efficiency ratio).
    Rather than guess which one was meant, both are computed as separate
    features -- `cvd_efficiency_specced` (literal §2 formula) and
    `price_efficiency_asused` (what actually produced the cited number) --
    and this needs a decision from Varad before regime definitions using
    either one get pre-committed for real. See regime_definitions.json's
    "known_spec_ambiguity" field.

USAGE
    python regimes.py --parquet data/gc_trades.parquet \
        --bar-size 5min --window 12 --vol-window-min 30 \
        --level window --k 3 --split-date 2026-07-19 \
        --no-session-phase-in-clustering --out-dir analysis/regimes

ON THE S1 FIXTURE (data/fixtures/gc_ticks_1session.parquet)
    An earlier version of this file imported compute_delta_cvd.add_delta(),
    which only matched the pipeline's post-mapped buy_initiated/sell_initiated
    strings and silently read the fixture's raw 'B'/'A'/'N' encoding as zero
    delta on every row. s1.py's SIDES map (see s1.load_ticks) is exhaustive
    over both encodings, so this file now goes through s1.py instead and the
    fixture works -- but it is one session (77,532 trades), too thin on its
    own for k=2/3 clustering to mean anything. Fine for an import/plumbing
    smoke test; use --parquet data/gc_trades.parquet for anything real.

TESTED (2026-08-26, against data/gc_trades.parquet, GC July 2026, 23
sessions, walk-forward split at 2026-07-19):
    - window level, bar_size=5min, window=12 bars, k=3, session-phase
      dummies INCLUDED in clustering: recovers almost exactly "which
      session" (regimes were 100.0/0/0, 0/100.0/0, 0/0/100.0 percent
      asia/london/ny) rather than a volatility/flow distinction -- the
      one-hot dummies dominate a Euclidean KMeans after standardization.
    - Same run with --no-session-phase-in-clustering: regimes split roughly
      evenly across sessions instead (34-41% each) and separate on
      cvd_persistence (0.22 / 0.25 / 0.67 median) and cvd_slope (-0.6 / +0.2
      / -12.9 median) -- i.e. one persistent/trending regime versus two
      churnier ones. This looks like the more useful split; --no-session-
      phase-in-clustering is worth defaulting to once Varad has eyeballed
      both, but it is left an explicit flag rather than silently decided
      here.
    - level=session, k=2: runs, correctly hits the n<30 guardrail warning
      (23 sessions total) -- confirms §9 Q3's own prediction that
      session-level regimes are too thin to trust, without having to take
      that on faith.

Requires: pandas, numpy, scikit-learn, pyarrow, matplotlib (all already used
elsewhere in this directory).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from compute_delta_cvd import DISPLAY_TZ
from s1 import SESSION_SHIFT, load_ticks, minute_bars

SPEC = "docs/superpowers/specs/2026-08-25-gc-strategy-selector-design.md"

KNOWN_SPEC_AMBIGUITY = (
    "§2's feature table defines directional efficiency as abs(CVD)/price "
    "range and cites 2026-07-16's 0.90 as validating it, but that 0.90 was "
    "actually produced by compute_delta_cvd.py's session auto-select using "
    "abs(close-open)/range on price alone, no CVD. Both are computed here "
    "as separate features (cvd_efficiency_specced, price_efficiency_asused) "
    "pending a decision on which was intended -- do not pre-commit regime "
    "definitions built on either one without resolving this first."
)

# Regime palette -- categorical, not diverging (regimes aren't a signed
# quantity). Kept muted and distinct from compute_delta_cvd's buy/sell blue
# so a reader never confuses a regime plot for a delta plot at a glance.
REGIME_COLORS = ["#2a78d6", "#c98a2b", "#4caf7d", "#9457c9"]  # up to 4 regimes
C_PRICE = "#0b0b0b"
C_SURFACE = "#fcfcfb"
C_GRID = "#e1e0d9"
C_AXIS = "#c3c2b7"
C_MUTED = "#898781"
C_SECONDARY = "#52514e"

FEATURE_COLS = [
    "realized_vol",
    "cvd_slope",
    "cvd_persistence",
    "cvd_efficiency_specced",
    "price_efficiency_asused",
]


# --------------------------------------------------------------------------
# Session phase -- Asia / London / NY from the ET clock, boundaries matched
# to the 18:00 ET session open used everywhere else in this project
# (compute_delta_cvd.SESSION_SHIFT / DELTA_CVD_FINDINGS §2).
# --------------------------------------------------------------------------
def session_phase(idx: pd.DatetimeIndex) -> pd.Series:
    et = idx.tz_convert(DISPLAY_TZ)
    hour = et.hour + et.minute / 60.0
    conditions = [
        (hour >= 18) | (hour < 3),   # Globex open through the Asia session
        (hour >= 3) & (hour < 8),    # London
        (hour >= 8) & (hour < 17),   # NY -- session closes 17:00 ET
    ]
    choices = ["asia", "london", "ny"]
    # The 17:00-18:00 ET daily maintenance halt has no bars, so the fallback
    # value is never actually hit -- kept only so the function is total.
    return pd.Series(np.select(conditions, choices, default="asia"), index=idx)


# --------------------------------------------------------------------------
# Bar resampling -- 1-minute bars (from compute_delta_cvd.minute_bars) rolled
# up to whatever --bar-size regime features are computed at. cvd is
# RE-DERIVED from the resampled delta rather than downsampled from the
# 1-minute cvd column, so a bar's cvd always agrees with its own delta sum.
# --------------------------------------------------------------------------
def resample_bars(bars_1min: pd.DataFrame, bar_size: str) -> pd.DataFrame:
    if bar_size in ("1min", "1T"):
        return bars_1min.copy()
    agg = bars_1min.resample(bar_size).agg(
        delta=("delta", "sum"),
        volume=("volume", "sum"),
        trades=("trades", "sum"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    )
    agg = agg[agg["trades"] > 0].copy()
    agg["session"] = (agg.index + SESSION_SHIFT).date
    agg["cvd"] = agg.groupby("session", sort=False)["delta"].cumsum()
    return agg


# --------------------------------------------------------------------------
# Shared math -- realized vol, CVD slope, CVD persistence, both efficiency
# variants -- computed over an arbitrary slice of bars in time order. Used
# both inside a rolling window (window level) and over a whole session
# (session level), so the two --level modes can never quietly diverge in
# what "the feature" means.
# --------------------------------------------------------------------------
def _slope(y: np.ndarray) -> float:
    if len(y) < 2:
        return np.nan
    x = np.arange(len(y), dtype="float64")
    return float(np.polyfit(x, y, 1)[0])


def _cvd_persistence(delta: np.ndarray) -> float:
    abs_sum = np.abs(delta).sum()
    if abs_sum == 0:
        return np.nan
    return float(abs(delta.sum()) / abs_sum)


def _efficiency_pair(delta: np.ndarray, close: np.ndarray, high: np.ndarray,
                      low: np.ndarray) -> tuple[float, float]:
    price_range = float(high.max() - low.min())
    if price_range <= 0:
        return np.nan, np.nan
    cvd_eff = float(abs(delta.sum()) / price_range)          # §2, literal
    price_eff = float(abs(close[-1] - close[0]) / price_range)  # as actually used
    return cvd_eff, price_eff


def realized_vol_1min(bars_1min: pd.DataFrame, window_minutes: int) -> pd.Series:
    """Stdev of 1-min returns over a trailing WALL-CLOCK window. §2 pins
    this feature to 1-min returns specifically, independent of whatever
    --bar-size the other features are computed at, so it is always derived
    from the 1-minute bar frame regardless of --bar-size."""
    ret = bars_1min["close"].pct_change()
    return ret.rolling(f"{window_minutes}min").std()


# --------------------------------------------------------------------------
# Level: window -- one feature row per regime bar, trailing --window bars.
# --------------------------------------------------------------------------
def window_features(bars_1min: pd.DataFrame, regime_bars: pd.DataFrame,
                     window: int, vol_window_min: int) -> pd.DataFrame:
    n = len(regime_bars)
    delta = regime_bars["delta"].to_numpy()
    close = regime_bars["close"].to_numpy()
    high = regime_bars["high"].to_numpy()
    low = regime_bars["low"].to_numpy()
    cvd = regime_bars["cvd"].to_numpy()

    slope = np.full(n, np.nan)
    persistence = np.full(n, np.nan)
    cvd_eff = np.full(n, np.nan)
    price_eff = np.full(n, np.nan)

    for i in range(n):
        if i + 1 < window:
            continue
        lo = i + 1 - window
        slope[i] = _slope(cvd[lo:i + 1])
        persistence[i] = _cvd_persistence(delta[lo:i + 1])
        cvd_eff[i], price_eff[i] = _efficiency_pair(
            delta[lo:i + 1], close[lo:i + 1], high[lo:i + 1], low[lo:i + 1]
        )

    feat = regime_bars.copy()
    feat["cvd_slope"] = slope
    feat["cvd_persistence"] = persistence
    feat["cvd_efficiency_specced"] = cvd_eff
    feat["price_efficiency_asused"] = price_eff
    feat["session_phase"] = session_phase(feat.index)

    vol = realized_vol_1min(bars_1min, vol_window_min)
    feat = pd.merge_asof(
        feat.sort_index(),
        vol.rename("realized_vol").to_frame().sort_index(),
        left_index=True, right_index=True, direction="backward",
    )
    return feat


# --------------------------------------------------------------------------
# Level: session -- one feature row per CME session, whole-session window.
# §9 Q3 flags this as very thin (~22 rows for a month) but explicitly worth
# testing rather than assuming away.
# --------------------------------------------------------------------------
def session_features(bars_1min: pd.DataFrame, regime_bars: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for session, g in regime_bars.groupby("session", sort=True):
        delta = g["delta"].to_numpy()
        close = g["close"].to_numpy()
        high = g["high"].to_numpy()
        low = g["low"].to_numpy()
        cvd_eff, price_eff = _efficiency_pair(delta, close, high, low)
        phases = session_phase(g.index)
        rows.append({
            "session": session,
            "n_bars": len(g),
            "cvd_slope": _slope(g["cvd"].to_numpy()),
            "cvd_persistence": _cvd_persistence(delta),
            "cvd_efficiency_specced": cvd_eff,
            "price_efficiency_asused": price_eff,
            "pct_asia": float((phases == "asia").mean() * 100),
            "pct_london": float((phases == "london").mean() * 100),
            "pct_ny": float((phases == "ny").mean() * 100),
        })
    feat = pd.DataFrame(rows).set_index("session")

    # realized_vol per session: stdev of 1-min returns over the WHOLE
    # session, from the 1-minute frame, per §2's "1-min returns" wording.
    vol_by_session = (
        bars_1min.assign(ret=bars_1min["close"].pct_change())
        .groupby("session")["ret"].std()
    )
    feat["realized_vol"] = vol_by_session.reindex(feat.index)
    return feat


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------
def build_feature_matrix(feat: pd.DataFrame, level: str,
                          include_session_phase: bool = True) -> pd.DataFrame:
    """NOTE on include_session_phase: one-hot session dummies sit at {0,1}
    and, after StandardScaler, separate maximally (distance sqrt(2) between
    any two sessions, zero overlap) -- in a first test run against the full
    July month this alone was enough for KMeans to recover almost exactly
    "which session" rather than a volatility/flow distinction, at k=3 with
    the other four features included. §2 lists session phase as one of the
    four canonical features, so it stays in by default, but --no-session-
    phase-in-clustering exists specifically to compare against that finding
    before pre-committing regime definitions (§6.2) -- this is exactly the
    kind of thing worth eyeballing rather than assuming."""
    if level == "window":
        parts = [feat[FEATURE_COLS]]
        if include_session_phase:
            dummies = pd.get_dummies(feat["session_phase"], prefix="session")
            for col in ("session_asia", "session_london", "session_ny"):
                if col not in dummies:
                    dummies[col] = 0.0
            parts.append(dummies)
        X = pd.concat(parts, axis=1)
    else:
        cols = list(FEATURE_COLS)
        if include_session_phase:
            cols += ["pct_asia", "pct_london", "pct_ny"]
        X = feat[cols].copy()
    return X


def fit_regimes(feat: pd.DataFrame, level: str, k: int, fit_mask: pd.Series | None,
                 random_state: int, include_session_phase: bool = True):
    X = build_feature_matrix(feat, level, include_session_phase)
    valid = X.notna().all(axis=1)

    walk_forward_safe = fit_mask is not None
    if fit_mask is None:
        fit_rows = valid
        print(
            "\nWARNING: no --split-date given -- fitting on the full frame. "
            "This is NOT walk-forward-safe (§6.4). Fine for a first look; "
            "not fine as the committed regime definitions (§6.2)."
        )
    else:
        fit_rows = valid & fit_mask
        if fit_rows.sum() == 0:
            sys.exit("--split-date leaves zero rows to fit on. Check the date.")

    scaler = StandardScaler().fit(X.loc[fit_rows])
    km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    km.fit(scaler.transform(X.loc[fit_rows]))

    labels = pd.Series(index=feat.index, dtype="float64")
    labels.loc[valid] = km.predict(scaler.transform(X.loc[valid])).astype("float64")

    return {
        "labels": labels,
        "valid": valid,
        "fit_rows": fit_rows,
        "scaler": scaler,
        "km": km,
        "X": X,
        "walk_forward_safe": walk_forward_safe,
        "feature_cols": list(X.columns),
    }


def silhouette_preview(X: pd.DataFrame, fit_rows: pd.Series, random_state: int,
                        max_sample: int = 5000) -> dict[int, float]:
    """§6's guardrail caps regimes at 2-3. Report silhouette for both so the
    choice of --k is informed rather than assumed. Subsampled above
    max_sample rows -- silhouette is O(n^2) and doesn't need the whole month
    to give a stable read."""
    Xf = X.loc[fit_rows].dropna()
    if len(Xf) > max_sample:
        Xf = Xf.sample(max_sample, random_state=random_state)
    scores = {}
    for k in (2, 3):
        if len(Xf) <= k:
            continue
        scaler = StandardScaler().fit(Xf)
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(scaler.transform(Xf))
        scores[k] = silhouette_score(scaler.transform(Xf), km.labels_)
    return scores


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def summarize_regimes(feat: pd.DataFrame, labels: pd.Series, valid: pd.Series,
                       level: str) -> pd.DataFrame:
    rows = []
    n_total = int(valid.sum())
    for r in sorted(labels.dropna().unique()):
        mask = valid & (labels == r)
        sub = feat.loc[mask]
        row = {
            "regime": int(r),
            "n": int(mask.sum()),
            "pct": round(mask.sum() / n_total * 100, 1) if n_total else np.nan,
            "realized_vol_med": round(sub["realized_vol"].median(), 6),
            "cvd_slope_med": round(sub["cvd_slope"].median(), 3),
            "cvd_persistence_med": round(sub["cvd_persistence"].median(), 3),
            "cvd_eff_specced_med": round(sub["cvd_efficiency_specced"].median(), 3),
            "price_eff_asused_med": round(sub["price_efficiency_asused"].median(), 3),
        }
        if level == "window":
            phases = sub["session_phase"]
            row["pct_asia"] = round((phases == "asia").mean() * 100, 1)
            row["pct_london"] = round((phases == "london").mean() * 100, 1)
            row["pct_ny"] = round((phases == "ny").mean() * 100, 1)
        else:
            row["pct_asia"] = round(sub["pct_asia"].mean(), 1)
            row["pct_london"] = round(sub["pct_london"].mean(), 1)
            row["pct_ny"] = round(sub["pct_ny"].mean(), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def plot_regimes(feat: pd.DataFrame, labels: pd.Series, valid: pd.Series,
                  level: str, out_path: Path) -> None:
    if level != "window":
        return  # session-level has too few points for a timeline plot
    tz = DISPLAY_TZ
    idx = feat.index.tz_convert(tz)
    regimes = sorted(labels.dropna().unique())
    color_map = {r: REGIME_COLORS[i % len(REGIME_COLORS)] for i, r in enumerate(regimes)}

    fig, axes = plt.subplots(
        2, 1, figsize=(13, 7), sharex=True,
        gridspec_kw={"height_ratios": [2.0, 1.2], "hspace": 0.12},
    )
    fig.patch.set_facecolor(C_SURFACE)

    ax = axes[0]
    ax.set_facecolor(C_SURFACE)
    ax.grid(True, color=C_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    # Plot the price LINE per session, not across the whole index in one
    # call -- a single ax.plot over the full month draws a straight line
    # through every weekend and the daily 17:00-18:00 ET halt, as if price
    # moved continuously across them. compute_delta_cvd.plot_month_cvd
    # avoids exactly this by looping per session; do the same here. The
    # regime-colored scatter below is unaffected either way since scatter
    # never connects points.
    for _, seg in feat.groupby("session", sort=True):
        seg_idx = seg.index.tz_convert(tz)
        ax.plot(seg_idx, seg["close"], color=C_PRICE, linewidth=0.7, zorder=1)
    for r in regimes:
        mask = (valid & (labels == r)).to_numpy()
        ax.scatter(idx[mask], feat["close"].to_numpy()[mask], s=4,
                   color=color_map[r], label=f"regime {r}", zorder=2)
    ax.set_ylabel("Price (USD/oz)", color=C_SECONDARY, fontsize=10)
    ax.set_title("Regime labels over price (Stage 2, unsupervised on state features only)",
                 color="#0b0b0b", fontsize=12, pad=12, loc="left", fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, frameon=False)

    ax = axes[1]
    ax.set_facecolor(C_SURFACE)
    ax.grid(True, color=C_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.axhline(0, color=C_AXIS, linewidth=1.0)
    for r in regimes:
        mask = (valid & (labels == r)).to_numpy()
        ax.scatter(idx[mask], feat["cvd"].to_numpy()[mask], s=4, color=color_map[r], zorder=2)
    ax.set_ylabel("CVD", color=C_SECONDARY, fontsize=10)
    ax.set_xlabel(f"Time ({tz})", color=C_SECONDARY, fontsize=10)

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet", default="data/gc_trades.parquet")
    ap.add_argument("--bar-size", default="5min",
                    help="Regime feature bar size (§9 Q2 -- open question, test freely). "
                         "e.g. 1min, 5min, 15min.")
    ap.add_argument("--window", type=int, default=30,
                    help="Trailing window, in bar COUNT at --bar-size, for CVD slope/"
                         "persistence/efficiency. Not minutes -- see the --bar-size note.")
    ap.add_argument("--vol-window-min", type=int, default=30,
                    help="Trailing window in MINUTES for realized_vol, always computed "
                         "from 1-min returns per §2, independent of --bar-size.")
    ap.add_argument("--level", choices=["window", "session"], default="window",
                    help="§9 Q3 -- open question. window = one label per bar (more labels, "
                         "autocorrelated). session = one label per day (~22/month, thin).")
    ap.add_argument("--k", type=int, default=3, choices=[2, 3],
                    help="§6 guardrail: 2-3 regimes, not more.")
    ap.add_argument("--split-date", default=None,
                    help="YYYY-MM-DD (ET session date). Fit KMeans only on bars/sessions "
                         "strictly before this date; label everything. Omit only for an "
                         "exploratory look -- required for §6.4 walk-forward-safe output.")
    ap.add_argument("--random-state", type=int, default=0)
    ap.add_argument("--out-dir", default="analysis/regimes")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--no-session-phase-in-clustering", action="store_true",
                    help="Exclude session-phase one-hot dummies from the clustering "
                         "features (they are still computed and reported). See "
                         "build_feature_matrix's docstring: in a full-month test, "
                         "session dummies alone were enough to make KMeans recover "
                         "'which session' rather than a volatility/flow distinction.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_ticks(Path(args.parquet))  # s1.py: reads + validates + adds delta/session
    bars_1min = minute_bars(df)
    print(f"loaded {len(df):,} trades -> {len(bars_1min):,} 1-min bars "
          f"across {bars_1min['session'].nunique()} session(s)")

    regime_bars = resample_bars(bars_1min, args.bar_size)
    print(f"resampled to {len(regime_bars):,} bars at --bar-size {args.bar_size}")

    if args.level == "window":
        feat = window_features(bars_1min, regime_bars, args.window, args.vol_window_min)
    else:
        feat = session_features(bars_1min, regime_bars)

    fit_mask = None
    if args.split_date:
        split = pd.Timestamp(args.split_date).date()
        if args.level == "window":
            fit_mask = pd.Series((feat.index.tz_convert(DISPLAY_TZ).date < split), index=feat.index)
        else:
            fit_mask = pd.Series(feat.index < split, index=feat.index)
        print(f"walk-forward split: fitting on rows before {split}, "
              f"labelling all {len(feat):,} rows")

    include_session_phase = not args.no_session_phase_in_clustering
    result = fit_regimes(feat, args.level, args.k, fit_mask, args.random_state,
                          include_session_phase)
    labels = result["labels"]

    sil = silhouette_preview(result["X"], result["fit_rows"], args.random_state)
    if sil:
        print("\nsilhouette preview (higher = more separated clusters; capped at k=3 per §6):")
        for k, s in sorted(sil.items()):
            marker = "  <- used" if k == args.k else ""
            print(f"  k={k}: {s:.3f}{marker}")

    summary = summarize_regimes(feat, labels, result["valid"], args.level)
    print(f"\nregime summary ({args.level}-level, bar_size={args.bar_size}, "
          f"k={args.k}, walk_forward_safe={result['walk_forward_safe']}):")
    print(summary.to_string(index=False))

    under_n = summary[summary["n"] < 30]
    if not under_n.empty:
        print(f"\nWARNING (§6.5 -- N next to every number): "
              f"{len(under_n)} regime(s) have n<30 -- report these, do not act on them.")

    # ---- write outputs ----------------------------------------------------
    tag = f"{args.level}_{args.bar_size}_k{args.k}"
    labels_path = out_dir / f"regime_labels_{tag}.csv"
    out_feat = feat.copy()
    out_feat["regime"] = labels
    out_feat.to_csv(labels_path)
    print(f"\nwrote labels -> {labels_path}")

    definitions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec": SPEC,
        "parquet": str(args.parquet),
        "bar_size": args.bar_size,
        "window_bars": args.window,
        "vol_window_minutes": args.vol_window_min,
        "level": args.level,
        "k": args.k,
        "split_date": args.split_date,
        "walk_forward_safe": result["walk_forward_safe"],
        "include_session_phase_in_clustering": include_session_phase,
        "random_state": args.random_state,
        "feature_cols": result["feature_cols"],
        "n_labelled": int(result["valid"].sum()),
        "n_fit": int(result["fit_rows"].sum()),
        "silhouette": {str(k): v for k, v in sil.items()},
        "scaler_mean": result["scaler"].mean_.tolist(),
        "scaler_scale": result["scaler"].scale_.tolist(),
        "cluster_centers_standardized": result["km"].cluster_centers_.tolist(),
        "regime_summary": summary.to_dict(orient="records"),
        "known_spec_ambiguity": KNOWN_SPEC_AMBIGUITY,
    }
    defs_path = out_dir / f"regime_definitions_{tag}.json"
    defs_path.write_text(json.dumps(definitions, indent=2))
    print(f"wrote regime definitions -> {defs_path}")

    if not args.no_plot:
        plot_path = out_dir / f"regime_plot_{tag}.png"
        plot_regimes(feat, labels, result["valid"], args.level, plot_path)
        if plot_path.exists():
            print(f"wrote plot -> {plot_path}")

    if not result["walk_forward_safe"]:
        print(
            "\nNOT COMMITTED-SAFE: rerun with --split-date before treating this as the "
            "§6.2 pre-committed regime definition."
        )
    else:
        print(
            "\nNext per §6.2: review regime_definitions.json and the plot, then "
            f"git add {labels_path} {defs_path} and commit BEFORE select.py or any "
            "strategy backtest looks at these regimes."
        )


if __name__ == "__main__":
    main()
