import type { AnalyzeRequest, AnalyzeResult } from "./types";

export const API_BASE = "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function analyze(
  payload: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResult> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch {
    throw new ApiError(
      "Could not reach the analysis service on 127.0.0.1:8000",
    );
  }

  if (!response.ok) {
    throw new ApiError(
      `The analysis service returned ${response.status}`,
      response.status,
    );
  }

  return (await response.json()) as AnalyzeResult;
}

/**
 * Stand-in used when the API is unreachable — keeps the UI explorable on a
 * plain dev server. Deterministic on the input so repeat runs look stable.
 */
export function offlineAnalysis(input: string): AnalyzeResult {
  const bullish = /\b(beat|beats|surge|rally|strong|growth|upgrade|record|gain)\w*/gi;
  const bearish = /\b(miss|misses|fall|drop|weak|cut|downgrade|loss|decline)\w*/gi;

  const up = (input.match(bullish) ?? []).length;
  const down = (input.match(bearish) ?? []).length;

  const sentiment = up === down ? "Neutral" : up > down ? "Bullish" : "Bearish";
  const spread = Math.abs(up - down);
  const confidence = Math.min(52 + spread * 11, 94);

  return {
    sentiment,
    confidence,
    summary:
      sentiment === "Neutral"
        ? "No decisive directional language in the captured context. Treat this as background, not a signal."
        : `Language in the capture leans ${sentiment.toLowerCase()}. Confirm against price and volume before acting on it.`,
    signals: [
      `${up} bullish and ${down} bearish phrases detected`,
      sentiment === "Neutral"
        ? "No clear catalyst identified"
        : "Directional catalyst present in the capture",
      "Offline heuristic — start the API for the model result",
    ],
  };
}
