import { isExtension } from "./storage";
import type { Capture } from "./types";

const DEMO_TEXT =
  "Nvidia beat consensus on both revenue and guidance, with data-centre growth accelerating for a third straight quarter. Management raised the full-year outlook, citing record backlog and strong hyperscaler demand.";

/**
 * Capture what the user is currently looking at: a screenshot of the visible
 * tab plus any text they have highlighted.
 *
 * Outside the extension (dev server / hosted preview) this returns a synthetic
 * chart and sample headline so the flow stays explorable.
 */
export async function captureScreen(): Promise<Capture> {
  if (!isExtension()) {
    return {
      text: DEMO_TEXT,
      screenshot: drawSyntheticChart(),
      url: "https://example.com/markets/nvda-earnings",
      title: "Nvidia beats on revenue and raises guidance",
      capturedAt: Date.now(),
    };
  }

  const stored = await chrome.storage.local.get([
    "selectedText",
    "selectedUrl",
    "selectedTitle",
  ]);

  let screenshot: string | undefined;

  try {
    screenshot = await chrome.tabs.captureVisibleTab({ format: "png" });
  } catch {
    // captureVisibleTab needs an active, capturable tab. A missing screenshot
    // is not fatal — the text path still works.
    screenshot = undefined;
  }

  let url = stored.selectedUrl as string | undefined;
  let title = stored.selectedTitle as string | undefined;

  if (!url) {
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });

      url = tab?.url;
      title = tab?.title;
    } catch {
      // Ignore — url/title are decorative here.
    }
  }

  return {
    text: (stored.selectedText as string | undefined) ?? "",
    screenshot,
    url,
    title,
    capturedAt: Date.now(),
  };
}

/**
 * Deterministic candlestick chart rendered to a data URL, used as the capture
 * stand-in when no real tab is available.
 */
function drawSyntheticChart(): string | undefined {
  if (typeof document === "undefined") return undefined;

  const w = 560;
  const h = 300;

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;

  const ctx = canvas.getContext("2d");
  if (!ctx) return undefined;

  ctx.fillStyle = "#0b0d13";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;

  for (let i = 1; i < 5; i += 1) {
    const y = (h / 5) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // Deterministic pseudo-random walk so the preview never flickers.
  let seed = 20260823;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };

  const count = 42;
  const slot = w / count;
  let price = h * 0.72;

  for (let i = 0; i < count; i += 1) {
    const drift = (rand() - 0.42) * 16;
    const open = price;
    const close = Math.min(Math.max(open + drift, 30), h - 30);
    const high = Math.min(open, close) - rand() * 10;
    const low = Math.max(open, close) + rand() * 10;

    const x = i * slot + slot / 2;
    const up = close < open;
    const color = up ? "#34d399" : "#f87171";

    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, high);
    ctx.lineTo(x, low);
    ctx.stroke();

    ctx.fillStyle = color;
    const top = Math.min(open, close);
    const body = Math.max(Math.abs(close - open), 2);
    ctx.fillRect(x - slot * 0.3, top, slot * 0.6, body);

    price = close;
  }

  ctx.fillStyle = "rgba(255,255,255,0.55)";
  ctx.font = "600 13px system-ui, sans-serif";
  ctx.fillText("NVDA  5m", 14, 24);

  return canvas.toDataURL("image/png");
}
