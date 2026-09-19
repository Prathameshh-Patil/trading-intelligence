/**
 * The content script's entry: one host element, one shadow root, React inside.
 *
 * The shadow root is what keeps the page's CSS off the panel and the panel's
 * CSS off the page; the stylesheet is bundled as a string (`?inline`) and
 * written into the root, because a content script cannot reference a
 * stylesheet file by URL without a `web_accessible_resources` grant. Mounted
 * once per page, on `document.documentElement` rather than `body` so a page
 * that replaces its body (single-page apps do) does not take the panel with
 * it.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { read } from "../storage";
import css from "../ui.css?inline";
import { Panel } from "./Panel";

const TAG = "vision-hub-root";

async function mount(): Promise<void> {
  if (document.querySelector(TAG)) return;
  const host = document.createElement(TAG);
  host.style.all = "initial";
  document.documentElement.appendChild(host);

  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = css;
  shadow.appendChild(style);
  const root = document.createElement("div");
  shadow.appendChild(root);

  const { panel } = await read();
  createRoot(root).render(
    <StrictMode>
      <Panel initial={panel[location.host]} />
    </StrictMode>,
  );
}

void mount();
