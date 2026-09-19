/**
 * What the extension keeps, and where.
 *
 * Everything lives in `chrome.storage.local`, which is per-profile, survives
 * the service worker being killed (it is, constantly), and is readable from
 * the popup, the content scripts and the worker alike -- so it is also the
 * bus: a write here reaches every open panel through `onChanged` with no
 * second message protocol.
 *
 * THE KEY IS HERE TOO. There is no OS keychain reachable from an extension;
 * `storage.local` is what a browser extension has, and it is scoped to this
 * extension's id -- a page script cannot read it. That is the same standing
 * as the desktop's in-memory dev mode, and the trader is told so in the popup.
 *
 * Nothing the content script reads off the chart is stored here or sent
 * anywhere. `ChartRead` lives in the panel's React state and dies with the tab.
 */

import type { Alert, AlertTier } from "@vision-hub/contracts";
import type { LicenceState } from "@vision-hub/core";

import { ext } from "./browser";

export type TierDisplay = "banner" | "badge" | "list" | "silent";
export type TierSettings = Record<AlertTier, TierDisplay>;
export type SocketStatus = "off" | "connecting" | "live" | "offline";

export interface PanelPos {
  x: number;
  y: number;
  collapsed: boolean;
}

export interface Stored {
  licenceKey: string | null;
  lastValidAt: number | null;
  /** The worker's view of the licence, mirrored here for popup and panels. */
  licence: LicenceState;
  /** A runtime override of the build's `VITE_API_BASE`. Null = the build's. */
  apiBase: string | null;
  tierSettings: TierSettings;
  /** Newest last, at most `MAX_ALERTS`. */
  alerts: Alert[];
  /** The highest alert id seen, for the reconnect catch-up. */
  lastAlertId: number;
  unreadSignals: number;
  /** Per site host, where the trader left the panel. */
  panel: Record<string, PanelPos>;
  socketStatus: SocketStatus;
  socketError: string | null;
}

export const DEFAULT_TIERS: TierSettings = {
  breaking: "banner",
  signal: "badge",
  analysis: "list",
};

export const DEFAULTS: Stored = {
  licenceKey: null,
  lastValidAt: null,
  licence: { kind: "unactivated" },
  apiBase: null,
  tierSettings: DEFAULT_TIERS,
  alerts: [],
  lastAlertId: 0,
  unreadSignals: 0,
  panel: {},
  socketStatus: "off",
  socketError: null,
};

export const MAX_ALERTS = 50;

export async function read(): Promise<Stored> {
  const got = (await ext.storage.local.get(DEFAULTS)) as Partial<Stored>;
  return { ...DEFAULTS, ...got, tierSettings: { ...DEFAULT_TIERS, ...(got.tierSettings ?? {}) } };
}

export async function write(patch: Partial<Stored>): Promise<void> {
  await ext.storage.local.set(patch);
}

/** Re-read the whole record whenever any of it changes. */
export function watch(cb: (s: Stored) => void): () => void {
  const listener = (_: unknown, area: string) => {
    if (area === "local") void read().then(cb);
  };
  ext.storage.onChanged.addListener(listener);
  return () => ext.storage.onChanged.removeListener(listener);
}

/**
 * Where the API is for this build: the override when the trader set one, the
 * build's `VITE_API_BASE` otherwise, null when neither -- in which case the
 * popup says the build cannot activate, exactly as the desktop does.
 */
export function apiBaseOf(s: Pick<Stored, "apiBase">): string | null {
  const v = s.apiBase || (import.meta.env.VITE_API_BASE as string | undefined) || null;
  return v ? v.trim().replace(/\/+$/, "") || null : null;
}

export const BUILT_API_BASE: string | null =
  ((import.meta.env.VITE_API_BASE as string | undefined) || null)?.replace(/\/+$/, "") ?? null;
export const SITE_URL: string | null =
  ((import.meta.env.VITE_SITE_URL as string | undefined) || null)?.replace(/\/+$/, "") ?? null;
