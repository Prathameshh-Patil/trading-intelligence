# Vision Hub desktop

The overlay: a 380×820 borderless, always-on-top Tauri window over a trader's chart. React in
the webview, Rust for the keychain, hotkeys and click-through. Installing a built copy is
[`INSTALL.md`](INSTALL.md); this file is for running it from source.

## Run

```sh
cp .env.example .env          # VITE_API_BASE, VITE_SITE_URL
pnpm dev:desktop              # from the repo root; needs Rust
```

It opens on the Licence screen and needs `services/api` running at `VITE_API_BASE` to get past
it (root README, "Backend" and "Auth material"). `VITE_API_BASE=http://localhost:8000 pnpm dev`
runs the same UI as a plain page on `:1420`, with the key held in memory instead of the
keychain.

The two URLs are baked in by Vite. To point one build at another server without rebuilding,
`src/lib/config.ts` reads a `localStorage` override:

```js
localStorage.setItem("vh.apiBase", "http://localhost:8000"); location.reload();
```

## Build installers

Locally, for the current machine:

```sh
pnpm tauri build --target aarch64-apple-darwin   # or x86_64-apple-darwin, x86_64-pc-windows-msvc
# -> src-tauri/target/<target>/release/bundle/{dmg,macos,nsis}/
```

For a release, `.github/workflows/release.yml`: push a tag `desktop-v<version>` (URLs from the
`DESKTOP_API_BASE` / `DESKTOP_SITE_URL` repo variables) or run the workflow by hand with the
URLs as inputs. It builds Apple silicon, Intel and Windows, signs the updater artifacts, and
uploads everything to a **draft** GitHub Release for a human to publish. The workflow's header
comment lists every secret and what happens without each one. The version comes from
`src-tauri/tauri.conf.json`; bump it before tagging.

## Signing

- **Updater** (`.sig` + `latest.json`): the public key is in `tauri.conf.json`; the private
  key lives outside the repo (`~/.tauri/visionhub.key` on the machine that generated it) and in
  the `TAURI_SIGNING_PRIVATE_KEY` secret. Lose it and every installed app stops seeing updates —
  back it up.
- **macOS**: unsigned until the Apple Developer account exists; then the six `APPLE_*` secrets
  turn on Developer ID signing and notarization with no workflow change.
- **Windows**: unsigned by decision until ~50 users.

## Tests

`cargo test` in `src-tauri` round-trips the real OS keychain and restores what was there, so
it is run on a developer machine and not in CI. The TypeScript half is `tsc && vite build`,
which CI's `web` job runs.
