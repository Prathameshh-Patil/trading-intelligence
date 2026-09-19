/**
 * cTrader Web. Title-based only: the app is a canvas-heavy SPA whose DOM is
 * not stable enough to promise a selector for. Verified against the public
 * demo 2026-09-19; the title reads `SYMBOL - cTrader` or `SYMBOL PRICE ...`.
 */

import { parseTitle, type SiteAdapter } from "./index";

export const ctrader: SiteAdapter = {
  name: "cTrader",
  matches: (host) => host === "ctrader.com" || host.endsWith(".ctrader.com"),
  readChart(doc) {
    const t = doc.title.replace(/\s*[-|–]\s*cTrader.*$/i, "");
    const r = parseTitle(t);
    return r ? { symbol: r.symbol, timeframe: null, lastPrice: r.price } : null;
  },
};
