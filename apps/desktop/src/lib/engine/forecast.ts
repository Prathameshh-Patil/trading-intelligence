/**
 * S7 · The forecast contract — the served reach table, as the UI consumes it.
 *
 * `docs/superpowers/specs/2026-09-05-live-signal-pipeline-design.md` §6.3
 * proposed `PipForecast` and said plainly it is **not frozen until all three
 * agree**. This file is the first time it exists in code, and it is
 * deliberately NOT a transcription of that draft: the draft was written
 * against Track A in early September, and `services/signal-data/reach.py`
 * (Varad, 9 Sep) now serves a table with a different shape.
 *
 * `strategy-precommit.md` §10 flagged the divergence and refused to reconcile
 * it there — *"S7 is a frozen-by-agreement contract and this file is not the
 * place"*. This is the place: the consumer that has to render the numbers,
 * proposing the shape it can actually render. **Still not frozen.** Four
 * differences from the draft, each one a thing the draft cannot express:
 *
 *  1. **`bucket.regime` is gone.** Track B's key has no regime axis —
 *     `regimes.py` clusters on `cvd_slope`/`cvd_persistence`, is parked, and
 *     does not port to spot at all. `reach.py`'s key is
 *     `instrument × atr_bp × phase × vol_state × side`, and the bucket a
 *     trader audits has to be the bucket the number came from.
 *
 *  2. **`reach[].p` becomes `p` AND `pMax`.** precommit §10 rule 2: every cell
 *     carries the tie band, never a midpoint. `p_target` reads same-bar ties to
 *     the stop, `p_target_max` reads them to the target, and no bar frame can
 *     say where inside that the truth is. M1 measured 10.2% of cells undecided
 *     by the band, and 20.45% of bars wide enough to tie at the grid's tight
 *     corner. **One number there is a precision the data does not have.**
 *
 *  3. **`horizonBars` becomes `horizonMinutes`.** The draft says `6` bars;
 *     `m1_sweep.HORIZONS` is `(15, 30, 60)` minutes against 5-minute bars. Two
 *     units that look alike at a glance and differ by 2x is the same class of
 *     bug as `DELTA_CVD_FINDINGS.md`'s inverted side — plausible on screen,
 *     wrong underneath. Minutes, because that is what the table was counted in.
 *
 *  4. **`mfe` and `mae` are nullable and null today.** `reach.SERVED` is
 *     `n, p_target, p_target_max, p_stop, p_neither` — stage 7 serves no
 *     excursion quantiles at all. They are kept rather than deleted because
 *     removing them is a scope decision for the room, not for this file; they
 *     are typed `| null` so that nothing can render an invented quantile while
 *     the table has none.
 *
 * The rules the draft set that this file keeps unchanged, because they are the
 * whole point of the contract: no `guaranteedPips` field ever, no lot size or
 * account-relative anything, `forecast: null` as a valid and common answer, and
 * `suggested` derived from `reach` or null — never picked.
 */

/** Long or short, matching `reach.py`'s `side` column exactly. */
export type ForecastSide = 1 | -1;

/**
 * `features/portable.py` `PHASES`, in ET wall clock. Prathamesh's six,
 * committed 2026-09-06 in `strategy-precommit.md` §4, before M3 ran.
 */
export type Phase = "Asia" | "Asia-London" | "London" | "London-NY" | "NY" | "NY-Asia";

/** `m2_magnitude.py` — `rv_slope` cut at ±0.20. */
export type VolState = "CONTRACTING" | "STABLE" | "EXPANDING";

/**
 * `ATR_BP_EDGES = (0.0, 7.0, 10.0, 14.0, inf)`, stringified by `pd.cut`.
 *
 * A string union rather than a number, because these arrive from the table as
 * pandas interval labels and round-tripping them through a float is how a
 * bucket boundary quietly moves.
 */
export type AtrBucket = "(0.0, 7.0]" | "(7.0, 10.0]" | "(10.0, 14.0]" | "(14.0, inf]";

/** `m1_sweep.HORIZONS`, minutes. See divergence 3 above. */
export type HorizonMinutes = 15 | 30 | 60;

/**
 * One bucket key — `reach.Cell`, field for field.
 *
 * Readonly for the same reason `Cell` is a frozen dataclass on the Python
 * side: *"a key that can be edited after a lookup is a key that can be edited
 * to find a better answer"*.
 */
export interface ForecastCell {
  readonly instrument: string;
  readonly atrBucket: AtrBucket;
  readonly phase: Phase;
  readonly volState: VolState;
  readonly side: ForecastSide;
}

/**
 * One bracket's answer, from `reach.SERVED`.
 *
 * `p` and `pMax` are the tie band and must be rendered as a band. A UI that
 * shows `p` alone, or shows their midpoint, has invented precision — see
 * divergence 2. `pStop` and `pNeither` are served alongside because a trader
 * auditing a forecast needs to know how often *nothing* happened, which is
 * frequently the largest of the three.
 */
