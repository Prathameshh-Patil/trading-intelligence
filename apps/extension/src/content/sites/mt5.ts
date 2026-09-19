/**
 * MT5 Web Terminal, MetaQuotes-hosted (`trade.mql5.com`, `web.metatrader.app`).
 * Title-based: `SYMBOL, TIMEFRAME: ...` is the pattern the terminal sets for
 * the active chart. Broker-hosted terminals are a follow-up (optional host
 * permissions). Verified 2026-09-19 against the MetaQuotes demo.
 */

import type { SiteAdapter } from "./index";

export const mt5: SiteAdapter = {
  name: "MT5 Web",
  matches: (host) => host === "trade.mql5.com" || host === "web.metatrader.app",
  readChart(doc) {
    const m = doc.title.match(/^([A-Z0-9!._:/-]{2,20})\s*,\s*([A-Za-z0-9]+)/);
    if (!m) return null;
    return { symbol: m[1]!, timeframe: m[2] ?? null, lastPrice: null };
  },
};
