"""E4 -- is a three-state HMM identifiable on the five portable observations?

`strategy-precommit.md` §17. `mathematical.md` §7 fits Chop / Build / Expansion
on eight observations; three of them (OFI_z, CVD_z, lambda_t) died with the
tape. This module fits the same model on what survives and asks the only
question that matters: does k=3 separate anything k=2 does not?

THE OBSERVATIONS, AND WHERE EACH COMES FROM. All five are derived from the S13
frame (`features/frame.FEATURES`); nothing is computed from ticks here.

    r_hat_60_bp         log(r_hat_60_usd / mid * 1e4)   the hourly forecast, in bp
    h_dfa_15m           as is                            one Hurst estimator, not two --
                                                         `h_vt` disagrees with it 75% of
                                                         the time (2026-09-18 §21), and a
                                                         second column that says so is
                                                         noise, not information
    spread_bp           log                              NaN on GC, real on spot
    range_compression   log(sigma_yz_12 / sigma_yz_288)  short vs long range estimator;
                                                         negative is compressed
    sigma_ratio         log(r_ratio)                     §2's R_hat / trailing median

`range_compression` has no frame column. `features/portable.py` takes no new
function without a standup, so it is derived here and its definition is
recorded in §17 -- if the room wants it in the frame, that is a seam change.

Logs make a Gaussian emission adequate for ratios that are lognormal-ish;
there is no Student-t and the pre-commit does not ask for one.

E4a AND E4b. GC has no spread (one tick, degenerate; `pipeline.py`), so
`observations(..., spread=False)` runs on FOUR observations and is E4a. Once
Route 2's spot pull is on disk the same code runs `spread=True` on five and is
E4b, in a new directory. §17's own "most likely wrong #1" says spread is the
one observation that could rescue §7, so E4a's verdict is provisional by
construction and E4b's is the one that closes the question.

THE THRESHOLDS ARE CONSTANTS, NOT FLAGS. `m2_magnitude.TRAIN` froze the split
for the reason `m3_profile` did: a number that can be passed at the prompt is
a number that can be tried twice. Every one of these is pinned by a test and
recorded in §17 before the fit runs.

    PYTHONPATH=. uv run python e4_hmm.py --data data --no-spread --out-dir analysis/e4_hmm_<date>

**Do not run this until §17's prediction is committed.** The module exists so
the code is reviewed before the number exists; the run is Varad's.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

import hmm
import pipeline
from features.regime_filter import regime_kappa
from m2_magnitude import TRAIN

OBS: tuple[str, ...] = ("r_hat_60_bp", "h_dfa_15m", "spread_bp", "range_compression", "sigma_ratio")
VOL_OBS: tuple[str, ...] = ("r_hat_60_bp", "range_compression", "sigma_ratio")

SEEDS = (0, 1, 2, 3, 4)
K_CANDIDATES = (2, 3)

# §17's refusals and decisions, in the order `decide` applies them.
MIN_SHARE = 0.02        # a state under 2% of bars is an outlier bucket, not a regime
MIN_STAY = 0.80         # every A_ii; the prior fit's states held 0.80-0.84
MIN_KAPPA = 0.75        # persistence above the state's own base rate, one hour ahead
MAX_COND = 50.0         # cond(A); a near-singular transition matrix is not a chain
MIN_SEP = 1.0           # min Mahalanobis distance between any two state means
MIN_DELTA_LL = 0.05     # held-out loglik per bar, k=3 over k=2, to call separation
LADDER_TOL = 0.25       # sd; states within this on the non-vol obs are a vol ladder
KAPPA_HORIZON = 12      # bars: one hour at 5 minutes

Outcome = Literal["outcome_1", "outcome_2", "outcome_3"]


def observations(frame: pd.DataFrame, *, spread: bool) -> pd.DataFrame:
    """OBS columns (minus spread if `spread=False`) plus `segment`, NaN rows dropped.

    A segment is a run of consecutive bars inside one session. Dropping a NaN
    row splits the run: the chain must not step across a bar it never saw.
    """
    if spread and not frame["spread_bp"].notna().any():
        raise ValueError("spread=True but spread_bp is all NaN -- this is GC; run E4a with spread=False")

    out = pd.DataFrame(index=frame.index)
    out["r_hat_60_bp"] = np.log(frame["r_hat_60_usd"] / frame["mid"] * 1e4)
    out["h_dfa_15m"] = frame["h_dfa_15m"]
    if spread:
        out["spread_bp"] = np.log(frame["spread_bp"])
    out["range_compression"] = np.log(frame["sigma_yz_12"] / frame["sigma_yz_288"])
    out["sigma_ratio"] = np.log(frame["r_ratio"])
    out = out.replace([np.inf, -np.inf], np.nan)

    keep = out.notna().all(axis=1)
    session = frame["session"].astype(str)
    # A new segment starts at a session change, or after any dropped row.
    pos = np.arange(len(frame))
    prev_kept = pd.Series(pos, index=frame.index).where(keep).ffill().shift(1)
    gap = (pos - prev_kept.to_numpy()) != 1
    new_seg = gap | (session != session.shift(1)).to_numpy()
    out["segment"] = np.cumsum(new_seg & keep.to_numpy())
    return out[keep].copy()


@dataclass(frozen=True, slots=True)
class Scaler:
    names: tuple[str, ...]
    mean: np.ndarray
    sd: np.ndarray

    def transform(self, obs: pd.DataFrame) -> np.ndarray:
        return ((obs[list(self.names)].to_numpy(dtype=float) - self.mean) / self.sd)


def standardise(obs: pd.DataFrame, *, fit_mask: pd.Series) -> tuple[np.ndarray, Scaler]:
    """Z-scores, with mean and sd taken from `fit_mask` rows ONLY.

    A scaler fit on the whole sample leaks the held-out half's level into the
    training half's units -- the same trap `r_ratio` names for its median.
    """
    names = tuple(c for c in obs.columns if c != "segment")
    fit = obs.loc[fit_mask, list(names)].to_numpy(dtype=float)
    sd = fit.std(axis=0, ddof=1)
    if (sd == 0).any():
        raise ValueError(f"zero variance in {[n for n, s in zip(names, sd, strict=True) if s == 0]}")
    scaler = Scaler(names=names, mean=fit.mean(axis=0), sd=sd)
    return scaler.transform(obs), scaler


def lengths_of(obs: pd.DataFrame) -> np.ndarray:
    """Run lengths of `segment`, in order, for `hmm`'s `lengths`."""
    seg = obs["segment"].to_numpy()
    if not (np.diff(seg) >= 0).all():
        raise ValueError("segments must be contiguous and increasing")
    _, counts = np.unique(seg, return_counts=True)
    return counts


