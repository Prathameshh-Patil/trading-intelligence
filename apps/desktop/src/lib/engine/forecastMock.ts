/**
 * S7 · `engine/forecastMock.ts` — the reach table, served to the UI.
 *
 * **The probabilities here are real.** `public/fixtures/reach_table.json` is
 * `services/signal-data/analysis/reach_table.csv` (Varad, 10 Sep — 207,984
 * legs, 19 months, 116 minutes) filtered to its 8,256 served rows and stripped
 * to the five `SERVED` columns: 372 KB, against the 4.7 MB tick fixture
 * `mock.ts` already ships. Nothing in this file computes a probability.
 *
 * That is the same split `mock.ts` uses and for the same reason — its bars are
 * real and reconcile to `s1.py`, and only its outliers are invented shapes.
 *
 * **Where those rows are read from is now a switch.** `VITE_FORECAST_API` points
 * this at `services/api`'s S7 route; unset, it reads the committed copy and
 * `pnpm dev` needs nothing running. See `TABLE_URL`.
 *
 * ## What is still fake, and it is only one thing
 *
 * **Which cell the current moment is in.** There is no live feed, so `atr_bp`
 * and `vol_state` cannot be computed and are derived from the timestamp
 * instead. The `phase` is real — it comes from the committed ET boundaries.
 * Once `engine/real.ts` exists this file's only job disappears: the key comes
 * from the bars and the lookup is unchanged.
 *
 * ## What it is built to break
 *
 * Every state the trader meets and a happy path forgets: the two-hour warm-up,
 * a bucket the archive cannot answer (19% of the grid — 28 of 144 cells, and
 * `REACH.md` §2 shows they are concentrated, not scattered), a failed fetch,
 * and the load window before 372 KB has arrived.
 */