export interface ReachRow {
  /** × the cell's own ATR. `m1_sweep.TARGETS`. */
  targetAtr: number;
  /** × the cell's own ATR. `m1_sweep.STOPS`. */
  stopAtr: number;
  /** Legs counted for THIS bracket. Not the cell's n — see `ForecastBucket.n`. */
  n: number;
  /** P(target first), same-bar ties read to the stop. The floor of the band. */
  p: number;
  /** P(target first), same-bar ties read to the target. The ceiling. */
  pMax: number;
  /** P(stop first). */
  pStop: number;
  /** P(neither barrier inside the horizon). Usually the biggest number here. */
  pNeither: number;
}

/** How the bucket was defined. The trader can audit this — that is its job. */
export interface ForecastBucket extends ForecastCell {
  horizonMinutes: HorizonMinutes;
  /**
   * The cell's leg count — the **max** across its brackets, which is what
   * `reach.main` groups by to decide whether a cell clears the floor. Each
   * `ReachRow` carries its own smaller `n`.
   */
  n: number;
}

/**
 * `MIN_SAMPLES`, transcribed. `strategy-precommit.md` §3 derives it rather than
 * picking it: `horizon.n_for_rate(0.1644, 0.224)` = 327, rounded up, where
 * 0.1644 is the pooled archive null and 0.224 the highest per-bucket breakeven.
 *
 * Here so the UI can *explain* a thin bucket, never to re-implement the floor —
 * the table already applied it and returned nothing.
 */
export const MIN_SAMPLES = 400;

export interface PipForecast {
  bucket: ForecastBucket;
  /**
   * Every bracket this cell can answer at this horizon, thin ones omitted.
   *
   * **An empty array is a real answer**, not an error: it says the bucket is
   * too thin at every one of the 72 grid points. Callers render that as no
   * forecast.
   */
  reach: ReachRow[];
  /** Not served by stage 7 today — divergence 4. Null, never invented. */
  mfe: { p25: number; median: number; p75: number } | null;
  /** Not served by stage 7 today — divergence 4. Null, never invented. */
  mae: { median: number; p75: number } | null;
  /**
   * Derived from `reach`, never chosen freely — draft rule 4, and
   * `reach.py`'s own first line: *"This module is a LOOKUP, not a chooser."*
   *
   * Null until a pass line is committed. Stage 9 owns that decision; nothing
   * in the UI may pick a bracket because it looks good on screen.
   */
  suggested: { targetAtr: number; stopAtr: number } | null;
}

/**
 * Why there is no forecast — for the UI, and **never for a number**.
 *
 * `reach.lookup` returns `None` for two reasons and says the caller *"must not
 * distinguish them into a forecast"*. That rule is about arithmetic: neither
 * reason may become a different, wider, or defaulted probability. It is not
 * about copy. What the trader is told has to differ, because the two demand
 * opposite responses — one is "wait", the other is "this will not answer today".
 */
export type ForecastUnavailable =
  /**
   * The feed has not been up long enough to form a key.
   *
   * **~120 minutes, not 60.** `reach.cell_of` spells this out: `vol_state`
   * reads `rv_slope`, which compares this hour's Parkinson volatility against
   * the previous hour's — two chained 60-minute windows. A just-connected feed
   * serves nothing for its first two hours, *"which is correct rather than
   * broken, and is worth saying out loud because it is otherwise discovered as
   * 'the product does not work at the open'."*
   *
   * That sentence is a UI requirement. This state must render as a countdown
   * to a real clock time, never as a spinner and never as an error.
   */
  | "warming-up"
  /** A key exists for neither this bar nor its window — a gap, or a stale feed. */
  | "no-key"
  /** Key formed, every bracket below `MIN_SAMPLES`. Honest and common. */
  | "thin-bucket"
  /** No table loaded at all. A wiring fault, not a market condition. */
  | "no-table";

/**
 * A forecast, or exactly one reason there isn't one.
 *
 * A discriminated union rather than `PipForecast | null` so that a consumer
 * cannot render "no forecast" without having said which of the four it is.
 */
export type ForecastResult =
  | { forecast: PipForecast; unavailable: null }
  | { forecast: null; unavailable: ForecastUnavailable };

/**
 * S7's seam. The UI asks; something behind this answers or declines.
 *
 * Mirrors `reach.py`'s two public functions — `cell_of` (bar → key) and
 * `reach` (key → the brackets it can answer) — so that the real
 * implementation, whenever it lands and whatever language it lands in, is
 * transcription rather than design.
 */
export interface Forecaster {
  /** The key for a moment, or null when no key can be formed. */
  cellAt(t: number): ForecastCell | null;
  /** Everything this cell can answer at one horizon. */
  forecastAt(t: number, horizonMinutes: HorizonMinutes): ForecastResult;
}
