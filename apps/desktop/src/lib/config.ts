/**
 * Where the API and the site live, for this build.
 *
 * `VITE_API_BASE` and `VITE_SITE_URL` are inlined by Vite at build time, so a
 * release binary carries one pair of URLs. That is right for the shipped app
 * and wrong for everyone testing it: a beta build pointed at staging, a dev
 * build pointed at a laptop. One `localStorage` key per URL overrides the
 * baked value -- set from the console (`localStorage.setItem("vh.apiBase",
 * "http://localhost:8000")`) and cleared the same way. Non-secret, so it does
 * not belong in the keychain; the same store `ti.licence.lastValidAt` uses.
 *
 * A trailing slash is stripped so callers can append paths without checking.
 */

export const API_BASE_KEY = "vh.apiBase";
export const SITE_URL_KEY = "vh.siteUrl";

function pick(built: unknown, storageKey: string): string | null {
  let value: string | null = null;
  try {
    value = localStorage.getItem(storageKey);
  } catch {
    // No storage (a very early load, or storage disabled): the build's value.
  }
  if (!value && built) value = String(built);
  if (!value) return null;
  return value.trim().replace(/\/+$/, "") || null;
}

export const API_BASE: string | null = pick(import.meta.env.VITE_API_BASE, API_BASE_KEY);
export const SITE_URL: string | null = pick(import.meta.env.VITE_SITE_URL, SITE_URL_KEY);

/** True when a `localStorage` override is in effect for either URL. */
export function overridden(): boolean {
  try {
    return !!(localStorage.getItem(API_BASE_KEY) || localStorage.getItem(SITE_URL_KEY));
  } catch {
    return false;
  }
}
