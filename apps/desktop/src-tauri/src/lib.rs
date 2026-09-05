use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::ShortcutState;

/// Forwards a webview console message to the process's own stderr.
///
/// A `WKWebView` does not reliably surface `console.error` to the terminal that
/// launched it — that is why `daily_updates/2026-09-03.md` could confirm the
/// window rendered but had to record "zero console errors" as *unverified*,
/// with no devtools attached. W1D1's number asks for that claim, so the webview
/// hands its errors to Rust rather than the terminal being trusted to have
/// caught them.
///
/// Prefixed and on stderr so `pnpm tauri dev` output can be grepped for it.
#[tauri::command]
fn log_webview(level: &str, message: &str) {
    eprintln!("[webview:{level}] {message}");
}

/// Cmd/Ctrl+Shift+K: the click-through emergency disarm.
///
/// **Found the hard way on W1D3, on-device.** `clickThrough.ts`'s original
/// design relied on `Escape` reaching the window's own keydown listener — which
/// requires the webview to hold *keyboard* focus, not just for the app to be
/// "active" via Cmd+Tab. In practice, refocusing via Cmd+Tab or the Dock icon
/// did not reliably return keyboard focus to the WKWebView, so `Escape` went
/// nowhere and the window stayed armed — every click still passing through,
/// permanently, with no way back short of killing the process. That is exactly
/// the failure `phase-2-month-one.md` W2D2 warns about: "a hotkey that only
/// works when our window is already focused is not a hotkey."
///
/// This is that hotkey, pulled forward from W2D2 because W1D3's toggle is
/// provably unusable without it. Registered at the OS level via
/// `global-hotkey`, so it fires regardless of which app currently has focus —
/// MT5's browser tab included — which is the one property `Escape` didn't
/// have. It calls `set_ignore_cursor_events(false)` directly on the Rust side,
/// not through a JS round-trip: if the frontend is for any reason unresponsive,
/// the window still becomes clickable again. The `click-through-disarmed`
/// event exists only to sync React's `enabled` state (so the crosshair icon
/// reflects reality) — the window itself is already unstuck before that event
/// is even sent.
const DISARM_SHORTCUT: &str = "CommandOrControl+Shift+K";

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state != ShortcutState::Pressed {
                        return;
                    }

                    // No shortcut-identity check: exactly one shortcut is ever
                    // registered (`DISARM_SHORTCUT`), so any invocation of this
                    // handler is unambiguously that one. An earlier version
                    // matched the pressed combo against `Modifiers::SHIFT`
                    // alone -- omitting Cmd/Ctrl -- which meant `matches()`
                    // never returned true for the actual `CommandOrControl+
                    // Shift+K` press and the disarm silently never fired.
                    // Found on-device: the hotkey was registered without error
                    // and simply never did anything. Reconstructing the exact
                    // modifier bitmask correctly is more failure-prone than
                    // just not needing the check at all.
                    if let Some(window) = app.get_webview_window("main") {
                        // The disarm itself, independent of anything the
                        // frontend is doing right now.
                        if let Err(e) = window.set_ignore_cursor_events(false) {
                            eprintln!("[click-through] emergency disarm failed: {e}");
                        }
                    }

                    // Best-effort UI sync. A failure here means the icon shows
                    // stale state next paint, not that the window is stuck --
                    // the disarm above already happened.
                    let _ = app.emit("click-through-disarmed", ());
                })
                .build(),
        )
        .setup(|app| {
            use tauri_plugin_global_shortcut::GlobalShortcutExt;
            app.global_shortcut().register(DISARM_SHORTCUT)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![log_webview])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
