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
import type { Engine } from "./types";

export type { MockEngine } from "./mock";

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
