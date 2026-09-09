/**
 * S7 · `engine/forecastMock.ts` — the fake reach table.
 *
 * `contracts.md`'s rule: whoever owns a seam ships the type and a fake on the
 * first day the seam exists, and the consumer builds against the fake. S7's
 * real table is `services/signal-data/analysis/reach_table.csv`, which is a
 * ~1.7-hour build on 19 months of archive, is gitignored, and does not exist on
 * this machine. The UI cannot wait for it and does not need to.
 *
 * ## What is real here and what is not
 *
 * **Real, and transcribed rather than invented:** the six phase boundaries and
 * their ET wall-clock rule (`features/portable.py` `_PHASE_EDGES`), the four
 * `atr_bp` buckets, the three vol states, the 72-point bracket grid, the
 * `MIN_SAMPLES = 400` floor, the ~120-minute warm-up, and the shape of every
 * answer.
 *
 * **Not real — and not citable, ever:** every probability and every leg count.
 * They are plausible *shapes* for laying out a UI, produced by a crude closed
 * form. No threshold here was derived from anything and none of it is evidence
 * about gold. The archive's actual numbers live in `analysis/M1_SURFACE.md` and
 * are Varad's.
 *
 * ## Why the numbers are deterministic
 *
 * A lookup table returns the same answer for the same key, forever. If this
 * fake used `Math.random`, a UI that re-queries on every render would show
 * numbers that shimmer, and the bug would look like a data problem rather than
 * a render problem. Same key, same answer — including across reloads.
 *
 * ## What it is built to break
 *
 * The three states that are common in production and absent from a happy path:
 * a feed inside its two-hour warm-up, a bucket too thin to answer, and an empty
 * `reach` array from a cell that clears the floor at no bracket at all.
 */

import {
  MIN_SAMPLES,
  type AtrBucket,
  type ForecastCell,
  type ForecastResult,
  type ForecastSide,
  type Forecaster,
  type HorizonMinutes,
  type Phase,
  type PipForecast,
  type ReachRow,
  type VolState,
} from "./forecast";

/** `m1_sweep.TARGETS`, × the cell's ATR. */
const TARGETS = [0.75, 1.0, 1.5, 2.0, 3.0, 4.0] as const;
/** `m1_sweep.STOPS`, × the cell's ATR. */
const STOPS = [0.5, 0.75, 1.0, 1.5] as const;

const BUCKETS: AtrBucket[] = ["(0.0, 7.0]", "(7.0, 10.0]", "(10.0, 14.0]", "(14.0, inf]"];
const STATES: VolState[] = ["CONTRACTING", "STABLE", "EXPANDING"];

/**
 * `features/portable.py` `_PHASE_EDGES` / `_PHASE_CUTS`, transcribed.
 *
 * Minutes past ET midnight, half-open `[from, to)` — `pd.cut(..., right=False)`.
 * Asia appears twice because the day wraps; `Asia-London` is exactly one hour,
 * which is why it is the thinnest phase in the table and why `strategy-precommit.md`
 * §10 predicted its cells would be the ones that fail to clear the floor.
 */
const PHASE_EDGES: ReadonlyArray<readonly [number, number, Phase]> = [
  [0, 120, "Asia"],
  [120, 180, "Asia-London"],
  [180, 480, "London"],
  [480, 570, "London-NY"],
  [570, 810, "NY"],
  [810, 1080, "NY-Asia"],
  [1080, 1440, "Asia"],
];

/**
 * `reach.cell_of`: two chained 60-minute windows before `vol_state` exists.
 *
 * Not 60. `rv_slope` compares this hour's Parkinson volatility to the previous
 * hour's, so a just-connected feed has no key for its first two hours. The
 * comment in `reach.py` is explicit that this is *"correct rather than broken"*
 * and is worth saying out loud, because otherwise it gets discovered as "the
 * product does not work at the open".
 */
export const WARM_UP_MINUTES = 120;

/**
 * Minutes past midnight in **ET wall clock**, DST included.
 *
 * `PHASE_TZ = "America/New_York"` and the boundaries are wall clock, not UTC —
 * `portable.py` is emphatic that a frozen UTC number is an hour wrong for five
 * months of the archive. `Intl` is used rather than a fixed −5/−4 offset for
 * exactly that reason.
 */
