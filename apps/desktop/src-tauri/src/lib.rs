use std::sync::Mutex;

use tauri::{Emitter, Manager, WindowEvent};
use tauri_plugin_global_shortcut::ShortcutState;

mod creds;
mod placement;
use placement::{Placements, Rect};

/// Where the remembered placements live. One file, under the app's own config
/// directory, so uninstalling takes it with it.
const PLACEMENTS_FILE: &str = "placements.json";

/// Reads the current monitor arrangement as plain rectangles.
///
/// Deliberately lossy: `placement` needs geometry and nothing else, and taking
/// only geometry keeps its logic testable without a display server. A machine
/// that cannot enumerate monitors returns an empty slice, which makes every
/// placement unreachable and every restore a no-op -- the window opens at its
/// configured default, which is the safe direction to fail in.
fn monitors_of(window: &tauri::WebviewWindow) -> Vec<Rect> {
    window
        .available_monitors()
        .unwrap_or_default()
        .iter()
        .map(|m| Rect {
            x: m.position().x,
            y: m.position().y,
            width: m.size().width,
            height: m.size().height,
        })
        .collect()
}

/// The window's current outer geometry, or `None` if the OS will not say.
fn current_placement(window: &tauri::WebviewWindow) -> Option<Rect> {
    let pos = window.outer_position().ok()?;
    let size = window.outer_size().ok()?;
    Some(Rect { x: pos.x, y: pos.y, width: size.width, height: size.height })
}

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

/// Cmd/Ctrl+Shift+O: summon and dismiss the overlay.
///
/// W2D2's item, and its own words are the whole specification: *"a hotkey that
/// only works when our window is already focused is not a hotkey."* A trader
/// spends the session in MT5, not in this window, so the toggle has to fire
/// while MT5 holds focus -- which is exactly the property `DISARM_SHORTCUT`
/// already needed, and the same OS-level registration gives it.
///
/// **Why `O`.** MT5's documented default hotkeys are function keys, `Ctrl`+a
/// letter, and `Alt+1/2/3/W`; there is no `Ctrl+Shift+letter` binding among
/// them, so this cannot shadow a chart command. It also sits next to `K` so
/// the two overlay hotkeys read as a pair. cTrader's defaults were **not**
/// checked -- MT5 is the launch platform and this is a default, not a
/// contract; a preference to rebind it is W4's problem, not W2's.
///
/// **Toggle, on the Rust side, from the window's own visibility.** Not from a
/// flag mirrored in React: if the frontend is wedged the trader still needs to
/// get the window out of the way, and `hide()` does not need the webview's
/// cooperation any more than `set_ignore_cursor_events(false)` does. Summon
/// also takes focus, so a hidden window comes back ready for keyboard input
/// rather than merely painted -- the failure `clickThrough.ts` documents is a
/// window that is *active* but not *focused*, and `show()` alone reproduces it.
///
/// Click-through is deliberately left as it was. Hiding an armed window and
/// summoning it armed is consistent; silently disarming on summon would make
/// the crosshair lie until the next paint, and the trader has `⌘⇧K` for that.
const SUMMON_SHORTCUT: &str = "CommandOrControl+Shift+O";

/// The disarm itself, independent of anything the frontend is doing right now.
fn disarm_click_through(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if let Err(e) = window.set_ignore_cursor_events(false) {
            eprintln!("[click-through] emergency disarm failed: {e}");
        }
    }

    // Best-effort UI sync. A failure here means the icon shows stale state
    // next paint, not that the window is stuck -- the disarm above already
    // happened.
    let _ = app.emit("click-through-disarmed", ());
}

