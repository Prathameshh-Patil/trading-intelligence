/**
 * What the popup and the panels may ask the service worker to do.
 *
 * The worker is the only place the key is read and the only place the socket
 * lives; everything else sends one of these and reads the result back out of
 * `storage.onChanged`. Requests carry no chart data -- there is no message
 * that could, and that is the point (`content/sites/index.ts`).
 */

import type { LicenceState } from "@vision-hub/core";

import { ext } from "./browser";
import type { PanelPos, TierSettings } from "./storage";

export type Request =
  | { type: "licence.get" }
  | { type: "licence.activate"; key: string }
  | { type: "licence.recheck" }
  | { type: "licence.deactivate" }
  | { type: "config.apiBase"; apiBase: string | null }
  | { type: "alerts.tiers"; tiers: TierSettings }
  | { type: "alerts.markRead" }
  | { type: "panel.save"; host: string; pos: PanelPos };

export type Response = { licence: LicenceState };

export function send(req: Request): Promise<Response> {
  return ext.runtime.sendMessage(req) as Promise<Response>;
}
