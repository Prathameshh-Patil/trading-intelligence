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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![log_webview])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
