import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * The popup and the service worker, as ES modules.
 *
 * `background.js` lands at a fixed, unhashed path because manifest.json
 * names it. The content script is NOT here: a content script is one classic
 * script with no imports, so it is a second, IIFE build --
 * `vite.content.config.ts` -- and `package.json`'s `build` runs both. Neither
 * clears `dist/` (`emptyOutDir: false` below, and the content build writes
 * into the same folder), so the order in `build` does not matter.
 */
export default defineConfig({
  plugins: [react()],
  build: {
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(import.meta.dirname, "popup.html"),
        background: resolve(import.meta.dirname, "src/background/index.ts"),
      },
      output: {
        entryFileNames: (chunk) => (chunk.name === "background" ? "background.js" : "assets/[name]-[hash].js"),
      },
    },
  },
});
