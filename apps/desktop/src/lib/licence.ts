/**
 * The licence: the key, where it lives, and whether the app is allowed to run.
 *
 * S3 is the whole wire (`plans/team/contracts.md`): `POST /api/v1/keys/validate`
 * with the key in `X-API-Key`, and **`valid: false` is a 200, not a 401** --
 * so this file can tell "your key is bad" from "we could not reach the
 * server", because those demand opposite responses from the trader.
 *
 * ## The five states
 *
 *   unactivated  no key stored                          → licence screen
 *   checking     a validate call is in flight           → licence screen (first) / keep working (re-check)
 *   active       the server said yes                    → the app
 *   invalid      the server said no, with its reason    → licence screen
 *   offline      no answer, and the key was valid within OFFLINE_GRACE_MS
 *                                                       → the app, with the pill saying so
 *
 * A missing or invalid key hard-gates the app: that is what "adding it to
 * Tauri enables it" means on `/account`. Only *unreachable* gets grace, and
 * only for a week -- after that an unreachable server reads as `invalid`
 * with reason `unknown`, because a key nobody has been able to check for a
 * week is not a key we can vouch for.
 *
 * ## Where things are kept
 *
 * The key goes webview → Rust → keychain (`src-tauri/src/licence.rs`), the
 * same path as the feed credentials, and JavaScript never writes it to
 * anything that persists. `localStorage` holds one non-secret: the wall-clock
 * time of the last *successful* validation, which is what the offline grace
 * is measured from and is meaningless without the key.
 *
 * Outside Tauri (`pnpm dev` as a plain page) the key lives in memory until
 * reload, exactly as `creds.ts` does -- there is no dev-mode exception to
 * "never plaintext on disk".
 *
 * ## Re-validation
 *
 * On launch, and every six hours while running. A revoke in the admin
 * portal therefore lands within six hours, or immediately on the next
 * launch. The server writes `last_validated_at` on every yes, which is the
 * "Activated in the app" step on the trader's account page.
 */

import { invoke, isTauri } from "@tauri-apps/api/core";
import { useSyncExternalStore } from "react";

export const KEY_PREFIX = "vh_live_";
/** `vh_live_` + exactly 32 of `[a-z0-9]`, per S3. Checked before any network call. */
const KEY_RE = /^vh_live_[a-z0-9]{32}$/;

const OFFLINE_GRACE_MS = 7 * 24 * 60 * 60 * 1000;
const RECHECK_MS = 6 * 60 * 60 * 1000;
// `ti` is the prefix every localStorage key in this app has carried since
// before the rebrand (`ti.` in `creds.ts`, `ti:` in `storage.ts`). It stays:
// renaming it would orphan every trader's saved rules and journal for a
// cosmetic gain.
const LAST_VALID_KEY = "ti.licence.lastValidAt";

export type Tier = "core" | "core_journal";
export type InvalidReason = "expired" | "revoked" | "unknown" | "malformed";

export type LicenceState =
  | { kind: "unactivated" }
  | { kind: "checking"; key: string }
  | { kind: "active"; key: string; tier: Tier; expiresAt: string | null; checkedAt: number }
  | { kind: "invalid"; key: string; reason: InvalidReason }
  | { kind: "offline"; key: string; lastValidAt: number; error: string };

/** Whether a stored key survives a restart on this build. */
export const PERSISTENT: boolean = isTauri();

/**
 * Where the API lives. `VITE_API_BASE` is the one setting; unset, validation
 * cannot happen and the licence screen says so rather than every key reading
 * as offline.
 */
export const API_BASE: string | null = import.meta.env.VITE_API_BASE
  ? String(import.meta.env.VITE_API_BASE).replace(/\/+$/, "")
  : null;

/* ------------------------------------------------------------------ */
/* Storage                                                             */
/* ------------------------------------------------------------------ */

let memoryKey: string | null = null;

async function loadKey(): Promise<string | null> {
  if (PERSISTENT) return invoke<string | null>("licence_load");
  return memoryKey;
}

async function saveKey(key: string): Promise<void> {
  if (PERSISTENT) await invoke("licence_save", { key });
  else memoryKey = key;
}

async function clearKey(): Promise<void> {
  if (PERSISTENT) await invoke("licence_clear");
  else memoryKey = null;
  localStorage.removeItem(LAST_VALID_KEY);
}

function lastValidAt(): number | null {
  const raw = localStorage.getItem(LAST_VALID_KEY);
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : null;
}

/* ------------------------------------------------------------------ */
/* The wire                                                            */
/* ------------------------------------------------------------------ */

type ValidateResponse =
  | { valid: true; tier: Tier; expires_at: string | null; reason: null }
  | { valid: false; tier: null; expires_at: null; reason: "expired" | "revoked" | "unknown" };

