/**
 * The licence: whether an installed client is allowed to run, and why not.
 *
 * Moved out of `apps/desktop/src/lib/licence.ts` so the desktop app and the
 * browser extension share one state machine rather than two copies that
 * drift. What lives here is everything that does not care where it runs:
 * the key's shape, the five states, the grace rules, the check that settles
 * a state, the re-check clock, and the store. What each platform supplies is
 * a `LicenceStorage` (keychain on the desktop, `chrome.storage` in the
 * extension), where the API is, and a timer.
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
 * A missing or invalid key hard-gates the app. Only *unreachable* gets grace,
 * and only for a week -- after that an unreachable server reads as `invalid`
 * with reason `unknown`, because a key nobody has been able to check for a
 * week is not a key we can vouch for. The grace expires in a running app,
 * not only on relaunch.
 *
 * ## Re-validation
 *
 * On start, and every six hours while running. A revoke in the admin portal
 * therefore lands within six hours, or immediately on the next launch. The
 * server writes `last_validated_at` on every yes, which is the "Activated in
 * the app" step on the trader's account page.
 */

import { useSyncExternalStore } from 'react'

import { validateKey as defaultValidate } from '@vision-hub/contracts'
import type { Tier, ValidateResponse } from '@vision-hub/contracts'

export const KEY_PREFIX = 'vh_live_'
/** `vh_live_` + exactly 32 of `[a-z0-9]`, per S3. Checked before any network call. */
export const KEY_RE = /^vh_live_[a-z0-9]{32}$/

export const OFFLINE_GRACE_MS = 7 * 24 * 60 * 60 * 1000
export const RECHECK_MS = 6 * 60 * 60 * 1000

export type InvalidReason = 'expired' | 'revoked' | 'unknown' | 'malformed'

export type LicenceState =
  | { kind: 'unactivated' }
  | { kind: 'checking'; key: string }
  | { kind: 'active'; key: string; tier: Tier; expiresAt: string | null; checkedAt: number }
  | { kind: 'invalid'; key: string; reason: InvalidReason }
  | { kind: 'offline'; key: string; lastValidAt: number; error: string }

/** What the trader is told for each `invalid` reason. One copy, both apps. */
export const reasonCopy: Record<InvalidReason, string> = {
  expired: 'This key has expired. Your account page has the current one.',
  revoked: 'This key has been revoked -- rotated from your account page, or the account was suspended.',
  unknown: 'The server does not recognise this key, or could not be reached to check it.',
  malformed: `A key is ${KEY_PREFIX} followed by exactly 32 letters and digits. Check the paste.`,
}

/** Whether the rest of the app may render. `checking` on launch shows the
 *  licence screen briefly rather than flashing the home view. */
export function unlocked(s: LicenceState): boolean {
  return s.kind === 'active' || s.kind === 'offline'
}

/** `vh_live_ab…yz`, for a pill or a title. */
export function shortKey(key: string): string {
  return key.length > 16 ? `${key.slice(0, 11)}…${key.slice(-4)}` : key
}

/* ------------------------------------------------------------------ */
/* The seam                                                            */
/* ------------------------------------------------------------------ */

/**
 * Where the key and the last-good timestamp live. The key is a secret and
 * goes wherever the platform keeps secrets; the timestamp is not, and only
 * means anything beside the key.
 */
export interface LicenceStorage {
  loadKey(): Promise<string | null>
  saveKey(key: string): Promise<void>
  clearKey(): Promise<void>
  loadLastValidAt(): Promise<number | null>
  saveLastValidAt(t: number | null): Promise<void>
}

export interface LicenceStoreOptions {
  storage: LicenceStorage
  /** Null means this build cannot validate; the store says so as `invalid/unknown`. */
  apiBase: () => string | null
  /** Injected by tests; contracts' `validateKey` otherwise. */
  validate?: (apiBase: string, key: string) => Promise<ValidateResponse>
  /** `window.setTimeout` on the desktop; an alarm in the extension. Returns a cancel. */
  setTimer?: (fn: () => void, ms: number) => () => void
  now?: () => number
  /** Where a keychain read failure is reported. `console.error` by default. */
  onError?: (context: string, error: unknown) => void
}

export interface LicenceStore {
  getState(): LicenceState
  subscribe(listener: () => void): () => void
  /** Load the stored key and check it. Idempotent; `subscribe` calls it. */
  start(): void
  /** Paste → save → validate. Saved before it is checked, so a valid key
   *  entered while offline is still there next launch. */
  activate(raw: string): Promise<LicenceState>
  /** Forget the key. The app returns to the licence screen. */
  deactivate(): Promise<void>
  /** Check the stored key again now. */
  recheck(): Promise<LicenceState>
}

