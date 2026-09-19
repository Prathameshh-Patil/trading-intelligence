# Vision Hub extension

The desktop overlay in browser form: the same licence gate, a floating panel over the
trader's chart, alerts from the same API. Chrome and Firefox, Manifest V3. For loading a built
copy, see the root README's **Extension** section; this file is for working on it.

## Shape

```
public/manifest.json        Chrome; the one source. scripts/firefox-manifest.mjs derives Firefox's.
src/background/             the service worker: the licence store (@vision-hub/core over
                            chrome.storage + alarms), the WebSocket, the one message handler
src/popup/                  the popup: licence key, connection, tier settings, API address
src/content/                the content script: shadow-root panel, drag, chart adapters
src/content/sites/          tradingview / ctrader / mt5 -- read-only, user-initiated, stays in the page
src/storage.ts              chrome.storage.local schema; it is also the bus (onChanged)
src/messages.ts             what popup and panels may ask the worker to do
dev/harness.html            a fake chart page running all three surfaces over a chrome.* stub
```

Two Vite builds: `vite.config.ts` (popup + worker, ES modules) and `vite.content.config.ts`
(the content script, one IIFE -- a content script is a classic script and cannot import).
`pnpm build` runs both, then writes `dist-firefox/`.

## Run

```sh
cp .env.example .env      # VITE_API_BASE, VITE_SITE_URL -- build-time defaults, both overridable in the popup
pnpm dev                  # then open http://localhost:1420/dev/harness.html
```

The harness is the real `background/index.ts`, `content/main.tsx` and `popup/Popup.tsx` in one
page, with `chrome.storage` over `localStorage` and `runtime.sendMessage` wired straight to the
worker's listener. The socket connects from the page's origin, which the API allows. Activate
with a real key, drag, **Sync chart** (the page's title is TradingView-shaped; *break the
title* exercises the manual fallback), then publish alerts:

```sh
curl -X POST localhost:8000/api/v1/admin/alerts -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"tier":"breaking","title":"…","body":"…","symbol":"XAUUSD"}'
```

Rotate or revoke the key in the portal and the panel re-gates within a second.

## What stays out

- No `activeTab`, no `scripting`, no `<all_urls>`. Four hosts, named in the manifest.
- Nothing read from a page is stored or sent. `ChartRead` is panel state and dies with the tab.
- No eval, no remote code: `content_security_policy.extension_pages` says so and the bundles
  are self-contained.
- The API sees the licence key and nothing else from the extension.

## Firefox

Same bundle. `src/browser.ts` picks `browser` when it is a real WebExtension namespace and
`chrome` otherwise; the manifest differs in `background.scripts` vs `service_worker` and the
absence of `minimum_chrome_version`, and that is all `scripts/firefox-manifest.mjs` changes.
Do not regenerate `browser_specific_settings.gecko.id`.