/// Hide the overlay if it is showing; show and focus it if it is not.
///
/// `is_visible` failing reads as visible, so the fallback is to hide -- a
/// window that vanishes on a hotkey is a nuisance, a window that will not go
/// away when the trader wants their chart back is the one that gets
/// uninstalled.
fn toggle_overlay(app: &tauri::AppHandle) {
    let Some(window) = app.get_webview_window("main") else { return };
    let visible = window.is_visible().unwrap_or(true);
    let result = if visible {
        window.hide()
    } else {
        window.show().and_then(|()| window.set_focus())
    };
    // One line either way, same prefix discipline as `log_webview`: this is
    // the only evidence a hotkey pressed while MT5 had focus actually landed,
    // since nothing outside the process can see a borderless window toggle.
    match result {
        Ok(()) => eprintln!("[overlay] {}", if visible { "hidden" } else { "shown" }),
        Err(e) => eprintln!("[overlay] toggle failed (was visible: {visible}): {e}"),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            use tauri_plugin_global_shortcut::GlobalShortcutExt;

            // One handler per shortcut, bound at registration, so neither ever
            // has to work out which combo was pressed. The first version had
            // a single handler matching the pressed combo against
            // `Modifiers::SHIFT` alone -- omitting Cmd/Ctrl -- so `matches()`
            // never returned true and the disarm silently never fired. Found
            // on-device: registered without error, did nothing. Identity by
            // registration cannot make that mistake, and it is what lets a
            // second shortcut exist at all.
            app.global_shortcut().on_shortcut(DISARM_SHORTCUT, |app, _, event| {
                if event.state == ShortcutState::Pressed {
                    disarm_click_through(app);
                }
            })?;
            app.global_shortcut().on_shortcut(SUMMON_SHORTCUT, |app, _, event| {
                if event.state == ShortcutState::Pressed {
                    toggle_overlay(app);
                }
            })?;

            let Some(window) = app.get_webview_window("main") else {
                return Ok(());
            };
            let file = app
                .path()
                .app_config_dir()
                .map(|d| d.join(PLACEMENTS_FILE))
                .map_err(|e| format!("no app config dir: {e}"))?;

            // Restore before the window is shown, so a remembered position does
            // not read as the window jumping after paint.
            let monitors = monitors_of(&window);
            let saved = Placements::load(&file);
            if let Some(r) = saved.restore(&monitors) {
                let _ = window.set_position(tauri::PhysicalPosition::new(r.x, r.y));
                let _ = window.set_size(tauri::PhysicalSize::new(r.width, r.height));
            }

            // ⚠️ THE HANDLER BELOW MUST NOT CALL BACK INTO THE WINDOW, and that is
            // not a style preference. The first version of this asked the window
            // for `outer_position`, `outer_size` and `available_monitors` from
            // inside its own event callback. The window appeared, the terminal
            // kept focus so `Focused(false)` fired immediately, the handler
            // re-entered the window system on the main thread -- and the window
            // was gone about a second after launch, with the process still alive
            // and nothing on stderr. Reverting just this file to the previous
            // commit brought the window back, which is how it was pinned.
            //
            // So geometry comes from the EVENT PAYLOAD, which `Moved` and
            // `Resized` already carry, and the monitor list is read once here in
            // `setup` where the call is safe.
            let start = current_placement(&window);
            let state = Mutex::new((saved, monitors, start));

            window.on_window_event(move |event| {
                let Ok(mut st) = state.lock() else { return };
                let (placements, monitors, latest) = &mut *st;

                match event {
                    // Payload, not a query. Size is unchanged by a move and
                    // position by a resize, so each updates only its own half.
                    WindowEvent::Moved(pos) => {
                        if let Some(r) = latest.as_mut() {
                            r.x = pos.x;
                            r.y = pos.y;
                        }
                    }
                    WindowEvent::Resized(size) => {
                        if let Some(r) = latest.as_mut() {
                            r.width = size.width;
                            r.height = size.height;
                        }
                    }
                    // Leaving the app and closing it both end an arrangement's
                    // session, and between them they cover every ordinary way a
                    // trader stops moving the window.
                    WindowEvent::Focused(false) | WindowEvent::CloseRequested { .. } => {
                        let Some(r) = *latest else { return };
                        placements.remember(monitors, r);
                        if let Err(e) = placements.save(&file) {
                            // A window that cannot remember where it was is worth
                            // a line on stderr and nothing more; it is not worth
                            // refusing to close over.
                            eprintln!("[placement] could not save: {e}");
                        }
                    }
                    _ => {}
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            log_webview,
            creds::creds_save,
            creds::creds_load,
            creds::creds_clear
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
