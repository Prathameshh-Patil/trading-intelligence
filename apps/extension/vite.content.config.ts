import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * The content script: one self-contained classic script.
 *
 * Chrome injects `content_scripts[].js` as plain scripts -- no `import`, no
 * module graph -- so React, the panel and its CSS (imported `?inline` and
 * written into the shadow root) are bundled into a single IIFE. Runs after
 * `vite.config.ts` into the same `dist/`, which it must not empty.
 */
export default defineConfig({
  plugins: [react()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    emptyOutDir: false,
    lib: {
      entry: resolve(import.meta.dirname, "src/content/main.tsx"),
      name: "VisionHubContent",
      formats: ["iife"],
      fileName: () => "content.js",
    },
    rollupOptions: {
      output: { inlineDynamicImports: true },
    },
  },
});
