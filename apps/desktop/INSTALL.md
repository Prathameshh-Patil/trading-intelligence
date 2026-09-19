# Installing Vision Hub

Installers are on the [releases page](https://github.com/Prathameshh-Patil/trading-intelligence/releases/latest).
Pick the one for your machine.

## macOS

- Apple silicon (M1 and later): `Vision.Hub_<version>_aarch64.dmg`
- Intel: `Vision.Hub_<version>_x64.dmg`

Open the `.dmg` and drag **Vision Hub** to Applications.

**If macOS says the app is damaged and should be moved to the Trash**, the build is not
notarized yet. Right-click the app in Applications → **Open** → **Open**. macOS asks once; after
that it launches normally. Notarized builds open silently — a build's release notes say which
it is.

## Windows

`Vision.Hub_<version>_x64-setup.exe`. It installs for your user only and needs no
administrator.

**Windows will say "Windows protected your PC".** Click **More info**, then **Run anyway**. The
installer is not code-signed yet: a signing certificate is bought once the first fifty traders
are on, and until then this warning is what every unsigned installer gets. It is not a fault in
the download. If you want to check the file, its SHA-256 is on the release page.

## First run

The app opens on its **Licence** screen. Paste the `vh_live_…` key from your account page
(**Open my account page** on that screen takes you there). The key is checked with Vision Hub,
stored in your operating system's keychain — not in a file — and re-checked every six hours.

- **Licensed** in the top bar: all good.
- **Offline**: Vision Hub could not be reached. The app keeps working for seven days on the
  last successful check, then locks until it can reach the server again.
- **Revoked / expired**: the key was rotated or the account changed. Your account page has the
  current key.

## What this build contains

The order-flow engine in this release replays a recorded GC session (2026-07-16) at 10× — the
layout, the states and the forecast table are real; the ticks are not live. Connecting your own
feed is done with you on the onboarding call.

## Where things are

- Keychain entries: `com.visionhub.desktop.licence` and `com.visionhub.desktop.feed`. Removing
  them signs the app out; nothing else on disk holds a secret.
- There is no log file yet. If something goes wrong, launch the app from a terminal
  (`/Applications/Vision\ Hub.app/Contents/MacOS/desktop` on macOS) and copy what it prints —
  webview errors are mirrored there as `[webview:*]` lines.

## Uninstall

macOS: drag the app to the Trash, then remove the two keychain entries in Keychain Access if you
want them gone. Windows: Settings → Apps → Vision Hub → Uninstall.
