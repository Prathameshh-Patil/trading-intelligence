/**
 * The licence screen -- paste the key, and see what the server made of it.
 *
 * This is the only view an unactivated app shows. It says, in order: what
 * state the licence is in and why; the field to paste into; where a key
 * comes from. The reason strings are S3's own (`expired`, `revoked`,
 * `unknown`) plus one of ours (`malformed`) for a paste that is not even
 * the right shape -- that one never reaches the network.
 *
 * The key is never echoed back after activation: the state card shows
 * `vh_live_ab…yz`, enough to recognise, not enough to copy from a
 * screenshot of the panel -- and a screenshot of the panel is the thing
 * this app takes.
 */

import { motion } from "framer-motion";
import { useState } from "react";

import {
  activate,
  API_BASE,
  deactivate,
  KEY_PREFIX,
  PERSISTENT,
  reasonCopy,
  recheck,
  shortKey,
  useLicence,
  type LicenceState,
} from "../lib/licence";
import { SITE_URL, overridden } from "../lib/config";
import { riseIn, stagger } from "../ui/motion";

const ACCOUNT_URL = SITE_URL ? `${SITE_URL}/account` : null;



function StateCard({ s }: { s: LicenceState }) {
  switch (s.kind) {
    case "unactivated":
      return (
        <div className="card pad-lg stack">
          <span className="eyebrow">No key</span>
          <p className="lede">
            Paste your licence key below. The app validates it with Vision Hub and unlocks; the
            key is kept in the {PERSISTENT ? "OS keychain" : "page's memory (no Tauri runtime)"} and
            nowhere else.
          </p>
        </div>
      );
    case "checking":
      return (
        <div className="card pad-lg stack feed-sync">
          <div className="row" style={{ gap: 8 }}>
            <span className="feed-dot" />
            <span className="feed-state">Checking…</span>
            <span className="feed-vendor">{shortKey(s.key)}</span>
          </div>
        </div>
      );
    case "active":
      return (
        <div className="card pad-lg stack feed-ok">
          <div className="row" style={{ gap: 8 }}>
            <span className="feed-dot" />
            <span className="feed-state">Active · {s.tier === "core_journal" ? "Core + Journal" : "Core"}</span>
            <span className="feed-vendor">{shortKey(s.key)}</span>
          </div>
          <p className="lede">
            Checked {new Date(s.checkedAt).toLocaleTimeString()}
            {s.expiresAt ? ` · expires ${new Date(s.expiresAt).toLocaleDateString()}` : " · no expiry"}.
            Re-checked every six hours while the app runs.
          </p>
        </div>
      );
    case "offline":
      return (
        <div className="card pad-lg stack feed-warn">
          <div className="row" style={{ gap: 8 }}>
            <span className="feed-dot" />
            <span className="feed-state">Offline</span>
            <span className="feed-vendor">{shortKey(s.key)}</span>
          </div>
          <p className="lede">
            Vision Hub could not be reached ({s.error}). The key was valid{" "}
            {s.lastValidAt ? new Date(s.lastValidAt).toLocaleString() : "before"}, so the app keeps
            working for up to seven days from then.
          </p>
        </div>
      );
    case "invalid":
      return (
        <div className="card pad-lg stack feed-bad">
          <div className="row" style={{ gap: 8 }}>
            <span className="feed-dot" />
            <span className="feed-state">Not valid · {s.reason}</span>
            <span className="feed-vendor">{shortKey(s.key)}</span>
          </div>
          <p className="lede">{reasonCopy[s.reason]}</p>
        </div>
      );
  }
}

export default function LicenceView() {
  const licence = useLicence();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const hasKey = licence.kind !== "unactivated";

  const submit = async () => {
    if (!draft.trim()) return;
    setBusy(true);
    setNote(null);
    try {
      const next = await activate(draft);
      if (next.kind === "active") {
        setDraft("");
        setNote("Activated. Your account page will show the app has checked in.");
      }
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setNote(null);
    try {
      await deactivate();
      setNote("Key removed. The app is locked until a key is pasted.");
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const again = async () => {
    setBusy(true);
    setNote(null);
    try {
      await recheck();
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div className="view" variants={stagger} initial="hidden" animate="show">
      <motion.div variants={riseIn}>
        <h2>Licence</h2>
        <p className="lede">One key, one person. It is what connects your account to this window.</p>
      </motion.div>

      <motion.div variants={riseIn}>
        <StateCard s={licence} />
      </motion.div>

      {!API_BASE && (
        <motion.div variants={riseIn} className="notice error">
          This build has no API address, so the key cannot be checked. It cannot activate.
        </motion.div>
      )}

      {API_BASE && overridden() && (
        <motion.div variants={riseIn} className="notice warn">
          Checking against {API_BASE} -- a local override, not this build's server.
        </motion.div>
      )}

      <motion.div variants={riseIn} className="card pad-lg stack">
        <div className="field">
          <label>{hasKey ? "Replace the key" : "Licence key"}</label>
          <input
            className="input"
            value={draft}
            placeholder={`${KEY_PREFIX}…`}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submit();
            }}
          />
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" disabled={busy || !draft.trim()} onClick={() => void submit()}>
            {busy ? "Checking…" : "Activate"}
          </button>
          {hasKey && (
            <button className="btn ghost" disabled={busy} onClick={() => void again()}>
              Check again
            </button>
          )}
          {hasKey && (
            <button className="btn danger" disabled={busy} onClick={() => void remove()}>
              Remove key
            </button>
          )}
        </div>
        {note && <div className="notice warn">{note}</div>}
      </motion.div>

      <motion.div variants={riseIn} className="card pad-lg stack">
        <span className="eyebrow">Where a key comes from</span>
        <p className="lede">
          Sign in at Vision Hub and open your account page. Once one of us has approved the
          account, the key is shown there and can be rotated from there.
        </p>
        {ACCOUNT_URL && (
          <a className="btn ghost" href={ACCOUNT_URL} target="_blank" rel="noreferrer">
            Open my account page
          </a>
        )}
      </motion.div>
    </motion.div>
  );
}
