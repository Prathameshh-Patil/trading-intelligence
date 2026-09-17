/**
 * Feed credentials — the frontend half of `src-tauri/src/creds.rs`.
 *
 * Three calls, each a thin `invoke` over the Rust command of the same name,
 * so the secret crosses exactly one boundary (webview → Rust → keychain) and
 * is never written by JavaScript to anything that persists. `localStorage`
 * holds one thing only: the **name** of the last vendor used, which is not a
 * secret and is what lets the shell know which keychain entry to open on the
 * next launch.
 *
 * ## Outside Tauri
 *
 * `pnpm dev` runs this UI as a plain page with no Rust behind it. There the
 * store is a `Map` that lives until reload and `PERSISTENT` is `false`, which
 * the form shows. The alternative — `localStorage` as a dev fallback — is a
 * plaintext credential on disk on a developer machine, and the W3D1 rule does
 * not have a dev-mode exception.
 *
 * ## Shape
 *
 * `FeedCreds` is `{ vendor; [field]: string | undefined }` and stays that way
 * until the Ironbeam account (`plans/current.md` #9) exists and its fields
 * are known. This module and the form take the map as-is; the day the fields
 * are known, the form gains labels and this file does not change.
 */

import { invoke, isTauri } from "@tauri-apps/api/core";

import type { FeedCreds } from "./engine/types";

/** Whether saved credentials survive a restart on this build. */
export const PERSISTENT: boolean = isTauri();

const LAST_VENDOR_KEY = "ti.feed.vendor";

const memory = new Map<string, string>();

/** Everything but `vendor`, as the JSON the keychain entry holds. */
function fieldsOf(creds: FeedCreds): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(creds)) {
    if (k !== "vendor" && typeof v === "string" && v !== "") out[k] = v;
  }
  return out;
}

export async function saveFeedCreds(creds: FeedCreds): Promise<void> {
  const json = JSON.stringify(fieldsOf(creds));
  if (PERSISTENT) {
    await invoke("creds_save", { vendor: creds.vendor, fieldsJson: json });
  } else {
    memory.set(creds.vendor, json);
  }
  localStorage.setItem(LAST_VENDOR_KEY, creds.vendor);
}

export async function loadFeedCreds(vendor: string): Promise<FeedCreds | null> {
  const json = PERSISTENT
    ? await invoke<string | null>("creds_load", { vendor })
    : (memory.get(vendor) ?? null);
  if (json === null) return null;
  return { vendor, ...(JSON.parse(json) as Record<string, string>) };
}

export async function clearFeedCreds(vendor: string): Promise<void> {
  if (PERSISTENT) {
    await invoke("creds_clear", { vendor });
  } else {
    memory.delete(vendor);
  }
  if (localStorage.getItem(LAST_VENDOR_KEY) === vendor) {
    localStorage.removeItem(LAST_VENDOR_KEY);
  }
}

/** The vendor whose credentials were last saved, or null. Not a secret. */
export function lastVendor(): string | null {
  return localStorage.getItem(LAST_VENDOR_KEY);
}