function etMinutes(t: number): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(t));

  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? "0");
  // `hour12: false` renders midnight as 24 in some ICU versions.
  return (get("hour") % 24) * 60 + get("minute");
}

function phaseAt(t: number): Phase {
  const m = etMinutes(t);
  for (const [from, to, phase] of PHASE_EDGES) {
    if (m >= from && m < to) return phase;
  }
  // Unreachable: the edges cover [0, 1440). Thrown rather than defaulted,
  // because a silent fallback would file bars under a phase they are not in.
  throw new Error(`no phase for ET minute ${m}`);
}

/** FNV-1a. Small, stable across reloads, and not trying to be a hash function. */
function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** A stable [0, 1) from a key. Same key, same value, forever. */
function unit(key: string): number {
  return hash(key) / 0x100000000;
}

function cellKey(c: ForecastCell): string {
  return `${c.instrument}|${c.atrBucket}|${c.phase}|${c.volState}|${c.side}`;
}

/** Every key in the table. 6 phases × 4 buckets × 3 states × 2 sides = 144. */
function allCells(): ForecastCell[] {
  const out: ForecastCell[] = [];
  for (const atrBucket of BUCKETS) {
    // 0..5: Asia appears twice in PHASE_EDGES where the day wraps, and counting
    // it twice would enumerate 168 cells instead of 144.
    for (const [, , phase] of PHASE_EDGES.slice(0, 6)) {
      for (const volState of STATES) {
        for (const side of [1, -1] as ForecastSide[]) {
          out.push({ instrument: "GC", atrBucket, phase, volState, side });
        }
      }
    }
  }
  return out;
}

/**
 * Legs per cell — **measured, not modelled.**
 *
 * Taken from `services/signal-data/analysis/reach_table.csv` (Varad, 10 Sep):
 * the max `n` across each cell's brackets, which is what `reach.main` groups by
 * to decide whether a cell clears. `side` is not in the key because both sides
 * evaluate the same bars and their counts are identical in all 72 — checked,
 * not assumed.
 *
 * **This replaced a synthetic weight model, and the replacement is the point.**
 * The model multiplied independent phase/bucket/state weights and was tuned to
 * `strategy-precommit.md` §10's prediction of "a third to a half" of cells
 * clearing. `REACH.md` §1 measured **81%**, and §2 found the two axes are not
 * independent at all: `London-NY` runs 4.7% CONTRACTING against 59.4%
 * EXPANDING, because a 90-minute handoff window containing the 08:30 release is
 * by construction a place where volatility is rising. Both transition phases
 * lose their entire CONTRACTING state — 16 of the 28 dead cells.
 *
 * No product of independent weights reproduces that, and a fake that smooths it
 * away would teach the layout that thin cells are scattered when they are in
 * fact concentrated in two identifiable corners.
 */
