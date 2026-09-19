/**
 * Derives the Firefox build from the Chrome one.
 *
 * Two manifests are unavoidable -- Chrome MV3 rejects `background.scripts`,
 * Firefox rejects `background.service_worker`, so no single file loads in
 * both. But a hand-maintained second copy drifts: a version bump, a new host
 * or a renamed icon lands in one and not the other, and the gap surfaces when
 * somebody happens to load the other browser. So `public/manifest.json` is
 * the single source of truth and this applies the differences, all mechanical:
 *
 *   1. `background.service_worker` -> `background.scripts`. Firefox MV3 uses
 *      event pages; the bundle is unchanged (`src/browser.ts` branches at runtime).
 *   2. Drop `minimum_chrome_version`. Firefox is gated by
 *      `browser_specific_settings.gecko.strict_min_version` instead.
 *
 * Everything else -- content scripts, host permissions, action, icons, CSP,
 * the gecko block -- is carried across untouched. Output is `dist-firefox/`,
 * a copy of `dist/` with the manifest swapped, so each folder loads as-is.
 */

import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");
const out = resolve(root, "dist-firefox");

const chrome = JSON.parse(readFileSync(resolve(dist, "manifest.json"), "utf8"));

const { minimum_chrome_version: _chromeOnly, background, ...rest } = chrome;
const firefox = {
  ...rest,
  background: { scripts: [background.service_worker], type: background.type },
};

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
cpSync(dist, out, { recursive: true });
writeFileSync(resolve(out, "manifest.json"), JSON.stringify(firefox, null, 2) + "\n");
console.log(`firefox manifest -> ${out}/manifest.json`);
