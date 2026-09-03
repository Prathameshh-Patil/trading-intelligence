import { invoke } from "@tauri-apps/api/core";

/**
 * Mirrors webview errors and warnings to the Rust process's stderr.
 *
 * A `WKWebView` does not reliably forward `console.error` to the terminal that
 * launched it, so a clean `pnpm tauri dev` log has never been evidence of a
 * clean console — `daily_updates/2026-09-03.md` recorded exactly that gap and
 * left W1D1's "zero console errors" unverifiable without attaching an
 * inspector. This closes it: anything that would have been swallowed arrives
 * as a `[webview:*]` line the terminal can be grepped for.
 *
 * Console methods are wrapped rather than replaced — the original still runs,
 * so an attached inspector sees exactly what it saw before.
 */
export function installWebviewLogBridge(): void {
  const forward = (level: string, args: unknown[]) => {
    const message = args
      .map((arg) => {
        if (arg instanceof Error) return `${arg.name}: ${arg.message}`;
        if (typeof arg === "string") return arg;

        try {
          return JSON.stringify(arg);
        } catch {
          return String(arg);
        }
      })
      .join(" ");

    // A failure here must never itself raise: the bridge is diagnostics, and a
    // throwing logger would corrupt the very thing it is measuring.
    void invoke("log_webview", { level, message }).catch(() => {});
  };

  for (const level of ["error", "warn"] as const) {
    const original = console[level].bind(console);

    console[level] = (...args: unknown[]) => {
      original(...args);
      forward(level, args);
    };
  }

  // Uncaught exceptions and rejected promises never reach console.error on
  // their own, and they are the failures that matter most.
  window.addEventListener("error", (event) => {
    forward("uncaught", [event.message, `${event.filename}:${event.lineno}`]);
  });

  window.addEventListener("unhandledrejection", (event) => {
    forward("unhandledrejection", [event.reason]);
  });
}
