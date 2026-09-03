/**
 * S2 · `engine/mock.ts` — the fake engine, W1D2.
 *
 * Replays the S1 fixture session (2026-07-16, 77,532 GC trades) at 10x and
 * emits `DeltaBar` / `Outlier` / `FeedStatus` through S2's `Engine` interface,
 * so every UI surface in Weeks 1-3 can be built and broken without a tick of
 * live data and without Varad's engine existing.
 *
 * **The point of this file is that it misbehaves on demand.** `contracts.md`
 * S2 is explicit that Prathamesh writes it "because he is the one who needs it
 * to behave badly on demand" — a layout that breaks on a 7-digit CVD should
 * break here in Week 1, on a Sunday, not in Week 3 against a live feed.
 *
 * ## What is real here and what is not
 *
 * The **bars are real**: barred from the committed fixture with the same
 * conventions `services/signal-data/s1.py` uses, and the whole session
 * reconciles to the numbers that file produces (see `RECONCILIATION` below).
 *
 * The **outliers are not real** — they are plausible *shapes* for laying out a
 * UI, produced by a deliberately crude rule. Nothing here is evidence about
 * gold, no threshold in it was derived from anything, and none of it may ever
 * be cited as a result. Stage 1's candidates live in
 * `services/signal-data/strategies.py` and are Varad's.
 */

import type {
  CaptureContext,
  DeltaBar,
  Engine,
  FeedCreds,
  FeedStatus,
  Outlier,
  Side,
  Unsubscribe,
} from "./types";

/** One row of `public/fixtures/gc_ticks_1session.json`. */
interface FixtureTick {
  t: number;
  price: number;
  size: number;
  /** S1's raw encoding, deliberately not squeezed into `Side` by the exporter. */
  side: "B" | "A" | "N";
}

interface Fixture {
  symbol: string;
  session: string;
  rowCount: number;
  ticks: FixtureTick[];
}

/**
 * The whole-session numbers `s1.py` produces from the same fixture, asserted at
 * load. They are the discriminating check on the mapping below: an inverted
 * `B`/`A` gives a session delta of -1,842 rather than +1,842, and a mapping
 * that folds `'N'` into either side moves `volume` off 110,817 — both of which
 * look entirely plausible on screen.
 */
export const RECONCILIATION = {
  ticks: 77_532,
  sessionDelta: 1_842,
  volume: 110_817,
} as const;

/**
 * S1 `aggressor_side` → S2 `DeltaBar` volumes. **Read the comment before
 * changing a letter of this.**
 *
 * `s1.py` is authoritative: `SIDES = {"B": 1, "A": -1, "N": 0}`. Databento's
 * `side` is the side that *initiated* the trade, so:
 *
 *   `'B'` — a **buy**er aggressed, lifting the offer → the print is at the
 *           **ask** → `askVol`, and it adds to delta.
 *   `'A'` — a **sell**er aggressed, hitting the bid → the print is at the
 *           **bid** → `bidVol`, and it subtracts.
 *
 * So `'A'` lands in `bidVol`, which reads backwards and is exactly the trap
 * `DELTA_CVD_FINDINGS.md` records: taking `A`/"Ask" to mean "printed at the
 * ask" inverts the sign and produces a mirror-image CVD that looks perfectly
 * plausible.
 *
 * `'N'` is neither. It carries real volume that no aggressor was disseminated
 * for, and folding it into a side is how a footprint acquires a directional
 * bias that is not in the market.
 */
const ASK_INITIATED = "B";
const BID_INITIATED = "A";

/** Ticks are barred at one minute, matching `s1.py`'s `minute_bars`. */
const BAR_MS = 60_000;

/**
 * Empty minutes are dropped, exactly as `minute_bars` drops them. That means
 * bar N+5 is **not** five minutes after bar N — the same trap `backtest.py`
 * solves for horizons — and it also means the replay contains real quiet gaps,
 * which is the honest way for `stale` to be reachable without faking it.
 */
export interface MockOptions {
  /** Wall-clock speed-up. `contracts.md` S2 says 10x. */
  speed?: number;
  /** Vendor string reported in `FeedStatus`. */
  vendor?: string;
  /**
   * How long without a bar before the feed calls itself `stale`, in wall-clock
   * ms. Must exceed one bar interval at the chosen speed (6s at 10x) or the
   * feed flags itself stale between ordinary bars.
   */
  staleAfterMs?: number;
  /** Overrides the fetch location; injected by tests. */
  fixtureUrl?: string;
}

