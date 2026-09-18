//! Feed credentials, in the OS keychain and nowhere else.
//!
//! W3D1 (`plans/team/prathamesh/README.md`): *"Credentials to the OS
//! keychain; never plaintext on disk, never to our servers."* This module is
//! the whole of that sentence on the Rust side. Three commands, one keychain
//! entry per vendor, the fields serialised as JSON in the entry's secret.
//!
//! ## Why one entry per vendor and not one per field
//!
//! `keyring` can set, get and delete an entry by `(service, account)`; it
//! cannot list entries. A field-per-entry layout would need a separate index
//! of which fields exist -- and an index of credential field names on disk is
//! plaintext about the credentials, which is the thing this exists to avoid.
//! One JSON blob under the vendor's name needs no index.
//!
//! ## What this module does not know
//!
//! Which fields a vendor has. `FeedCreds` in `engine/types.ts` is
//! deliberately `{ vendor; [field]: string }` until the Ironbeam account
//! (`plans/current.md` #9) exists and its fields are known, and this module
//! stores whatever map it is given. The shape is the UI's to firm up later;
//! storage does not care.
//!
//! ## Native backends only
//!
//! `Cargo.toml` enables `apple-native`, `windows-native` and
//! `sync-secret-service`, and none of the crate's file-based fallbacks. If
//! the platform has no keychain, `Entry::new` or `set_password` fails and the
//! frontend shows that rather than quietly writing a file.

use keyring::Entry;

/// The keychain "service". Every entry this app writes is under this name,
/// so a trader looking in Keychain Access sees exactly what we hold.
// Renamed from `trading-intelligence.feed` with the Vision Hub rebrand. An
// entry saved under the old name is not migrated: the form asks for the
// credentials again, which is one paste, and a migration that copies a
// secret between keychain entries is code that handles a secret for no
// gain.
const SERVICE: &str = "com.visionhub.desktop.feed";

fn entry(vendor: &str) -> Result<Entry, String> {
    if vendor.trim().is_empty() {
        return Err("vendor must not be empty".into());
    }
    Entry::new(SERVICE, vendor).map_err(|e| format!("keychain unavailable: {e}"))
}

/// Store `fields_json` as the secret for `vendor`, replacing any previous one.
#[tauri::command]
pub fn creds_save(vendor: &str, fields_json: &str) -> Result<(), String> {
    entry(vendor)?
        .set_password(fields_json)
        .map_err(|e| format!("keychain write failed: {e}"))
}

/// The stored fields for `vendor`, or `None` if nothing is stored.
#[tauri::command]
pub fn creds_load(vendor: &str) -> Result<Option<String>, String> {
    match entry(vendor)?.get_password() {
        Ok(json) => Ok(Some(json)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(format!("keychain read failed: {e}")),
    }
}

/// Remove the stored fields for `vendor`. Removing nothing is not an error.
#[tauri::command]
pub fn creds_clear(vendor: &str) -> Result<(), String> {
    match entry(vendor)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(format!("keychain delete failed: {e}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Round-trips through the real keychain of whatever machine runs the
    /// suite. The item is created and deleted by the same binary, which on
    /// macOS is the case that does not prompt.
    #[test]
    fn save_load_clear_round_trip() {
        let vendor = format!("test-{}", std::process::id());
        assert_eq!(creds_load(&vendor).unwrap(), None);

        creds_save(&vendor, r#"{"apiKey":"k","secret":"s"}"#).unwrap();
        assert_eq!(
            creds_load(&vendor).unwrap().as_deref(),
            Some(r#"{"apiKey":"k","secret":"s"}"#)
        );

        creds_save(&vendor, r#"{"apiKey":"k2"}"#).unwrap();
        assert_eq!(creds_load(&vendor).unwrap().as_deref(), Some(r#"{"apiKey":"k2"}"#));

        creds_clear(&vendor).unwrap();
        assert_eq!(creds_load(&vendor).unwrap(), None);
        // Clearing twice is fine.
        creds_clear(&vendor).unwrap();
    }

    #[test]
    fn empty_vendor_is_refused() {
        assert!(creds_save("  ", "{}").is_err());
        assert!(creds_load("").is_err());
    }
}
