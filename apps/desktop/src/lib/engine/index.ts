/**
 * S2 · engine selection — `VITE_ENGINE=mock|real`, default `mock`.
 *
 * `contracts.md` S2 specifies this switch so that every consumer imports one
 * thing and never learns which implementation it got. `engine/real.ts` is
 * Varad's, W3D1; until it exists, asking for `real` is a startup error rather
 * than a silent fall back to the fake — a UI quietly running on replayed July
 * ticks while someone believes they are watching a live feed is the worst
 * failure this seam can produce.
 */

import { createMockEngine, type MockEngine } from "./mock";
import { createMockForecaster, type MockForecaster } from "./forecastMock";
import type { Forecaster } from "./forecast";
import type { Engine } from "./types";

export type { MockEngine } from "./mock";
export type { MockForecaster } from "./forecastMock";

const CHOICE = import.meta.env.VITE_ENGINE ?? "mock";

let instance: Engine | null = null;

export function getEngine(): Engine {
  if (instance) return instance;

  if (CHOICE === "real") {
    throw new Error(
      "VITE_ENGINE=real, but engine/real.ts does not exist yet (Varad, W3D1). " +
        "Refusing to fall back to the mock: replayed 2026-07-16 ticks must never " +
        "be mistaken for a live feed.",
    );
  }

  if (CHOICE !== "mock") {
    throw new Error(`VITE_ENGINE must be "mock" or "real", got "${CHOICE}"`);
  }

  instance = createMockEngine();
  return instance;
}

/**
 * The mock's control surface, or `null` when the real engine is in use.
 *
 * Every dev-only failure-mode control goes through this, so that the moment
 * `real.ts` lands those controls disappear on their own instead of throwing.
 */
export function getMockControls(): MockEngine | null {
  const engine = getEngine();
  return "goStale" in engine ? (engine as MockEngine) : null;
}

let forecaster: Forecaster | null = null;

/**
 * S7 · the reach table, behind the same switch as S2.
 *
 * The real one is `services/signal-data/reach.py`'s output — a ~1.7-hour build
 * over 19 months, gitignored, and not on this machine. `VITE_ENGINE=real`
 * refuses rather than falling back for the same reason S2 does: a UI quoting
 * probabilities that were never counted is worse than a UI that will not start.
 */
export function getForecaster(): Forecaster {
  if (forecaster) return forecaster;

  if (CHOICE === "real") {
    throw new Error(
      "VITE_ENGINE=real, but no real forecaster exists yet — reach_table.csv is " +
        "built offline and nothing serves it. Refusing to fall back to the fake: " +
        "invented probabilities must never be mistaken for the archive's.",
    );
  }

  forecaster = createMockForecaster();
  return forecaster;
}

/** The fake forecaster's controls, or `null` once a real one exists. */
export function getMockForecasterControls(): MockForecaster | null {
  const f = getForecaster();
  return "coverage" in f ? (f as MockForecaster) : null;
}
