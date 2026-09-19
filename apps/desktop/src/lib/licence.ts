/**
 * The desktop's licence: `@vision-hub/core`'s state machine over the OS keychain.
 *
 * Everything about *what* a licence state is and *when* it changes lives in
 * `packages/core/licence.ts`, shared with the browser extension. This file is
 * only where the desktop keeps things:
 *
 * - The key goes webview → Rust → keychain (`src-tauri/src/licence.rs`), the
 *   same path as the feed credentials, and JavaScript never writes it to
 *   anything that persists. Outside Tauri (`pnpm dev` as a plain page) it
 *   lives in memory until reload, exactly as `creds.ts` does -- there is no
 *   dev-mode exception to "never plaintext on disk".
 * - `localStorage` holds one non-secret: the wall-clock time of the last
 *   *successful* validation, which the offline grace is measured from and is
 *   meaningless without the key.
 */

import { invoke, isTauri } from "@tauri-apps/api/core";
import {
  createLicenceStore,
  useLicenceStore,
  type LicenceStorage,
} from "@vision-hub/core";

import { API_BASE } from "./config";

export { KEY_PREFIX, reasonCopy, shortKey, unlocked } from "@vision-hub/core";
export type { InvalidReason, LicenceState } from "@vision-hub/core";
export type { Tier } from "@vision-hub/contracts";

/**
 * Where the API lives -- `lib/config.ts`, which is the build's `VITE_API_BASE`
 * unless a `localStorage` override says otherwise. Unset, validation cannot
 * happen and the licence screen says so rather than every key reading as
 * offline.
 */
export { API_BASE };

// `ti` is the prefix every localStorage key in this app has carried since
// before the rebrand (`ti.` in `creds.ts`, `ti:` in `storage.ts`). It stays:
// renaming it would orphan every trader's saved rules and journal for a
// cosmetic gain.
const LAST_VALID_KEY = "ti.licence.lastValidAt";

/** Whether a stored key survives a restart on this build. */
export const PERSISTENT: boolean = isTauri();

let memoryKey: string | null = null;

const storage: LicenceStorage = {
  async loadKey() {
    if (PERSISTENT) return invoke<string | null>("licence_load");
    return memoryKey;
  },
  async saveKey(key) {
    if (PERSISTENT) await invoke("licence_save", { key });
    else memoryKey = key;
  },
  async clearKey() {
    if (PERSISTENT) await invoke("licence_clear");
    else memoryKey = null;
  },
  async loadLastValidAt() {
    const raw = localStorage.getItem(LAST_VALID_KEY);
    const n = raw ? Number(raw) : NaN;
    return Number.isFinite(n) ? n : null;
  },
  async saveLastValidAt(t) {
    if (t === null) localStorage.removeItem(LAST_VALID_KEY);
    else localStorage.setItem(LAST_VALID_KEY, String(t));
  },
};

const store = createLicenceStore({
  storage,
  apiBase: () => API_BASE,
  setTimer: (fn, ms) => {
    const id = window.setTimeout(fn, ms);
    return () => window.clearTimeout(id);
  },
});

export const activate = store.activate;
export const deactivate = store.deactivate;
export const recheck = store.recheck;

export function useLicence() {
  return useLicenceStore(store);
}
