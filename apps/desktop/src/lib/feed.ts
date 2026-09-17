/**
 * W3D1 · one feed connection for the whole shell, and what state it is in.
 *
 * Until this file existed the engine was connected from inside `FlowView`'s
 * effect, which meant two things a trader would notice and nobody in the room
 * had: the feed only existed while the Order Flow view was open, and its state
 * was invisible from every other view. The four-state indicator
 * `plans/team/prathamesh/README.md` asks for on W3D1 is a shell concern, so the
 * connection is too.
 *
 * ## Why a module store rather than state in `SidePanel`
 *
 * Two consumers need the same status — the topbar pill and the Flow view's own
 * header — and `FlowView` takes no props. Threading it through would work; a
 * second `connect()` from the view would not, because S2 has no `disconnect`
 * and the mock's generation guard exists precisely because overlapping connects
 * once orphaned a replay scheduler (see `mock.ts`). One `start()`, idempotent,
 * and `useSyncExternalStore` for anyone who wants to read it.
 *
 * ## `stale` gets a clock
 *
 * S2's comment on `FeedState`: *stale is connected but not receiving, which
 * looks identical to a quiet market and is not.* The label alone does not fix
 * that from three feet away; a number that keeps growing does. So the pill
 * renders `Stale 42s` rather than `Stale`.
 *
 * **The clock counts from the transition into `stale`, not from
 * `lastTickAt`.** The first version did the latter and the mock rendered
 * `Stale 5512993s` — the fixture's ticks are stamped July 2026, so "since the
 * last tick" was sixty-three days. S2 promises no clock domain for
 * `lastTickAt`, and a replay has every right to keep the data's own. Time in
 * state is wall-clock by construction and needs nothing from the engine.
 *
 * ## Credentials
 *
 * On start, the shell asks `lib/creds.ts` for the last vendor's saved
 * credentials and connects with those; with none saved it connects as
 * `{ vendor: "mock" }`, the call `FlowView` used to make. `reconnect()` is the
 * form's path — save, then connect with what was saved. S2 has no
 * `disconnect`, so a reconnect is just another `connect()`, which is exactly
 * the overlapping-connect case the mock's generation guard exists for.
 *
 * The fields inside `FeedCreds` are still the open hole `engine/types.ts`
 * describes; nothing here reads them. They go from the form to the keychain
 * to `connect()` as an opaque map.
 */

import { useEffect, useState, useSyncExternalStore } from "react";

import { lastVendor, loadFeedCreds } from "./creds";
import { getEngine } from "./engine";
import type { FeedCreds, FeedStatus } from "./engine/types";

export interface FeedSnapshot {
  status: FeedStatus;
  /** Why `connect()` rejected, if it did. The pill shows `No feed` either way. */
  error: string | null;
  /** Wall-clock ms at which `status.state` last changed. */
  stateSince: number;
}

export interface Feed extends FeedSnapshot {
  /** Milliseconds in the current state. Updated once a second while stale. */
  inStateMs: number;
}

const OFFLINE: FeedStatus = {
  state: "disconnected",
  vendor: null,
  lastTickAt: null,
  gapCount: 0,
};

let snapshot: FeedSnapshot = { status: OFFLINE, error: null, stateSince: Date.now() };
let started = false;
const listeners = new Set<() => void>();

function publish(next: Partial<Pick<FeedSnapshot, "status" | "error">>) {
  const changed = next.status !== undefined && next.status.state !== snapshot.status.state;
  // A new object every time: `useSyncExternalStore` compares by identity.
  snapshot = { ...snapshot, ...next, stateSince: changed ? Date.now() : snapshot.stateSince };
  for (const l of listeners) l();
}

/**
 * Connect once, for the life of the module. Safe to call from every consumer;
 * only the first call does anything. `getEngine()` throwing under
 * `VITE_ENGINE=real` is deliberate and propagates — `engine/index.ts` explains
 * why a UI that will not start beats one quietly replaying July.
 */
function start() {
  if (started) return;
  started = true;

  const engine = getEngine();
  engine.onStatus((status) => publish({ status }));

  void (async () => {
    const vendor = lastVendor();
    let creds: FeedCreds = { vendor: "mock" };
    if (vendor) {
      try {
        creds = (await loadFeedCreds(vendor)) ?? creds;
      } catch (e) {
        // A keychain that will not open is a reason to say so, not to
        // pretend there were no credentials.
        publish({ error: e instanceof Error ? e.message : String(e) });
      }
    }
    await connectWith(creds);
  })();
}

async function connectWith(creds: FeedCreds): Promise<void> {
  try {
    const status = await getEngine().connect(creds);
    publish({ status, error: null });
  } catch (e) {
    publish({ error: e instanceof Error ? e.message : String(e) });
  }
}

/** Connect (again) with these credentials. The form calls this after saving. */
export function reconnect(creds: FeedCreds): Promise<void> {
  start();
  return connectWith(creds);
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  start();
  return () => {
    listeners.delete(cb);
  };
}

const getSnapshot = () => snapshot;

export function useFeed(): Feed {
  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const counting = snap.status.state === "stale";

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!counting) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [counting]);

  return { ...snap, inStateMs: Math.max(0, now - snap.stateSince) };
}

/** `42s` under a minute, `3m` under an hour, `1h+` past it. Short on purpose. */
export function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return "1h+";
}