/* ------------------------------------------------------------------ */
/* The decision                                                        */
/* ------------------------------------------------------------------ */

/**
 * Settle a state from the server's answer, or from its silence. Pure: the
 * caller supplies the last-good timestamp and the clock.
 */
export function settle(
  key: string,
  outcome: { ok: true; res: ValidateResponse } | { ok: false; error: string },
  lastValidAt: number | null,
  now: number,
): LicenceState {
  if (outcome.ok) {
    const res = outcome.res
    if (res.valid) {
      return { kind: 'active', key, tier: res.tier, expiresAt: res.expires_at, checkedAt: now }
    }
    return { kind: 'invalid', key, reason: res.reason }
  }
  if (lastValidAt !== null && now - lastValidAt < OFFLINE_GRACE_MS) {
    return { kind: 'offline', key, lastValidAt, error: outcome.error }
  }
  // Never validated, or not for a week: no grace to give. On a fresh paste
  // this reads as "could not reach the server"; the view says exactly that.
  return { kind: 'invalid', key, reason: 'unknown' }
}

/* ------------------------------------------------------------------ */
/* The store                                                           */
/* ------------------------------------------------------------------ */

const defaultTimer = (fn: () => void, ms: number): (() => void) => {
  const id = setTimeout(fn, ms)
  return () => clearTimeout(id)
}

export function createLicenceStore(o: LicenceStoreOptions): LicenceStore {
  const validate = o.validate ?? defaultValidate
  const setTimer = o.setTimer ?? defaultTimer
  const now = o.now ?? Date.now
  const onError = o.onError ?? ((ctx, e) => console.error(`[licence] ${ctx}:`, e))

  let state: LicenceState = { kind: 'unactivated' }
  let started = false
  let cancelRecheck: (() => void) | null = null
  const listeners = new Set<() => void>()

  const publish = (next: LicenceState) => {
    state = next
    for (const l of listeners) l()
  }

  async function check(key: string): Promise<LicenceState> {
    if (!KEY_RE.test(key)) return { kind: 'invalid', key, reason: 'malformed' }
    const base = o.apiBase()
    if (!base) return { kind: 'invalid', key, reason: 'unknown' }
    let outcome: Parameters<typeof settle>[1]
    try {
      outcome = { ok: true, res: await validate(base, key) }
    } catch (e) {
      outcome = { ok: false, error: e instanceof Error ? e.message : String(e) }
    }
    const t = now()
    const next = settle(key, outcome, await o.storage.loadLastValidAt(), t)
    if (next.kind === 'active') await o.storage.saveLastValidAt(t)
    else if (next.kind === 'invalid' && outcome.ok) await o.storage.saveLastValidAt(null)
    return next
  }

  function scheduleRecheck() {
    cancelRecheck?.()
    cancelRecheck = setTimer(() => {
      if (state.kind === 'active' || state.kind === 'offline') {
        void check(state.key).then((next) => {
          publish(next)
          scheduleRecheck()
        })
      }
    }, RECHECK_MS)
  }

  function start() {
    if (started) return
    started = true
    void (async () => {
      let key: string | null = null
      try {
        key = await o.storage.loadKey()
      } catch (e) {
        // A keychain that will not open is worth saying; the screen shows it
        // as an unactivated app, and a paste can still work.
        onError('key read failed', e)
      }
      if (!key) {
        publish({ kind: 'unactivated' })
        return
      }
      publish({ kind: 'checking', key })
      publish(await check(key))
      scheduleRecheck()
    })()
  }

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener)
      start()
      return () => {
        listeners.delete(listener)
      }
    },
    start,
    async activate(raw) {
      const key = raw.trim()
      if (!KEY_RE.test(key)) {
        const next: LicenceState = { kind: 'invalid', key, reason: 'malformed' }
        publish(next)
        return next
      }
      publish({ kind: 'checking', key })
      await o.storage.saveKey(key)
      const next = await check(key)
      publish(next)
      if (next.kind === 'active') scheduleRecheck()
      return next
    },
    async deactivate() {
      cancelRecheck?.()
      cancelRecheck = null
      await o.storage.clearKey()
      await o.storage.saveLastValidAt(null)
      publish({ kind: 'unactivated' })
    },
    async recheck() {
      if (state.kind === 'unactivated') return state
      const key = state.key
      publish({ kind: 'checking', key })
      const next = await check(key)
      publish(next)
      return next
    },
  }
}

/** React binding. Subscribing starts the store. */
export function useLicenceStore(store: LicenceStore): LicenceState {
  return useSyncExternalStore(store.subscribe, store.getState, store.getState)
}
