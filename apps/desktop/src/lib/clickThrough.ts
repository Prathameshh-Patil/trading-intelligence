/**
 * W1D3 · click-through — the overlay's first real behaviour, not just its shape.
 *
 * `phase-2-month-one.md`: "transparent regions pass clicks to MT5 underneath and
 * the opaque regions don't — get the hit-test region right, because 'sometimes
 * swallows a click on a live chart' is the kind of bug that loses a subscriber
 * in Week 10 and gets reported as 'it feels laggy'."
 *
 * ## Why this is a whole-window toggle, not per-pixel hit-testing
 *
 * The obvious design — poll `elementFromPoint` on `pointermove` and flip
 * `setIgnoreCursorEvents` per pixel — was tried first and is wrong on this
 * stack. Tauri's `setIgnoreCursorEvents(ignore)` has no Electron-style
 * `forward` option (checked against `@tauri-apps/api/window.d.ts` before
 * writing this): once `ignore` is `true`, the OS stops delivering **all**
 * mouse events to the window, `pointermove` included. The window that just
 * armed pass-through goes deaf to the cursor at that exact moment, so it can
 * never detect the mouse moving back over a button — a one-way trap, not a
 * toggle. Region-based hit-testing needs per-pixel OS support this API
 * doesn't expose.
 *
 * So click-through here is **the whole window at once**, armed and disarmed
 * explicitly rather than inferred from cursor position.
 *
 * ## Disarming — the part that was wrong on the first attempt
 *
 * The first version disarmed on `Escape`, reasoning that keyboard focus and
 * mouse pass-through are independent OS properties, so the window should keep
 * receiving keystrokes even while it ignores clicks. **True in principle,
 * false in practice, found on-device on W1D3**: after a pass-through click
 * landed on MT5 and Prathamesh switched back via Cmd+Tab / the Dock icon,
 * `Escape` still went nowhere. Cmd+Tab reliably reactivates the *app*; it does
 * not reliably return *keyboard* focus to the specific WKWebView inside a
 * borderless, cursor-ignoring window. The result was a window armed
 * permanently, unclickable, with no way back short of killing the process —
 * exactly what `phase-2-month-one.md` W2D2 already warned a focus-dependent
 * hotkey would do.
 *
 * The fix is `lib.rs`'s `Cmd/Ctrl+Shift+K`, registered at the **OS level**
 * via `tauri-plugin-global-shortcut` — pulled forward from W2D2 because W1D3's
 * toggle is provably unusable without it. It fires regardless of which app
 * currently holds focus, disarms the window directly from Rust (not through a
 * JS round-trip, so a stuck frontend still can't trap the user), and then
 * notifies this hook only to keep the crosshair icon's displayed state
 * truthful. `Escape` stays wired as a secondary path for the case where the
 * webview genuinely does still have focus — it costs nothing to keep and it
 * sometimes works — but the hotkey is the one this is built to depend on.
 */

import { useCallback, useEffect, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen } from "@tauri-apps/api/event";

export interface ClickThroughState {
  /** Whether the whole window is currently passing clicks through. */
  enabled: boolean;
  toggle: () => void;
}

export function useClickThrough(): ClickThroughState {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    // `package.json`'s `dev` script runs this UI as a plain page in a browser
    // for fast iteration, where there is no Tauri runtime and
    // `getCurrentWindow()` THROWS rather than rejecting — so the `.catch`
    // below never sees it and the whole panel fails to mount. Click-through is
    // a window-manager capability that has no meaning outside the window
    // anyway; the hook keeps its React state so the crosshair still toggles,
    // and simply has no OS-level effect there.
    if (!isTauri()) return;

    void getCurrentWindow()
      .setIgnoreCursorEvents(enabled)
      .catch((e: unknown) => {
        console.error("[click-through] setIgnoreCursorEvents failed:", e);
      });
  }, [enabled]);

  // The real disarm path. lib.rs's Cmd/Ctrl+Shift+K handler has already
  // called set_ignore_cursor_events(false) on the Rust side by the time this
  // fires -- this listener only brings React's `enabled` state back in sync
  // so the crosshair icon stops showing armed.
  useEffect(() => {
    // Same reason as above: no Tauri runtime, no event bus to listen on.
    if (!isTauri()) return;

    const un = listen("click-through-disarmed", () => {
      setEnabled(false);
    });
    return () => {
      void un.then((f) => f());
    };
  }, []);

  // Secondary path: fires only while the webview genuinely holds keyboard
  // focus. See the module comment for exactly when that stops being true.
  useEffect(() => {
    if (!enabled) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setEnabled(false);
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);

  // Never leave the window stuck ignoring clicks across a hot-reload or an
  // unmount -- a component swap must not survive as an invisible, unclickable
  // window with no way back short of the global hotkey or quitting.
  useEffect(() => {
    if (!isTauri()) return;

    return () => {
      void getCurrentWindow().setIgnoreCursorEvents(false).catch(() => {});
    };
  }, []);

  const toggle = useCallback(() => setEnabled((v) => !v), []);

  return { enabled, toggle };
}