def label_states(m: hmm.GaussianHMM, names: tuple[str, ...]) -> dict[str, int]:
    """E is the state with the highest r_hat mean, C the lowest, B whatever is left.

    Only meaningful for k=3; for k=2 there is no B and the dict has C and E.
    """
    r = m.means[:, names.index("r_hat_60_bp")]
    order = np.argsort(r)
    if m.k == 2:
        return {"C": int(order[0]), "E": int(order[1])}
    return {"C": int(order[0]), "B": int(order[1]), "E": int(order[2])}


@dataclass(frozen=True, slots=True)
class Diagnostics:
    k: int
    train_ll_per_bar: float
    heldout_ll_per_bar: float
    bic: float
    share_viterbi: tuple[float, ...]
    share_gamma: tuple[float, ...]
    stay: tuple[float, ...]
    kappa: tuple[float, ...]
    cond_A: float
    min_mahalanobis: float
    means: tuple[tuple[float, ...], ...]
    is_ladder: bool


def _mahalanobis_min(m: hmm.GaussianHMM) -> float:
    best = np.inf
    for i in range(m.k):
        for j in range(i + 1, m.k):
            pooled = 0.5 * (m.covs[i] + m.covs[j])
            diff = m.means[i] - m.means[j]
            best = min(best, float(np.sqrt(diff @ np.linalg.solve(pooled, diff))))
    return best


def _is_ladder(m: hmm.GaussianHMM, names: tuple[str, ...]) -> bool:
    """Monotone on every vol observation and flat on the rest: two states and a rung.

    Means are in standardised units, so `LADDER_TOL` is in sd.
    """
    if m.k < 3:
        return False
    order = np.argsort(m.means[:, names.index("r_hat_60_bp")])
    vol = [names.index(c) for c in VOL_OBS if c in names]
    other = [i for i in range(len(names)) if i not in vol]
    for c in vol:
        col = m.means[order, c]
        if not ((np.diff(col) > 0).all() or (np.diff(col) < 0).all()):
            return False
    return all(float(np.ptp(m.means[:, c])) <= LADDER_TOL for c in other)


