import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

/**
 * Two entries:
 *   sidepanel  -> index.html, the React UI Chrome loads as the side panel
 *   background -> background.js, the MV3 service worker
 *
 * background must land at a fixed, unhashed path because manifest.json
 * references it by name.
 *
 * There is no content-script entry. capture.ts reads the page's selection
 * on demand via activeTab + chrome.scripting.executeScript when the user
 * clicks "Capture screen" — see 8cd4790, which made the same call for the
 * popup: no standing <all_urls> permission, nothing runs until asked.
 */
export default defineConfig({
  plugins: [react()],

  build: {
    rollupOptions: {
      input: {
        sidepanel: resolve(import.meta.dirname, "index.html"),
        background: resolve(import.meta.dirname, "src/background.ts"),
      },

      output: {
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "background") return "background.js";

          return "assets/[name]-[hash].js";
        },
      },
    },
  },
});
