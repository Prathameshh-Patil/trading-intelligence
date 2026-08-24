import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

/**
 * Three entries:
 *   sidepanel  -> index.html, the React UI Chrome loads as the side panel
 *   content    -> content.js, injected into pages to capture selections
 *   background -> background.js, the MV3 service worker
 *
 * content and background must land at fixed, unhashed paths because
 * manifest.json references them by name.
 */
export default defineConfig({
  plugins: [react()],

  build: {
    rollupOptions: {
      input: {
        sidepanel: resolve(import.meta.dirname, "index.html"),
        content: resolve(import.meta.dirname, "src/content/main.ts"),
        background: resolve(import.meta.dirname, "src/background.ts"),
      },

      output: {
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "content") return "content.js";
          if (chunkInfo.name === "background") return "background.js";

          return "assets/[name]-[hash].js";
        },
      },
    },
  },
});
