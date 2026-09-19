/**
 * TradingView. The tab title is `SYMBOL PRICE ▲ +x.xx% Unnamed` on a chart
 * page and is the most stable thing on it; the legend and the interval
 * button are the fallbacks and the timeframe. Selectors last checked
 * 2026-09-19 -- they are TradingView's, and they change.
 */

import { parseTitle, type SiteAdapter } from "./index";

export const tradingview: SiteAdapter = {
  name: "TradingView",
  matches: (host) => host === "tradingview.com" || host.endsWith(".tradingview.com"),
  readChart(doc) {
    const fromTitle = parseTitle(doc.title);
    const legend = doc.querySelector<HTMLElement>('[data-name="legend-source-title"]');
    const symbol = fromTitle?.symbol ?? legend?.textContent?.trim().split(/\s/)[0] ?? "";
    if (!symbol) return null;

    const interval =
      doc.querySelector<HTMLElement>('#header-toolbar-intervals [aria-checked="true"]') ??
      doc.querySelector<HTMLElement>('#header-toolbar-intervals button');
    const timeframe = interval?.textContent?.trim() || null;

    return { symbol, timeframe, lastPrice: fromTitle?.price ?? null };
  },
};
