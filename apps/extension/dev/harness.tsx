/**
 * The harness: the real service worker module, the real content script and
 * the real popup, all in one page, over `chrome-stub.ts`. Run `vite dev` and
 * open /dev/harness.html. Everything except "Load unpacked" can be checked
 * here against a local API -- the socket connects from this page's origin
 * (`http://localhost:1420`, which the API's origin list allows).
 */

import { createRoot } from "react-dom/client";

import { installChromeStub } from "./chrome-stub";

installChromeStub();

// Order matters: the worker registers its onMessage listener before anything
// sends. Dynamic imports so the stub is in place when their modules evaluate.
await import("../src/background/index");
await import("../src/content/main");
const { Popup } = await import("../src/popup/Popup");
await import("../src/ui.css");

// The popup, docked bottom-right so both surfaces are visible at once.
const dock = document.createElement("div");
dock.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483646;border:1px solid #333;border-radius:12px;overflow:hidden";
document.body.appendChild(dock);
createRoot(dock).render(<Popup />);

document.getElementById("break-title")?.addEventListener("click", () => {
  document.title = "Something the adapter cannot parse — TradingView";
  document.querySelector('[data-name="legend-source-title"]')?.remove();
});
document.getElementById("reset")?.addEventListener("click", () => {
  localStorage.removeItem("vh.harness.storage");
  location.reload();
});