const CELL_LEGS: Record<string, number> = {
  "(0.0, 7.0]|Asia|CONTRACTING": 3450,
  "(0.0, 7.0]|Asia|EXPANDING": 2074,
  "(0.0, 7.0]|Asia|STABLE": 5078,
  "(0.0, 7.0]|Asia-London|CONTRACTING": 107,
  "(0.0, 7.0]|Asia-London|EXPANDING": 428,
  "(0.0, 7.0]|Asia-London|STABLE": 638,
  "(0.0, 7.0]|London|CONTRACTING": 1758,
  "(0.0, 7.0]|London|EXPANDING": 565,
  "(0.0, 7.0]|London|STABLE": 4132,
  "(0.0, 7.0]|London-NY|CONTRACTING": 38,
  "(0.0, 7.0]|London-NY|EXPANDING": 143,
  "(0.0, 7.0]|London-NY|STABLE": 310,
  "(0.0, 7.0]|NY|CONTRACTING": 1131,
  "(0.0, 7.0]|NY|EXPANDING": 29,
  "(0.0, 7.0]|NY|STABLE": 558,
  "(0.0, 7.0]|NY-Asia|CONTRACTING": 2599,
  "(0.0, 7.0]|NY-Asia|EXPANDING": 279,
  "(0.0, 7.0]|NY-Asia|STABLE": 3637,
  "(10.0, 14.0]|Asia|CONTRACTING": 1827,
  "(10.0, 14.0]|Asia|EXPANDING": 2107,
  "(10.0, 14.0]|Asia|STABLE": 3137,
  "(10.0, 14.0]|Asia-London|CONTRACTING": 87,
  "(10.0, 14.0]|Asia-London|EXPANDING": 605,
  "(10.0, 14.0]|Asia-London|STABLE": 579,
  "(10.0, 14.0]|London|CONTRACTING": 929,
  "(10.0, 14.0]|London|EXPANDING": 1426,
  "(10.0, 14.0]|London|STABLE": 3484,
  "(10.0, 14.0]|London-NY|CONTRACTING": 113,
  "(10.0, 14.0]|London-NY|EXPANDING": 1427,
  "(10.0, 14.0]|London-NY|STABLE": 807,
  "(10.0, 14.0]|NY|CONTRACTING": 2121,
  "(10.0, 14.0]|NY|EXPANDING": 634,
  "(10.0, 14.0]|NY|STABLE": 2324,
  "(10.0, 14.0]|NY-Asia|CONTRACTING": 672,
  "(10.0, 14.0]|NY-Asia|EXPANDING": 457,
  "(10.0, 14.0]|NY-Asia|STABLE": 1394,
  "(14.0, inf]|Asia|CONTRACTING": 1487,
  "(14.0, inf]|Asia|EXPANDING": 2482,
  "(14.0, inf]|Asia|STABLE": 2485,
  "(14.0, inf]|Asia-London|CONTRACTING": 94,
  "(14.0, inf]|Asia-London|EXPANDING": 542,
  "(14.0, inf]|Asia-London|STABLE": 375,
  "(14.0, inf]|London|CONTRACTING": 558,
  "(14.0, inf]|London|EXPANDING": 1274,
  "(14.0, inf]|London|STABLE": 1905,
  "(14.0, inf]|London-NY|CONTRACTING": 118,
  "(14.0, inf]|London-NY|EXPANDING": 1888,
  "(14.0, inf]|London-NY|STABLE": 770,
  "(14.0, inf]|NY|CONTRACTING": 1905,
  "(14.0, inf]|NY|EXPANDING": 2902,
  "(14.0, inf]|NY|STABLE": 4374,
  "(14.0, inf]|NY-Asia|CONTRACTING": 469,
  "(14.0, inf]|NY-Asia|EXPANDING": 759,
  "(14.0, inf]|NY-Asia|STABLE": 1107,
  "(7.0, 10.0]|Asia|CONTRACTING": 2373,
  "(7.0, 10.0]|Asia|EXPANDING": 2240,
  "(7.0, 10.0]|Asia|STABLE": 3647,
  "(7.0, 10.0]|Asia-London|CONTRACTING": 199,
  "(7.0, 10.0]|Asia-London|EXPANDING": 512,
  "(7.0, 10.0]|Asia-London|STABLE": 718,
  "(7.0, 10.0]|London|CONTRACTING": 1669,
  "(7.0, 10.0]|London|EXPANDING": 1565,
  "(7.0, 10.0]|London|STABLE": 5155,
  "(7.0, 10.0]|London-NY|CONTRACTING": 72,
  "(7.0, 10.0]|London-NY|EXPANDING": 894,
  "(7.0, 10.0]|London-NY|STABLE": 746,
  "(7.0, 10.0]|NY|CONTRACTING": 1872,
  "(7.0, 10.0]|NY|EXPANDING": 169,
  "(7.0, 10.0]|NY|STABLE": 1528,
  "(7.0, 10.0]|NY-Asia|CONTRACTING": 1232,
  "(7.0, 10.0]|NY-Asia|EXPANDING": 544,
  "(7.0, 10.0]|NY-Asia|STABLE": 2279,
};

/** Below this the archive has no row at all — distinct from "thin", same answer. */
function cellLegs(c: ForecastCell): number {
  return CELL_LEGS[`${c.atrBucket}|${c.phase}|${c.volState}`] ?? 0;
}

/**
 * Legs surviving to one horizon.
 *
 * Longer horizons lose the legs at the tail of each month with no room left to
 * run. Shared by `bracketRow` and `coverage` so the two cannot drift into
 * disagreeing about which cells clear.
 */