def diagnose(m: hmm.GaussianHMM, X: np.ndarray, lengths: np.ndarray, *,
             names: tuple[str, ...], train: np.ndarray, sessions: pd.Series,
             index: pd.Index) -> Diagnostics:
    """Everything §17 asks to be read off a fit, on one model."""
    n_train, n_held = int(train.sum()), int((~train).sum())
    ll_train = hmm.loglik(m, X[train], lengths_of_mask(lengths, train))
    ll_held = hmm.loglik(m, X[~train], lengths_of_mask(lengths, ~train)) if n_held else np.nan

    path = hmm.viterbi(m, X, lengths)
    gamma = hmm.posteriors(m, X, lengths)
    share_v = np.bincount(path, minlength=m.k) / len(path)
    share_g = gamma.mean(axis=0)

    bars = pd.DataFrame({"regime": path, "session": sessions.to_numpy()}, index=index)
    kappa = regime_kappa(bars, horizon_bars=KAPPA_HORIZON).reindex(range(m.k)).to_numpy()

    d = X.shape[1]
    n_params = (m.k - 1) + m.k * (m.k - 1) + m.k * d + m.k * d * (d + 1) / 2
    return Diagnostics(
        k=m.k,
        train_ll_per_bar=ll_train / n_train,
        heldout_ll_per_bar=float(ll_held / n_held) if n_held else np.nan,
        bic=float(-2 * ll_train + n_params * np.log(n_train)),
        share_viterbi=tuple(float(s) for s in share_v),
        share_gamma=tuple(float(s) for s in share_g),
        stay=tuple(float(a) for a in np.diag(m.A)),
        kappa=tuple(float(x) for x in kappa),
        cond_A=float(np.linalg.cond(m.A)),
        min_mahalanobis=_mahalanobis_min(m),
        means=tuple(tuple(float(v) for v in row) for row in m.means),
        is_ladder=_is_ladder(m, names),
    )