/**
 * The fake's control surface — **not part of S2.**
 *
 * These four exist because W1D2's number is "four failure modes triggerable
 * from the UI". `engine/real.ts` will implement `Engine` and none of this, so
 * nothing in the app may depend on a method from here outside a dev control.
 */
export interface MockEngine extends Engine {
  /** Connected, but the ticks stop. The state that looks like a quiet market. */
  goStale(): void;
  /** The connection drops outright. */
  drop(): void;
  /** Resume normal replay from wherever it stopped. */
  resume(): void;
  /** Emit one bar carrying a 7-digit CVD. */
  emitWideCvd(): void;
  /**
   * Report a 40-character vendor string.
   *
   * S2 puts `symbol` in `CaptureContext`, which flows UI → engine, so a feed
   * cannot "emit a symbol" under this contract at all — `vendor` is the only
   * free-text string that travels engine → UI. The long-string layout risk
   * W1D2 is aiming at is the same either way, so the control stresses `vendor`
   * here and the caller stresses `symbol` through `setContext`.
   */
  emitLongVendor(): void;
  /** Whole-session totals, for the reconciliation assertion. */
  totals(): { ticks: number; delta: number; volume: number };
}

/** A bar under construction. */
interface Accum {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  volume: number;
  bidVol: number;
  askVol: number;
}

/**
 * Bars a tick array into `DeltaBar`s.
 *
 * Exported because it is the piece worth checking independently: feed it the
 * fixture and the totals must reproduce `s1.py`'s.
 */
export function barTicks(ticks: readonly FixtureTick[]): DeltaBar[] {
  const bars: DeltaBar[] = [];
  let acc: Accum | null = null;
  let cvd = 0;

  const flush = () => {
    if (!acc) return;

    // `delta` is defined by S2 as askVol - bidVol. Unsigned ('N') volume is in
    // `volume` and in neither leg, so it moves volume without moving delta —
    // which is the correct behaviour and not a rounding artefact.
    const delta = acc.askVol - acc.bidVol;
    cvd += delta;

    bars.push({
      t: acc.t,
      o: acc.o,
      h: acc.h,
      l: acc.l,
      c: acc.c,
      volume: acc.volume,
      delta,
      cvd,
      bidVol: acc.bidVol,
      askVol: acc.askVol,
    });

    acc = null;
  };

  for (const tick of ticks) {
    const bucket = Math.floor(tick.t / BAR_MS) * BAR_MS;

    if (acc && acc.t !== bucket) flush();

    if (!acc) {
      acc = {
        t: bucket,
        o: tick.price,
        h: tick.price,
        l: tick.price,
        c: tick.price,
        volume: 0,
        bidVol: 0,
        askVol: 0,
      };
    }

    acc.h = Math.max(acc.h, tick.price);
    acc.l = Math.min(acc.l, tick.price);
    acc.c = tick.price;

    // Every trade counts toward volume, including the unsigned ones. Dropping
    // them here would make volume stop reconciling with the fixture.
    acc.volume += tick.size;

    if (tick.side === ASK_INITIATED) acc.askVol += tick.size;
    else if (tick.side === BID_INITIATED) acc.bidVol += tick.size;
  }

  flush();
  return bars;
}

/**
 * The unsigned share of a bar, in contracts.
 *
 * `contracts.md`'s pending `'N'` amendment requires that any consumer reporting
 * delta reports the `'N'` share beside it. **S2 can already express this
 * without a contract change** — `volume` counts every trade while `bidVol` and
 * `askVol` count only attributed ones, so what is left over is precisely the
 * unsigned volume. Nothing needs adding to `DeltaBar`.
 */
export function unsignedVolume(bar: DeltaBar): number {
  return bar.volume - bar.bidVol - bar.askVol;
}

/**
 * Plausible outliers for laying out a UI. **Not a signal, not a strategy, and
 * not evidence.**
 *
 * The thresholds are round numbers chosen to make roughly a handful fire per
 * session so the list has something in it. `strategies.py`'s `absorption_fade`
 * already learned the lesson encoded in `MIN_SIZE`: a purely scale-free ratio
 * selects for illiquidity, firing on 5-lot prints in the overnight dead zone.
 */
const MIN_SIZE = 60;

