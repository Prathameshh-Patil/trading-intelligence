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
 * **The table is no longer the missing half** — `services/api`'s
 * `GET /api/v1/forecast/table` serves it, and `VITE_FORECAST_API` points the
 * forecaster at it. What is still missing is the other half of `reach.py`:
 * `cell_of` needs `atr_bp` and `rv_slope`, so forming the key needs a live feed
 * and `plans/current.md` C1 reopened on 5 Sep. Until then the key is derived
 * from the timestamp, which is a fake, so this stays behind the mock switch.
 *
 * `VITE_ENGINE=real` refuses rather than falling back for the same reason S2
 * does: a UI quoting real probabilities under an invented bucket is worse than
 * a UI that will not start.
 */
export function getForecaster(): Forecaster {
  if (forecaster) return forecaster;

  if (CHOICE === "real") {
    throw new Error(
      "VITE_ENGINE=real, but no real forecaster exists yet — services/api serves " +
        "the table, and nothing forms the key from a live feed. Refusing to fall " +
        "back to the fake: an invented bucket must never be mistaken for the " +
        "archive's own.",
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
