/**
 * Feed credentials — W3D1's other half, as a card in the Order Flow view.
 *
 * A vendor name and a list of `field = value` rows, because that is exactly
 * what `FeedCreds` is (`{ vendor; [field]: string }`) and no more. The rows
 * have no labels of their own on purpose: which fields Ironbeam wants is
 * unknown until the account (`plans/current.md` #9) exists, and a form that
 * printed "API key" and "Secret" today would be freezing a guess. When the
 * fields are known this card gains labels; nothing underneath it changes.
 *
 * Values go to `lib/creds.ts` → Rust → the OS keychain, and then to
 * `reconnect()`. They are never echoed back into the DOM after save: the
 * fields load in as `••••` placeholders so a screenshot of this panel — the
 * thing this whole app takes — never contains a credential.
 */

import { useEffect, useState } from "react";

import { clearFeedCreds, lastVendor, loadFeedCreds, PERSISTENT, saveFeedCreds } from "../lib/creds";
import { reconnect } from "../lib/feed";
import type { FeedCreds } from "../lib/engine/types";

interface Row {
  key: string;
  value: string;
}

const MASK = "••••••••";

export default function FeedCredsCard() {
  const [vendor, setVendor] = useState("");
  const [rows, setRows] = useState<Row[]>([{ key: "", value: "" }]);
  const [saved, setSaved] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  // On mount, learn what is stored -- field names only, values masked.
  useEffect(() => {
    const v = lastVendor();
    if (!v) return;
    setVendor(v);
    void loadFeedCreds(v)
      .then((c) => {
        if (!c) return;
        const keys = Object.keys(c).filter((k) => k !== "vendor");
        setSaved(keys);
        setRows(keys.length ? keys.map((k) => ({ key: k, value: "" })) : [{ key: "", value: "" }]);
      })
      .catch((e: unknown) => setNote(e instanceof Error ? e.message : String(e)));
  }, []);

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const save = async () => {
    const v = vendor.trim();
    if (!v) {
      setNote("Give the vendor a name first.");
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      // A row left masked keeps its stored value; a typed row replaces it.
      const existing = saved ? await loadFeedCreds(v) : null;
      const creds: FeedCreds = { vendor: v };
      for (const r of rows) {
        const k = r.key.trim();
        if (!k) continue;
        if (r.value !== "") creds[k] = r.value;
        else if (existing && typeof existing[k] === "string") creds[k] = existing[k];
      }
      await saveFeedCreds(creds);
      await reconnect(creds);
      const keys = Object.keys(creds).filter((k) => k !== "vendor");
      setSaved(keys);
      setRows(keys.length ? keys.map((k) => ({ key: k, value: "" })) : [{ key: "", value: "" }]);
      setNote(
        PERSISTENT
          ? `Saved to the OS keychain as com.visionhub.desktop.feed / ${v}, and connecting.`
          : `Kept in memory for this page only — no Tauri runtime, so nothing is persisted. Connecting.`,
      );
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    const v = vendor.trim();
    if (!v) return;
    setBusy(true);
    setNote(null);
    try {
      await clearFeedCreds(v);
      setSaved(null);
      setRows([{ key: "", value: "" }]);
      setNote(`Removed ${v} from the keychain. The feed stays as it is until you reconnect.`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card pad-lg stack">
      <div className="between">
        <span className="eyebrow">Feed credentials</span>
        <span className="context-tf">{PERSISTENT ? "OS keychain" : "not persisted"}</span>
      </div>

      <div className="field">
        <label>Vendor</label>
        <input
          className="input"
          value={vendor}
          placeholder="ironbeam"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          onChange={(e) => setVendor(e.target.value)}
        />
      </div>

      {rows.map((r, i) => (
        <div className="row" style={{ gap: 8 }} key={i}>
          <input
            className="input"
            style={{ flex: 1 }}
            value={r.key}
            placeholder="field"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            onChange={(e) => setRow(i, { key: e.target.value })}
          />
          <input
            className="input"
            style={{ flex: 1.4 }}
            type="password"
            value={r.value}
            placeholder={saved?.includes(r.key) ? MASK : "value"}
            autoComplete="off"
            onChange={(e) => setRow(i, { value: e.target.value })}
          />
          <button
            className="btn ghost sm"
            aria-label="Remove field"
            onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((_, j) => j !== i) : rs))}
          >
            ×
          </button>
        </div>
      ))}

      <button className="btn ghost sm" onClick={() => setRows((rs) => [...rs, { key: "", value: "" }])}>
        + field
      </button>

      <div className="row" style={{ gap: 8 }}>
        <button className="btn" style={{ flex: 1 }} disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save & connect"}
        </button>
        <button className="btn ghost" disabled={busy || !saved} onClick={clear}>
          Clear
        </button>
      </div>

      {note && <div className="mock-note">{note}</div>}

      <div className="mock-note">
        Field names are up to you until the vendor is settled — `FeedCreds` is
        an open map by design. Values never come back into this panel after
        saving; a masked field keeps what is stored.
      </div>
    </div>
  );
}