function detectOutlier(bar: DeltaBar, prev: DeltaBar | undefined): Outlier | null {
  const rangeTicks = Math.round((bar.h - bar.l) * 10);
  const side: Side = bar.delta >= 0 ? "ask" : "bid";
  const magnitude = Math.abs(bar.delta);

  if (bar.volume < MIN_SIZE) return null;

  let kind: Outlier["kind"] | null = null;

  // Heavy one-sided flow that failed to move price.
  if (magnitude >= 120 && rangeTicks <= 6) kind = "absorption";
  // Aggression one way, close the other way.
  else if (prev && magnitude >= 100 && Math.sign(bar.c - bar.o) === -Math.sign(bar.delta))
    kind = "trapped";
  // A lot of volume in a tight band.
  else if (bar.volume >= 400 && rangeTicks <= 10) kind = "cluster";

  if (!kind) return null;

  return {
    id: `mock-${bar.t}-${kind}`,
    t: bar.t,
    price: bar.c,
    size: magnitude,
    side,
    kind,
    clusterLow: bar.l,
    clusterHigh: bar.h,
    // Deliberately coarse. A score with more precision than the rule behind it
    // would invite someone to read meaning into the digits.
    score: Math.min(100, Math.round((magnitude / 4 + bar.volume / 20))),
  };
}

