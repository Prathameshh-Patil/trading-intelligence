/**
 * The service worker: the licence, the socket, and the one message handler.
 *
 * Nothing here renders. It holds the two things that must exist exactly once
 * -- the licence store and the socket -- and mirrors their state into
 * `chrome.storage.local`, which popup and panels watch. It is stopped by the
 * browser whenever idle and restarted on a message, an alarm or a socket
 * frame; everything it needs to resume is in storage, and `start()` is
 * idempotent.
 */

import { ext } from "../browser";
import type { Request, Response } from "../messages";
import { DEFAULT_TIERS, read, write } from "../storage";
import { publishState, refreshApiBase, store } from "./licence";
import { badge, reconcile, restart } from "./socket";

async function start(): Promise<void> {
  await refreshApiBase();
  publishState((licence) => {
    void write({ licence });
    reconcile(licence, () => void store.recheck());
  });
  await badge((await read()).unreadSignals);
}

ext.runtime.onInstalled.addListener(() => void start());
ext.runtime.onStartup.addListener(() => void start());
void start();

ext.runtime.onMessage.addListener((raw: unknown, _sender, reply: (r: Response) => void) => {
  void handle(raw as Request).then(reply);
  return true; // async reply
});

async function handle(req: Request): Promise<Response> {
  switch (req.type) {
    case "licence.get":
      break;
    case "licence.activate":
      await store.activate(req.key);
      break;
    case "licence.recheck":
      await store.recheck();
      break;
    case "licence.deactivate":
      await store.deactivate();
      await write({ alerts: [], lastAlertId: 0, unreadSignals: 0 });
      await badge(0);
      break;
    case "config.apiBase":
      await write({ apiBase: req.apiBase?.trim().replace(/\/+$/, "") || null });
      await refreshApiBase();
      restart();
      await store.recheck();
      break;
    case "alerts.tiers":
      await write({ tierSettings: { ...DEFAULT_TIERS, ...req.tiers } });
      if (req.tiers.signal !== "badge") {
        await write({ unreadSignals: 0 });
        await badge(0);
      }
      break;
    case "alerts.markRead":
      await write({ unreadSignals: 0 });
      await badge(0);
      break;
    case "panel.save": {
      const { panel } = await read();
      await write({ panel: { ...panel, [req.host]: req.pos } });
      break;
    }
  }
  return { licence: store.getState() };
}