function bracketLegs(cellN: number, horizon: HorizonMinutes): number {
  return Math.round(cellN * (1 - (horizon / 60) * 0.06));
}

/**
 * One bracket's numbers.
 *
 * The closed form is deliberately crude and is documented so nobody mistakes it
 * for a model: for a driftless walk with barriers at `target` and `stop`, first
 * touch splits as `stop / (target + stop)`, and the horizon truncates both by
 * however much of the distance the price can cover in the time. `p_neither`
 * takes the remainder, and is usually the largest of the three — which is the
 * one qualitative fact about this table a trader most needs the UI to survive.
 */
function bracketRow(c: ForecastCell, targetAtr: number, stopAtr: number, horizon: HorizonMinutes, cellN: number): ReachRow | null {
  // ATR is a 60-minute window, so a 15-minute horizon covers ~sqrt(15/60) of it.
  const reachable = Math.sqrt(horizon / 60);
  const pTouch = Math.min(0.97, reachable / (0.5 * (targetAtr + stopAtr)));

  const split = stopAtr / (targetAtr + stopAtr);
  const wobble = (unit(`p:${cellKey(c)}:${targetAtr}:${stopAtr}:${horizon}`) - 0.5) * 0.06;

  const p = Math.max(0, Math.min(1, pTouch * split + wobble));
  const pStop = Math.max(0, Math.min(1 - p, pTouch * (1 - split) - wobble));
  const pNeither = Math.max(0, 1 - p - pStop);

  /**
   * The tie band, widest at the tight corner of the grid.
   *
   * M1 measured 20.45% of bars wide enough to tie at (0.75, 0.5) — a 5-minute
   * bar that contains both barriers cannot say which came first. The band
   * narrows fast as the brackets widen, and is near zero at (4.0, 1.5).
   */
  /**
   * Calibrated to `REACH.md` §3, which measured the real band across 8,256
   * served rows: **max 0.107, p90 0.018, p50 0.002**, and wider than 0.05 on
   * only 1.0% of them. The first version of this used M1's 20.45% tie *rate* as
   * a band width and produced 0.198 at the tight corner — nearly twice the
   * widest band that exists in the real table. The squared decay is what keeps
   * the median near zero while leaving the tight corner wide, which is the
   * shape §3 describes: "costs almost nothing across the bulk of the table and
   * earns its place entirely at the tight corner".
   */
  const tieRate = 0.107 * Math.pow(Math.min(1, (0.75 / targetAtr) * (0.5 / stopAtr)), 2);

  /**
   * The ambiguous mass MOVES between the two readings; it is not clipped.
   *
   * A leg whose bar contains both barriers counts to the stop under `p_target`
   * and to the target under `p_target_max` — so the ceiling is the floor plus
   * however much of the stop's mass is ambiguous, bounded by the stop's mass
   * itself. Clamping to `1 - pStop` instead (the first version of this)
   * squeezed the band hardest exactly where `pStop` is largest, which is the
   * tight corner — inverting M1's actual finding that ties are *most* common
   * there, and teaching the layout that uncertainty shrinks as brackets tighten.
   */
  const pMax = p + Math.min(tieRate * pTouch, pStop);

  const n = bracketLegs(cellN, horizon);
  if (n < MIN_SAMPLES) return null;

  return { targetAtr, stopAtr, n, p, pMax, pStop, pNeither };
}

/** Every state a fake has to be able to be, on demand. */
type Mode = "normal" | "warming" | "thin" | "no-table" | "clearing";

/**
 * A cell known to clear the floor, for `forceClearing`.
 *
 * The fattest corner of the weights: the longest, busiest phase against the
 * densest bucket in the most common vol state. Needed because 58% of cells are
 * thin, so the *populated* state is the one a developer cannot reach by waiting
 * — and `contracts.md`'s rule for `keys_fake` is that every branch is reachable
 * on demand rather than only when the data happens to be in that state.
 */
const CLEARING_CELL: ForecastCell = {
  instrument: "GC",
  atrBucket: "(7.0, 10.0]",
  phase: "London-NY",
  volState: "STABLE",
  side: 1,
};