export function createMockEngine(options: MockOptions = {}): MockEngine {
  const speed = options.speed ?? 10;
  const vendor = options.vendor ?? "mock:gc_ticks_1session";
  const staleAfterMs = options.staleAfterMs ?? 18_000;
  const fixtureUrl = options.fixtureUrl ?? "/fixtures/gc_ticks_1session.json";

  const barSubs = new Set<(b: DeltaBar) => void>();
  const outlierSubs = new Set<(o: Outlier) => void>();
  const statusSubs = new Set<(s: FeedStatus) => void>();

  let bars: DeltaBar[] = [];
  let totals = { ticks: 0, delta: 0, volume: 0 };
  let cursor = 0;
  let timer: number | undefined;
  let staleTimer: number | undefined;

  /**
   * Guards against more than one replay scheduler running at a time.
   *
   * **Found the hard way on W1D2**: `connect()` clears timers *before* it
   * awaits the fixture, so two overlapping connects both get past the clear
   * before either schedules, and each then starts its own chain. Only the
   * newest timer id is held, so the older chain is orphaned — un-cancellable,
   * still emitting, and `emit()` flips the state back to `live` on its next
   * bar. That made every failure mode look like it silently did nothing.
   *
   * React's StrictMode double-mount triggers it on every dev start, so the
   * cheapest possible reproduction was already running. Anything that stops
   * the feed bumps the generation; a scheduler whose generation is stale exits
   * instead of rescheduling.
   */
  let generation = 0;

  /** Shared so two overlapping connects fetch 4.8MB once, not twice. */
  let loading: Promise<void> | null = null;

  let status: FeedStatus = {
    state: "disconnected",
    vendor: null,
    lastTickAt: null,
    gapCount: 0,
  };

  const setStatus = (next: Partial<FeedStatus>) => {
    status = { ...status, ...next };
    for (const cb of statusSubs) cb(status);
  };

  const clearTimers = () => {
    generation += 1;
    window.clearTimeout(timer);
    window.clearTimeout(staleTimer);
    timer = undefined;
    staleTimer = undefined;
  };

  /** Connected but not receiving — the state S2 calls out as easy to get wrong. */
  const armStale = () => {
    window.clearTimeout(staleTimer);
    staleTimer = window.setTimeout(() => {
      if (status.state === "live") setStatus({ state: "stale" });
    }, staleAfterMs);
  };

  const emit = (bar: DeltaBar) => {
    for (const cb of barSubs) cb(bar);

    const outlier = detectOutlier(bar, bars[cursor - 2]);
    if (outlier) for (const cb of outlierSubs) cb(outlier);

    if (status.state !== "live") setStatus({ state: "live" });
    setStatus({ lastTickAt: bar.t });
    armStale();
  };

  /**
   * Schedules the next bar at its own fixture spacing, divided by `speed`.
   * A quiet stretch in the session therefore stays quiet in the replay rather
   * than being evened out — which is what lets `stale` be reached honestly.
   */
  const schedule = (gen: number) => {
    if (gen !== generation) return;

    if (cursor >= bars.length) {
      setStatus({ state: "stale" });
      return;
    }

    const bar = bars[cursor];
    const prev = bars[cursor - 1];
    const gapMs = prev ? bar.t - prev.t : BAR_MS;

    // A dropped empty minute shows up here as a gap wider than one bar.
    if (prev && gapMs > BAR_MS) setStatus({ gapCount: status.gapCount + 1 });

    timer = window.setTimeout(() => {
      if (gen !== generation) return;
      cursor += 1;
      emit(bar);
      schedule(gen);
    }, Math.max(16, gapMs / speed));
  };

  const load = (): Promise<void> => (loading ??= loadOnce());

  const loadOnce = async (): Promise<void> => {
    if (bars.length) return;

    const res = await fetch(fixtureUrl);
    if (!res.ok) throw new Error(`fixture ${fixtureUrl}: HTTP ${res.status}`);

    const fixture = (await res.json()) as Fixture;
    bars = barTicks(fixture.ticks);

    totals = {
      ticks: fixture.ticks.length,
      delta: bars.reduce((sum, b) => sum + b.delta, 0),
      volume: bars.reduce((sum, b) => sum + b.volume, 0),
    };

    // Loud, not silent. If the fixture or the mapping ever drifts, every number
    // this fake produces is wrong in a way that still looks plausible, and the
    // UI built on it would be validated against nothing.
    if (
      totals.ticks !== RECONCILIATION.ticks ||
      totals.delta !== RECONCILIATION.sessionDelta ||
      totals.volume !== RECONCILIATION.volume
    ) {
      console.error(
        "[mock] fixture does not reconcile with s1.py:",
        JSON.stringify({ got: totals, want: RECONCILIATION }),
      );
    }
  };

  return {
    async connect(_creds: FeedCreds): Promise<FeedStatus> {
      // A second connect must not leave the first one's scheduler running:
      // two timers advancing one cursor replays the session at double speed
      // and skips every other bar. StrictMode's double-mount hits this on
      // every dev start, which is the cheapest possible way to have found it.
      clearTimers();
      setStatus({ state: "connecting", vendor, gapCount: 0 });

      await load();

      // Taken *after* the await, so an overlapping connect that resolved first
      // is superseded here rather than left running alongside this one.
      const gen = (generation += 1);

      cursor = 0;
      setStatus({ state: "live", lastTickAt: null });
      schedule(gen);

      return status;
    },

    async status(): Promise<FeedStatus> {
      return status;
    },

    /**
     * Accepted and ignored, the same way creds are ignored: this fake replays
     * one committed session whatever chart the trader has open. It exists so
     * consumers can exercise the call — the real engine will narrow its
     * outlier search to the context's levels.
     */
    async setContext(_ctx: CaptureContext): Promise<void> {},

    onBar(cb) {
      barSubs.add(cb);
      return (() => barSubs.delete(cb)) as Unsubscribe;
    },

    onOutlier(cb) {
      outlierSubs.add(cb);
      return (() => outlierSubs.delete(cb)) as Unsubscribe;
    },

    /**
     * Replays the current status to the new subscriber immediately.
     *
     * **Found by W1D2's own screenshot, and it is not a mock-only bug.** Without
     * this, a component that mounts *after* the feed has settled shows whatever
     * its local default is — "Disconnected" over a feed that is live — because
     * `emit` only pushes a state change when the state actually changes, and a
     * steady `live` feed never changes it. React's StrictMode double-mount makes
     * it reproducible on every start in dev; in production it is any view opened
     * after connection. `real.ts` must do the same thing.
     */
    onStatus(cb) {
      statusSubs.add(cb);
      cb(status);
      return (() => statusSubs.delete(cb)) as Unsubscribe;
    },

    /* ---- failure modes, mock only ------------------------------------- */

    goStale() {
      clearTimers();
      setStatus({ state: "stale" });
    },

    drop() {
      clearTimers();
      setStatus({ state: "disconnected", vendor: null });
    },

    resume() {
      clearTimers();
      if (!bars.length) return;
      setStatus({ state: "live", vendor });
      schedule(generation);
    },

    emitWideCvd() {
      const last = bars[Math.max(0, cursor - 1)];
      if (!last) return;

      // 7 digits, which is what a UI that sized its CVD field for four will
      // fail on. Not reachable from the fixture — GC's session CVD is O(1e3).
      emit({ ...last, t: last.t + BAR_MS, cvd: 1_234_567, delta: 98_765 });
    },

    emitLongVendor() {
      setStatus({ vendor: "GC-CONTINUOUS-FRONT-MONTH-ADJUSTED-XX".padEnd(40, "X").slice(0, 40) });
    },

    totals() {
      return totals;
    },
  };
}