import {
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

/** The key `reach_table.json` is indexed by. `instrument` is omitted — GC only. */
function fixtureKey(c: ForecastCell): string {
  return `${c.atrBucket}|${c.phase}|${c.volState}|${c.side}`;
}

/**
 * One row as the fixture stores it, positionally.
 *
 * Positional rather than named because 8,256 of them as objects is roughly
 * three times the bytes for no gain — the order is declared in the fixture's
 * own `_row` field, and `rowOf` below is the only thing that reads it.
 */
type FixtureRow = [
  targetAtr: number,
  stopAtr: number,
  horizonMinutes: number,
  n: number,
  p: number,
  pMax: number,
  pStop: number,
  pNeither: number,
];

interface Fixture {
  minSamples: number;
  cells: Record<string, FixtureRow[]>;
  /** The column order the rows are stored in — checked, see `ROW`. */
  _row?: string[];
}

/**
 * `FixtureRow`'s fields, in the order `rowOf` reads them.
 *
 * `services/api` refuses to serve a table whose `_row` is not this, and the
 * same check runs here so the fixture path is not the unguarded one. A
 * transposed column is a wrong probability rendered with total confidence, and
 * a positional read cannot see the header move.
 */
const ROW = [
  "targetAtr",
  "stopAtr",
  "horizonMinutes",
  "n",
  "p",
  "pMax",
  "pStop",
  "pNeither",
] as const;

/** Throws rather than rendering a table whose columns are not where it thinks. */
function checkColumnOrder(t: Fixture, from: string): Fixture {
  // Absent is tolerated — a hand-cut table need not declare its order. Present
  // and different is not: that is a table that moved a column and said so.
  if (t._row && t._row.join() !== ROW.join()) {
    throw new Error(
      `${from}: column order is [${t._row.join(", ")}], but this reads ` +
        `[${ROW.join(", ")}] positionally`,
    );
  }
  return t;
}

function rowOf(r: FixtureRow): ReachRow {
  return {
    targetAtr: r[0],
    stopAtr: r[1],
    n: r[3],
    p: r[4],
    pMax: r[5],
    pStop: r[6],
    pNeither: r[7],
  };
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
  /** Resolves once the table has loaded (or failed). For tests and for waiting. */
  ready(): Promise<void>;
}

/**
 * Where the table comes from.
 *
 * Injectable for two reasons that are the same reason: the standalone check
 * runs under Node with no server to fetch a relative URL from, and the real
 * implementation loads this from `services/api` rather than a fixture. A seam
 * that only exists for tests tends to rot; **this one is now on the path** —
 * `GET /api/v1/forecast/table` serves the `Fixture` shape byte for byte, so
 * the swap below is a URL and nothing else.
 */
export type TableLoader = () => Promise<Fixture>;

/**
 * The committed copy — `public/fixtures/reach_table.json`, 372 KB.
 *
 * `contracts.md`'s fixture ledger exists so that both engineers can work
 * *"offline, on a plane, at 2am, with the other one asleep"*, so this stays the
 * default and `pnpm dev` needs no server running.
 */
export const FIXTURE_URL = "/fixtures/reach_table.json";

/**
 * Where the table is read from — the S7 route when `VITE_FORECAST_API` is set,
 * the committed fixture otherwise.
 *
 * **An env var rather than a hardcoded URL, because where the API lives is not
 * this file's decision.** `plans/current.md` row #4 is open and owned by both of
 * us; the popup's `http://localhost:8000` is a local convention, not a settled
 * answer, and baking it in here would close a room question by writing a string.
 *
 * The switch mirrors `VITE_ENGINE` deliberately, and so does its discipline:
 * **there is no fallback between the two.** If the route is configured and does
 * not answer, that is `no-table` — the wiring fault `forecast.ts` already names
 * — never a silent drop back to the committed copy. They are byte-identical
 * today, and the day they are not, "the app quietly served the stale one" is the
 * failure nobody can see from either end.
 *
 *     VITE_FORECAST_API=http://localhost:8000 pnpm dev
 */
export const TABLE_URL: string = import.meta.env.VITE_FORECAST_API
  ? `${String(import.meta.env.VITE_FORECAST_API).replace(/\/+$/, "")}/api/v1/forecast/table`
  : FIXTURE_URL;

const fetchFixture: TableLoader = async () => {
  const r = await fetch(TABLE_URL);
  if (!r.ok) throw new Error(`${TABLE_URL}: ${r.status}`);
  return checkColumnOrder((await r.json()) as Fixture, TABLE_URL);
};

export function createMockForecaster(
  now: () => number = Date.now,
  load: TableLoader = fetchFixture,
): MockForecaster {
  let mode: Mode = "normal";
  let connectedAt = now();
  let table: Fixture | null = null;
  let fetchFailed = false;

  /**
   * Fetch the table once, at construction.
   *
   * A failure is recorded rather than thrown: a forecaster that cannot answer
   * is a state this contract already has a name for, and crashing the panel
   * because one fixture 404'd would take the rest of the app with it.
   */
  const ready = load()
    .then((t) => {
      table = t;
    })
    .catch((e: unknown) => {
      fetchFailed = true;
      console.error("[forecast] table unavailable:", e);
    });

  function warming(): boolean {
    return mode === "warming" || now() - connectedAt < WARM_UP_MINUTES * 60_000;
  }

  function cellAt(t: number): ForecastCell | null {
    if (mode === "no-table" || mode === "warming") return null;
    if (mode === "clearing") return CLEARING_CELL;
    if (now() - connectedAt < WARM_UP_MINUTES * 60_000) return null;

    // The one thing still invented: with no feed there is no `atr_bp` and no
    // `rv_slope`, so both are derived from the 5-minute bar the timestamp falls
    // in — stable when re-read, and varying through a session the way the real
    // ones do. `phase` is real; it comes from the committed ET boundaries.
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
    if (mode === "no-table" || fetchFailed) return { forecast: null, unavailable: "no-table" };
    if (!table) return { forecast: null, unavailable: "loading" };
    if (mode === "thin") return { forecast: null, unavailable: "thin-bucket" };
    if (mode !== "clearing" && warming()) {
      return { forecast: null, unavailable: "warming-up" };
    }

    const cell = cellAt(t);
    if (!cell) return { forecast: null, unavailable: "no-key" };

    // A cell absent from the fixture is one the archive could not answer — the
    // thin rows were dropped when it was generated, so absence IS the floor
    // having been applied. Nothing here re-applies or second-guesses it, and
    // nothing widens the bucket to find an answer.
    const rows = table.cells[fixtureKey(cell)] ?? [];
    const reach = rows
      .filter((r) => r[2] === horizonMinutes)
      .map(rowOf)
      // **Grid order — target then stop — and never value order.** The CSV's own
      // row order is arbitrary, and sorting by `p` would quietly make the UI the
      // chooser that `reach.py` refuses to be: whatever lands on top of a list
      // reads as the recommendation, whether or not anything called it one.
      // `m1_sweep.TARGETS` x `STOPS` is the declared order and carries no opinion.
      .sort((a, b) => a.targetAtr - b.targetAtr || a.stopAtr - b.stopAtr);

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
      const loaded = table;
      const clearing = loaded
        ? cells.filter((c) => (loaded.cells[fixtureKey(c)] ?? []).length > 0).length
        : 0;
      return { cells: cells.length, clearing, fraction: clearing / cells.length };
    },
    ready() {
      return ready;
    },
  };
}