export interface MockForecaster extends Forecaster {
  /** Pretend the feed just connected — two hours of `warming-up`. */
  restartWarmUp(): void;
  /** Skip the warm-up, as if the feed has been up all session. */
  finishWarmUp(): void;
  /** Every lookup returns `thin-bucket`, whatever the key. */
  forceThin(): void;
  /** No table at all — the wiring-fault state. */
  forceNoTable(): void;
  /**
   * Pin every lookup to a cell that clears, so the populated layout can be
   * inspected without waiting for the clock to land in one of the 42%.
   */
  forceClearing(): void;
  /** Back to answering normally. */
  resume(): void;
  /**
   * How many of the 144 cells clear `MIN_SAMPLES` at their best bracket.
   *
   * The reconciliation check for this file, and the reason it is worth having:
   * `strategy-precommit.md` §10 predicts **between a third and a half** before
   * the real table was built. A fake that disagrees with that prediction is a
   * fake that will teach the UI the wrong lesson about how often it has to
   * render nothing.
   */
  coverage(): { cells: number; clearing: number; fraction: number };
}

export function createMockForecaster(now: () => number = Date.now): MockForecaster {
  let mode: Mode = "normal";
  let connectedAt = now();

  function cellAt(t: number): ForecastCell | null {
    if (mode === "no-table" || mode === "warming") return null;
    if (mode === "clearing") return CLEARING_CELL;
    if (now() - connectedAt < WARM_UP_MINUTES * 60_000) return null;

    // A real cell's bucket and state come from the bars. This fake derives them
    // from the 5-minute bar the timestamp falls in, so they vary through a
    // session the way the real ones do and are stable when re-read.
    const bar = Math.floor(t / 300_000);
    return {
      instrument: "GC",
      atrBucket: BUCKETS[hash(`b:${bar}`) % BUCKETS.length],
      phase: phaseAt(t),
      volState: STATES[hash(`v:${Math.floor(bar / 12)}`) % STATES.length],
      side: (hash(`s:${bar}`) % 2 === 0 ? 1 : -1) as ForecastSide,
    };
  }

  function forecastAt(t: number, horizonMinutes: HorizonMinutes): ForecastResult {
    if (mode === "no-table") return { forecast: null, unavailable: "no-table" };
    if (mode === "thin") return { forecast: null, unavailable: "thin-bucket" };
    if (mode !== "clearing" && (mode === "warming" || now() - connectedAt < WARM_UP_MINUTES * 60_000)) {
      return { forecast: null, unavailable: "warming-up" };
    }

    const cell = cellAt(t);
    if (!cell) return { forecast: null, unavailable: "no-key" };

    const cellN = cellLegs(cell);
    const reach: ReachRow[] = [];
    for (const target of TARGETS) {
      for (const stop of STOPS) {
        const row = bracketRow(cell, target, stop, horizonMinutes, cellN);
        if (row) reach.push(row);
      }
    }

    // Clears at no bracket at all — the honest empty answer, and the one a
    // happy-path layout forgets exists.
    if (reach.length === 0) return { forecast: null, unavailable: "thin-bucket" };

    const forecast: PipForecast = {
      bucket: { ...cell, horizonMinutes, n: Math.max(...reach.map((r) => r.n)) },
      reach,
      // Stage 7 serves no excursion quantiles. Null, never invented.
      mfe: null,
      mae: null,
      // Derived from `reach` or null, and there is no committed pass line to
      // derive it with. `reach.py`: "This module is a LOOKUP, not a chooser."
      suggested: null,
    };
    return { forecast, unavailable: null };
  }

  return {
    cellAt,
    forecastAt,
    restartWarmUp() {
      mode = "normal";
      connectedAt = now();
    },
    finishWarmUp() {
      mode = "normal";
      connectedAt = now() - WARM_UP_MINUTES * 60_000 - 1;
    },
    forceThin() {
      mode = "thin";
    },
    forceNoTable() {
      mode = "no-table";
    },
    forceClearing() {
      mode = "clearing";
    },
    resume() {
      mode = "normal";
    },
    coverage() {
      const cells = allCells();
      // The 15-minute horizon keeps the most legs, so a cell that clears
      // anywhere clears there.
      const clearing = cells.filter((c) => bracketLegs(cellLegs(c), 15) >= MIN_SAMPLES).length;
      return { cells: cells.length, clearing, fraction: clearing / cells.length };
    },
  };
}
