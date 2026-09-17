/**
 * S6 · Chart-context extraction — the one thing capture is allowed to produce.
 *
 * W3D2's instruction, from `plans/team/prathamesh/README.md`: *"Wire the
 * Analyze view to the local engine instead of the stub API. Delete the
 * `http://localhost:8000` call from the desktop signal path entirely — no
 * signal number crosses a network any more. The one remaining API call from
 * desktop is chart-context extraction, and it sends a screenshot, never a
 * tick."*
 *
 * This file is that one call, and its fake. `lib/api.ts` — which POSTed the
 * capture to `/analyze` and rendered whatever sentiment and confidence came
 * back as a prediction — is deleted, not wrapped. A "Bullish 78%" derived from
 * headline text was a stub from the browser-extension days; on a desk it is
 * exactly the confident wrong number `contracts.md` S6 exists to make
 * impossible.
 *
 * ## What comes back, and what may never come back
 *
 * `CaptureContext`: a symbol, a timeframe, the levels the trader has drawn, and
 * how sure the extraction is. **No delta, no CVD, no volume, no outlier** —
 * S6's type has no numeric field other than `levels` and `confidence`, and
 * that is the enforcement. Everything that looks like a signal in the Analyze
 * view comes from `Engine`, after `setContext(ctx)` has told it what chart the
 * trader is on.
 *
 * ## The switch
 *
 * `VITE_CONTEXT=mock|real`, default `mock`, same shape as `engine/index.ts`.
 * `services/api` has no extraction route today (`/analyze`, `/forecast/table`,
 * `/health` — that is all of it), so `real` throws rather than falling back:
 * a view quietly reading a mocked "GC" while the trader sits on a chart we
 * have no feed for is the same failure as replayed July ticks read as live.
 *
 * ## The fake misbehaves on demand
 *
 * W3D4 names the ugly cases: *"symbol not recognised, MT5 minimised, trader on
 * a chart we have no feed for. Each needs a visible, honest state — never a
 * wrong number, and never a confident one."* The mock can produce each of
 * them, and the Analyze view's dev-only controls drive it, in the same way
 * `FlowView` drives `engine/mock.ts`.
 */

import type { CaptureContext } from "./engine/types";
import type { Capture } from "./types";

export interface ContextExtractor {
  /** Screenshot in, context out. The only network call the desktop signal path may make. */
  extract(capture: Capture): Promise<CaptureContext>;
}

/**
 * What the mock will say the trader is looking at, next time it is asked.
 *
 *   gc          the launch instrument, confidently — the good path
 *   unknown     a chart we have no feed for (the capture shim's NVDA page, honestly read)
 *   uncertain   GC, but the extractor is not sure it is — below `CONFIDENT`
 *   failed      nothing usable in the capture — the MT5-minimised case
 */
export type MockScenario = "gc" | "unknown" | "uncertain" | "failed";

export interface MockContextExtractor extends ContextExtractor {
  scenario: MockScenario;
  setScenario(next: MockScenario): void;
}

/**
 * Below this, the Analyze view treats the symbol as unconfirmed and shows no
 * engine numbers against it. Chosen for the fake; the real threshold is the
 * extraction route's to publish, and this constant moves when it does.
 */
export const CONFIDENT = 70;

/**
 * Instruments this build has a feed for. `GC` because it is the launch
 * instrument and the only thing `engine/mock.ts` replays; the second entry
 * arrives with the spot lane (`plans/current.md` R7) and not before.
 *
 * A `Set`, not a check against `FeedStatus.vendor`: S2 does not say what a
 * vendor string means, and "does the engine have this symbol" is a question
 * the engine will answer directly once `real.ts` exists.
 */
export const FEED_SYMBOLS: ReadonlySet<string> = new Set(["GC"]);

export class ContextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContextError";
  }
}

export function createMockExtractor(initial: MockScenario = "gc"): MockContextExtractor {
  let scenario = initial;

  return {
    get scenario() {
      return scenario;
    },
    setScenario(next) {
      scenario = next;
    },

    async extract(capture) {
      // A real extraction takes a moment; a fake that returns instantly hides
      // the loading state the view has to render.
      await new Promise((r) => setTimeout(r, 450));

      const capturedAt = capture.capturedAt ?? Date.now();

      switch (scenario) {
        case "gc":
          return {
            symbol: "GC",
            timeframe: "1m",
            // Plausible-looking levels for layout only. Invented, like the
            // mock's outliers; nothing here is a measurement.
            levels: [3384.5, 3371.2],
            confidence: 91,
            capturedAt,
          };
        case "unknown":
          // The capture shim's page really is an NVDA headline over a
          // synthetic chart. Reading it as "NVDA" is the honest answer.
          return { symbol: "NVDA", timeframe: "5m", levels: [], confidence: 88, capturedAt };
        case "uncertain":
          return { symbol: "GC", timeframe: "1m", levels: [], confidence: 41, capturedAt };
        case "failed":
          throw new ContextError(
            "Nothing readable in the capture — is the chart window visible and unobstructed?",
          );
      }
    },
  };
}

const CHOICE = import.meta.env.VITE_CONTEXT ?? "mock";

let instance: ContextExtractor | null = null;

export function getExtractor(): ContextExtractor {
  if (instance) return instance;

  if (CHOICE === "real") {
    throw new Error(
      "VITE_CONTEXT=real, but services/api has no extraction route yet. " +
        "Refusing to fall back to the mock: a fabricated symbol must never be " +
        "mistaken for the chart the trader is actually on.",
    );
  }

  if (CHOICE !== "mock") {
    throw new Error(`VITE_CONTEXT must be "mock" or "real", got "${CHOICE}"`);
  }

  instance = createMockExtractor();
  return instance;
}

/** The mock's control surface, or `null` once the real extractor is in use. */
export function getMockExtractorControls(): MockContextExtractor | null {
  const x = getExtractor();
  return "setScenario" in x ? (x as MockContextExtractor) : null;
}
