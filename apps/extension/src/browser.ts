/**
 * One namespace for both browsers.
 *
 * Firefox exposes `browser` (promise-returning) and a `chrome` alias; Chrome
 * exposes only `chrome`, whose MV3 APIs return promises when no callback is
 * passed. Every API this extension uses -- `storage`, `runtime`, `alarms`,
 * `action`, `tabs` -- is promise-shaped in both, so the same bundle runs in
 * either and only the manifest differs (`scripts/firefox-manifest.mjs`).
 *
 * `browser` is preferred only when it is a real WebExtension namespace: some
 * pages carry a `browser` global with nothing but `runtime` on it (other
 * extensions' content scripts leave one), and `storage` is what tells them apart.
 */

declare const browser: typeof chrome | undefined;

function pick(): typeof chrome {
  if (typeof browser !== "undefined" && browser && "storage" in browser && browser.storage) return browser;
  return chrome;
}

export const ext: typeof chrome = pick();
