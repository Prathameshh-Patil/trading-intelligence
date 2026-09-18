//! The licence key, in the OS keychain and nowhere else.
//!
//! The same shape as `creds.rs`, for the same reason: a `vh_live_` key is a
//! credential -- anyone holding it validates as this trader -- so it gets
//! the treatment W3D1 gives the feed password. Three commands, one keychain
//! entry, and JavaScript never writes the secret to anything that persists.
//!
//! One entry, fixed account name. There is exactly one key per install --
//! S5 issues one active key per account -- so unlike `creds.rs` there is
//! nothing to index by.

use keyring::Entry;

/// The keychain "service", so a trader looking in Keychain Access sees
/// exactly what we hold and under whose name.
const SERVICE: &str = "com.visionhub.desktop.licence";
const ACCOUNT: &str = "licence-key";

fn entry() -> Result<Entry, String> {
    Entry::new(SERVICE, ACCOUNT).map_err(|e| format!("keychain unavailable: {e}"))
}

/// Store `key`, replacing any previous one. An empty key is refused rather
/// than stored: "no key" is `licence_clear`, and a blank secret in the
/// keychain would read as a key on the next launch.
#[tauri::command]
pub fn licence_save(key: &str) -> Result<(), String> {
    if key.trim().is_empty() {
        return Err("key must not be empty".into());
    }
    entry()?
        .set_password(key.trim())
        .map_err(|e| format!("keychain write failed: {e}"))
}

/// The stored key, or `None` if nothing is stored.
#[tauri::command]
pub fn licence_load() -> Result<Option<String>, String> {
    match entry()?.get_password() {
        Ok(key) => Ok(Some(key)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(format!("keychain read failed: {e}")),
    }
}

/// Remove the stored key. Removing nothing is not an error.
#[tauri::command]
pub fn licence_clear() -> Result<(), String> {
    match entry()?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(format!("keychain delete failed: {e}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Round-trips through the real keychain, as `creds.rs` does. The entry
    /// is the app's one licence slot, so the test restores whatever was
    /// there before it ran -- a developer's own key must survive `cargo test`.
    #[test]
    fn save_load_clear_round_trip() {
        let before = licence_load().unwrap();

        licence_save("vh_live_abcdefghijklmnopqrstuvwxyz012345").unwrap();
        assert_eq!(
            licence_load().unwrap().as_deref(),
            Some("vh_live_abcdefghijklmnopqrstuvwxyz012345")
        );

        // Replacing works, and whitespace around a pasted key is not stored.
        licence_save("  vh_live_second  ").unwrap();
        assert_eq!(licence_load().unwrap().as_deref(), Some("vh_live_second"));

        licence_clear().unwrap();
        assert_eq!(licence_load().unwrap(), None);
        licence_clear().unwrap();

        if let Some(k) = before {
            licence_save(&k).unwrap();
        }
    }

    #[test]
    fn empty_key_is_refused() {
        assert!(licence_save("").is_err());
        assert!(licence_save("   ").is_err());
    }
}
