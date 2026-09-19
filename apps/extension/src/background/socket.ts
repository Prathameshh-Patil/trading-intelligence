/**
 * The socket, from the worker's side.
 *
 * Connect while the licence is `active` or `offline`; authenticate with the
 * key in the first frame (`packages/contracts/alerts.ts`); catch up on
 * anything missed with `GET /alerts?since=` before listening; ping every 25s.
 * The ping is not decoration: Chrome keeps a Manifest V3 service worker alive
 * while it holds an open WebSocket AND that socket sees activity inside every
 * thirty seconds, so the ping is what lets this connection outlive the
 * worker's idle limit. Reconnect on close with a backoff held in an alarm,
 * because a `setTimeout` in a stopped worker never fires.
 *
 * Alerts are appended to storage, which is the bus: every open panel sees
 * the change through `storage.onChanged`. The badge counts `signal`-tier
 * alerts the trader has not looked at yet, when their setting says badge.
 */

import { alertsSince, socketUrl, KeyRejected, type Alert, type SocketIn } from "@vision-hub/contracts";
import type { LicenceState } from "@vision-hub/core";

import { ext } from "../browser";
import { MAX_ALERTS, apiBaseOf, read, write, type SocketStatus } from "../storage";

const PING_MS = 25_000;
const RETRY_ALARM = "vh.socket.retry";
const BACKOFF_MS = [1_000, 2_000, 5_000, 10_000, 30_000];

let ws: WebSocket | null = null;
let pingTimer: number | undefined;
let attempt = 0;
let wanted = false;
let onKeyEvent: (() => void) | null = null;

async function setStatus(socketStatus: SocketStatus, socketError: string | null = null) {
  await write({ socketStatus, socketError });
}

/** Called with every licence state; opens or closes the socket to match. */
export function reconcile(licence: LicenceState, keyEvent: () => void): void {
  onKeyEvent = keyEvent;
  const shouldRun = licence.kind === "active" || licence.kind === "offline";
  if (shouldRun && !wanted) {
    wanted = true;
    attempt = 0;
    void connect();
  } else if (!shouldRun && wanted) {
    wanted = false;
    close();
    void setStatus("off");
  }
}

async function connect(): Promise<void> {
  if (!wanted || ws) return;
  const s = await read();
  const base = apiBaseOf(s);
  if (!s.licenceKey || !base) return;
  await setStatus("connecting");

  let socket: WebSocket;
  try {
    socket = new WebSocket(socketUrl(base));
  } catch (e) {
    await setStatus("offline", e instanceof Error ? e.message : String(e));
    scheduleRetry();
    return;
  }
  ws = socket;

  socket.onopen = () => {
    socket.send(JSON.stringify({ type: "auth", key: s.licenceKey }));
  };

  socket.onmessage = (ev) => {
    void handle(parse(ev.data), s.licenceKey!, base);
  };

  socket.onclose = (ev) => {
    if (ws !== socket) return;
    ws = null;
    clearInterval(pingTimer);
    // 4401: the server said the key is no longer good. Not a network
    // condition -- re-check the licence instead of retrying the socket.
    if (ev.code === 4401) {
      void setStatus("off", "key rejected");
      onKeyEvent?.();
      return;
    }
    void setStatus("offline", ev.reason || `closed ${ev.code}`);
    if (wanted) scheduleRetry();
  };

  socket.onerror = () => {
    // `onclose` follows and carries the code; nothing to do here.
  };
}

async function handle(frame: SocketIn | null, key: string, base: string): Promise<void> {
  if (!frame) return;
  switch (frame.type) {
    case "hello": {
      attempt = 0;
      await setStatus("live");
      clearInterval(pingTimer);
      pingTimer = setInterval(() => ws?.send(JSON.stringify({ type: "ping" })), PING_MS) as unknown as number;
      // Anything published while we were away, before the live stream.
      const { lastAlertId } = await read();
      try {
        const missed = await alertsSince(base, key, lastAlertId);
        if (missed.length) await append(missed);
      } catch (e) {
        if (e instanceof KeyRejected) onKeyEvent?.();
      }
      return;
    }
    case "alert":
      await append([frame.alert]);
      return;
    case "key":
      // The close that follows carries 4401 and is handled there.
      return;
    case "pong":
    case "error":
      return;
  }
}

async function append(incoming: Alert[]): Promise<void> {
  const s = await read();
  const known = new Set(s.alerts.map((a) => a.id));
  const fresh = incoming.filter((a) => !known.has(a.id)).sort((a, b) => a.id - b.id);
  if (!fresh.length) return;
  const alerts = [...s.alerts, ...fresh].slice(-MAX_ALERTS);
  const lastAlertId = Math.max(s.lastAlertId, ...fresh.map((a) => a.id));
  const newSignals = fresh.filter((a) => a.tier === "signal").length;
  const unreadSignals =
    s.tierSettings.signal === "badge" ? s.unreadSignals + newSignals : s.unreadSignals;
  await write({ alerts, lastAlertId, unreadSignals });
  await badge(unreadSignals);
}

export async function badge(n: number): Promise<void> {
  await ext.action.setBadgeText({ text: n > 0 ? String(Math.min(n, 99)) : "" });
  if (n > 0) await ext.action.setBadgeBackgroundColor({ color: "#8b5cf6" });
}

function scheduleRetry() {
  const ms = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
  attempt += 1;
  void ext.alarms.create(RETRY_ALARM, { when: Date.now() + ms });
}

ext.alarms.onAlarm.addListener((a) => {
  if (a.name === RETRY_ALARM && wanted && !ws) void connect();
});

function close() {
  clearInterval(pingTimer);
  const socket = ws;
  ws = null;
  socket?.close(1000, "licence changed");
  void ext.alarms.clear(RETRY_ALARM);
}

/** The API address changed: drop the connection and come back on the new one. */
export function restart(): void {
  if (!wanted) return;
  close();
  attempt = 0;
  void connect();
}

function parse(data: unknown): SocketIn | null {
  if (typeof data !== "string") return null;
  try {
    const v = JSON.parse(data) as { type?: unknown };
    return typeof v?.type === "string" ? (v as SocketIn) : null;
  } catch {
    return null;
  }
}
