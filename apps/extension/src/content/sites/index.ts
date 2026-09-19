/**
 * Reading the chart the trader is looking at -- on their say-so, and no further.
 *
 * Three rules, and the code is shaped so breaking them takes effort:
 *
 *   1. USER-INITIATED. Nothing here runs until *Sync chart* is pressed. No
 *      observer, no interval, no read on load.
 *   2. READ-ONLY. `readChart` touches `document.title` and a handful of
 *      `querySelector`s. It dispatches no events, sets no values, calls
 *      nothing on the page's own objects.
 *   3. IT STAYS IN THE PAGE. `ChartRead` is returned to the panel's React
 *      state and rendered. There is no `messages.ts` request that carries
 *      it, the socket has no frame for it, and storage has no field for it.
 *      The backend never learns which symbol a trader has open.
 *
 * Every adapter is best-effort against a page it does not own. Selectors
 * rot; a `null` is the normal failure and the panel offers a text box.
 */

import { ctrader } from "./ctrader";
import { mt5 } from "./mt5";
import { tradingview } from "./tradingview";

export interface ChartRead {
  symbol: string;
  timeframe: string | null;
  lastPrice: string | null;
}

export interface SiteAdapter {
  /** Human name, for the panel. */
  name: string;
  matches(host: string): boolean;
  /** Synchronous, no side effects; `null` when the page did not yield. */
  readChart(doc: Document): ChartRead | null;
}

const ADAPTERS: SiteAdapter[] = [tradingview, ctrader, mt5];

export function adapterFor(host: string): SiteAdapter | null {
  return ADAPTERS.find((a) => a.matches(host)) ?? null;
}

/** Wraps an adapter so a selector that throws reads as "did not yield". */
export function readChart(host: string, doc: Document): ChartRead | null {
  const a = adapterFor(host);
  if (!a) return null;
  try {
    const r = a.readChart(doc);
    return r && r.symbol ? r : null;
  } catch {
    return null;
  }
}

/** `XAUUSD 2,650.5 ▲ +0.31% ...` -> symbol and price, from a tab title. */
export function parseTitle(title: string): { symbol: string; price: string | null } | null {
  const m = title.trim().match(/^([A-Z0-9!._:/-]{2,20})\s+([\d,]+(?:\.\d+)?)/);
  if (m) return { symbol: m[1]!, price: m[2]! };
  const s = title.trim().match(/^([A-Z0-9!._:/-]{2,20})\b/);
  return s ? { symbol: s[1]!, price: null } : null;
}