def lengths_of_mask(lengths: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Segment lengths restricted to `mask` rows; segments the mask empties vanish."""
    out = []
    start = 0
    for length in lengths:
        n = int(mask[start:start + length].sum())
        if n:
            out.append(n)
        start += length
    return np.asarray(out, dtype=np.int64)


def decide(d2: Diagnostics, d3: Diagnostics) -> Outcome:
    """§17's three outcomes, applied in the order the section states them.

    1. A degenerate state, or a chain that does not persist -> §7 dropped.
    3. k=3 fits no better than k=2 on held-out bars, or is a vol ladder -> two
       states and a parameter; treated as 1.
    2. Only when every check passes.
    """
    if min(d3.share_viterbi) < MIN_SHARE or min(d3.share_gamma) < MIN_SHARE:
        return "outcome_1"
    if min(d3.stay) < MIN_STAY or np.nanmin(d3.kappa) < MIN_KAPPA:
        return "outcome_1"
    if d3.cond_A > MAX_COND or d3.min_mahalanobis < MIN_SEP:
        return "outcome_1"
    if d3.heldout_ll_per_bar - d2.heldout_ll_per_bar < MIN_DELTA_LL:
        return "outcome_3"
    if d3.is_ladder:
        return "outcome_3"
    return "outcome_2"


def apply(frame: pd.DataFrame, m: hmm.GaussianHMM, scaler: Scaler,
          labels: dict[str, int]) -> pd.DataFrame:
    """Outcome 2 only: fill `p_build` and `p_expand` on a built S13 frame.

    `p_build` is the FILTERED P(B_t | x_1..t). `p_expand` is
    P(S_{t+1} = E | x_1..t) = (filtered @ A)[:, E] -- §7's event, one step
    ahead, from what was knowable at t. Neither reads a smoothed posterior.
    Rows the observations dropped keep NaN: not measured, never zero.
    """
    if "B" not in labels:
        raise ValueError("apply needs a k=3 model with a B state; k=2 has nothing to fill")
    obs = observations(frame, spread="spread_bp" in scaler.names)
    f = hmm.filtered(m, scaler.transform(obs), lengths_of(obs))
    out = frame.copy()
    out.loc[obs.index, "p_build"] = f[:, labels["B"]]
    out.loc[obs.index, "p_expand"] = (f @ m.A)[:, labels["E"]]
    return out


def best_of_seeds(X: np.ndarray, lengths: np.ndarray, *, k: int) -> hmm.GaussianHMM:
    """Best training log-likelihood over `SEEDS`. EM is local; five starts is the hedge."""
    best: tuple[float, hmm.GaussianHMM] | None = None
    for seed in SEEDS:
        m, trace = hmm.fit(X, lengths, k=k, seed=seed)
        if best is None or trace[-1] > best[0]:
            best = (trace[-1], m)
    assert best is not None
    return best[1]


def model_json(m: hmm.GaussianHMM, scaler: Scaler, labels: dict[str, int]) -> dict[str, object]:
    return {
        "pi": m.pi.tolist(), "A": m.A.tolist(), "means": m.means.tolist(),
        "covs": m.covs.tolist(), "names": list(scaler.names),
        "scaler_mean": scaler.mean.tolist(), "scaler_sd": scaler.sd.tolist(),
        "labels": labels,
    }


def load_bars(data: Path) -> pd.DataFrame:
    """Nineteen months of GC as one 5-minute frame. One build, not nineteen:
    `r_ratio` needs 5,760 bars of history and a per-month build resets it."""
    from regimes import resample_bars
    from s1 import load_ticks, minute_bars

    months = sorted(p for p in data.iterdir() if p.is_dir() and p.name[:4].isdigit())
    if not months:
        raise SystemExit(f"no month directories under {data}")
    frames = [resample_bars(minute_bars(load_ticks(p)), "5min") for p in months]
    return pd.concat(frames).sort_index()


def run(frame: pd.DataFrame, *, spread: bool) -> tuple[dict[int, Diagnostics], Outcome,
                                                       dict[int, hmm.GaussianHMM], Scaler]:
    obs = observations(frame, spread=spread)
    month = pd.DatetimeIndex(obs.index).strftime("%Y-%m")
    train = pd.Series(np.isin(month, TRAIN), index=obs.index)
    X, scaler = standardise(obs, fit_mask=train)
    lengths = lengths_of(obs)
    sessions = frame.loc[obs.index, "session"]

    models: dict[int, hmm.GaussianHMM] = {}
    diags: dict[int, Diagnostics] = {}
    for k in K_CANDIDATES:
        tr = train.to_numpy()
        models[k] = best_of_seeds(X[tr], lengths_of_mask(lengths, tr), k=k)
        diags[k] = diagnose(models[k], X, lengths, names=scaler.names, train=tr,
                            sessions=sessions, index=obs.index)
    return diags, decide(diags[2], diags[3]), models, scaler


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--spread", dest="spread", action="store_true")
    p.add_argument("--no-spread", dest="spread", action="store_false")
    p.set_defaults(spread=None)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--events", type=Path, default=None, help="CSV of event timestamps, UTC")
    a = p.parse_args()
    if a.spread is None:
        raise SystemExit("say --spread (E4b, spot) or --no-spread (E4a, GC) explicitly")
    if a.out_dir.exists():
        raise SystemExit(f"{a.out_dir} exists; a new run gets a new directory (regimes.py §6.2)")

    t0 = time.perf_counter()
    bars = load_bars(a.data)
    events = (pd.DatetimeIndex(pd.read_csv(a.events)["ts"], tz="UTC") if a.events
              else pd.DatetimeIndex([], tz="UTC"))
    frame = pipeline.build(bars, events=events)
    print(f"frame: {len(frame):,} bars  {time.perf_counter() - t0:.0f}s", flush=True)

    diags, outcome, models, scaler = run(frame, spread=a.spread)
    a.out_dir.mkdir(parents=True)
    pd.DataFrame([asdict(d) for d in diags.values()]).to_csv(a.out_dir / "diagnostics.csv",
                                                             index=False)
    for k, m in models.items():
        (a.out_dir / f"model_k{k}.json").write_text(
            json.dumps(model_json(m, scaler, label_states(m, scaler.names)), indent=2))
    (a.out_dir / "outcome.txt").write_text(outcome + "\n")
    for d in diags.values():
        print(f"k={d.k}  held-out ll/bar {d.heldout_ll_per_bar:.4f}  shares {d.share_viterbi}"
              f"  stay {d.stay}  cond {d.cond_A:.1f}  ladder {d.is_ladder}")
    print(f"{outcome}  {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