/**
 * One S3 call. Resolves to the server's answer, or throws when there was no
 * answer -- a network failure, a 5xx, a body that is not S3's shape. The
 * caller decides what "no answer" means; this function does not guess.
 */
export async function validateKey(key: string): Promise<ValidateResponse> {
  if (!API_BASE) throw new Error("VITE_API_BASE is not set; the key cannot be checked.");
  const r = await fetch(`${API_BASE}/api/v1/keys/validate`, {
    method: "POST",
    headers: { "X-API-Key": key },
  });
  if (!r.ok) throw new Error(`key service answered ${r.status}`);
  const body = (await r.json()) as Partial<ValidateResponse>;
  if (typeof body.valid !== "boolean") throw new Error("key service answered with the wrong shape");
  return body as ValidateResponse;
}

/* ------------------------------------------------------------------ */
/* The store                                                           */
/* ------------------------------------------------------------------ */

let state: LicenceState = { kind: "unactivated" };
let started = false;
let recheckTimer: number | undefined;
const listeners = new Set<() => void>();

function publish(next: LicenceState) {
  state = next;
  for (const l of listeners) l();
}

/**
 * Check `key` against the server and settle the state. An unreachable server
 * means `offline` only while the last successful validation is inside the
 * grace window; otherwise -- a fresh paste, or a week without an answer --
 * there is nothing to vouch for and the key reads as invalid.
 */
async function check(key: string): Promise<LicenceState> {
  if (!KEY_RE.test(key)) {
    return { kind: "invalid", key, reason: "malformed" };
  }
  try {
    const res = await validateKey(key);
    if (res.valid) {
      const now = Date.now();
      localStorage.setItem(LAST_VALID_KEY, String(now));
      return { kind: "active", key, tier: res.tier, expiresAt: res.expires_at, checkedAt: now };
    }
    localStorage.removeItem(LAST_VALID_KEY);
    return { kind: "invalid", key, reason: res.reason };
  } catch (e) {
    const error = e instanceof Error ? e.message : String(e);
    const last = lastValidAt();
    if (last !== null && Date.now() - last < OFFLINE_GRACE_MS) {
      return { kind: "offline", key, lastValidAt: last, error };
    }
    // Never validated, or not for a week: no grace to give, on launch or on
    // a re-check alike. The first version kept a running app in `offline`
    // past the week and only locked on relaunch, against this file's own
    // docstring. On a fresh paste this reads as "could not reach the
    // server"; the view says exactly that.
    return { kind: "invalid", key, reason: "unknown" };
  }
}

function scheduleRecheck() {
  window.clearTimeout(recheckTimer);
  recheckTimer = window.setTimeout(() => {
    if (state.kind === "active" || state.kind === "offline") {
      const key = state.key;
      void check(key).then((next) => {
        publish(next);
        scheduleRecheck();
      });
    }
  }, RECHECK_MS);
}

function start() {
  if (started) return;
  started = true;
  void (async () => {
    let key: string | null = null;
    try {
      key = await loadKey();
    } catch (e) {
      // A keychain that will not open is worth saying; the screen shows it
      // as an unactivated app with the error, and a paste can still work.
      console.error("[licence] keychain read failed:", e);
    }
    if (!key) {
      publish({ kind: "unactivated" });
      return;
    }
    publish({ kind: "checking", key });
    publish(await check(key));
    scheduleRecheck();
  })();
}

/** Paste → save → validate. The key is saved before it is checked, so a
 *  valid key entered while offline is still there next launch. */
export async function activate(raw: string): Promise<LicenceState> {
  const key = raw.trim();
  if (!KEY_RE.test(key)) {
    const next: LicenceState = { kind: "invalid", key, reason: "malformed" };
    publish(next);
    return next;
  }
  publish({ kind: "checking", key });
  await saveKey(key);
  const next = await check(key);
  publish(next);
  if (next.kind === "active") scheduleRecheck();
  return next;
}

/** Forget the key. The app returns to the licence screen. */
export async function deactivate(): Promise<void> {
  window.clearTimeout(recheckTimer);
  await clearKey();
  publish({ kind: "unactivated" });
}

/** Check the stored key again now, for the button on the licence screen. */
export async function recheck(): Promise<LicenceState> {
  if (state.kind === "unactivated") return state;
  const key = state.key;
  publish({ kind: "checking", key });
  const next = await check(key);
  publish(next);
  return next;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  start();
  return () => {
    listeners.delete(cb);
  };
}

const getSnapshot = () => state;

export function useLicence(): LicenceState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/** Whether the rest of the app may render. `checking` on launch shows the
 *  licence screen briefly rather than flashing the home view. */
export function unlocked(s: LicenceState): boolean {
  return s.kind === "active" || s.kind === "offline";
}

/** `vh_live_ab…yz`, for a pill or a title. */
export function shortKey(key: string): string {
  return key.length > 16 ? `${key.slice(0, 11)}…${key.slice(-4)}` : key;
}
