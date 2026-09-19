/**
 * The popup: the desktop's Licence screen in miniature, plus the connection
 * and the three tier settings. It renders `chrome.storage`'s snapshot and
 * sends `messages.ts` requests; it holds no state the worker does not.
 */

import { useEffect, useReducer, useState } from "react";

import { KEY_PREFIX, reasonCopy, shortKey } from "@vision-hub/core";
import type { AlertTier } from "@vision-hub/contracts";

import { send } from "../messages";
import {
  BUILT_API_BASE,
  DEFAULTS,
  SITE_URL,
  apiBaseOf,
  read,
  watch,
  type Stored,
  type TierDisplay,
} from "../storage";

type Action = { type: "snapshot"; s: Stored } | { type: "draft"; v: string } | { type: "busy"; v: boolean };
interface State {
  s: Stored;
  draft: string;
  busy: boolean;
}

function reducer(st: State, a: Action): State {
  switch (a.type) {
    case "snapshot":
      return { ...st, s: a.s };
    case "draft":
      return { ...st, draft: a.v };
    case "busy":
      return { ...st, busy: a.v };
  }
}

const TIER_LABEL: Record<AlertTier, string> = {
  breaking: "Breaking",
  signal: "Signal",
  analysis: "Analysis",
};
const TIER_OPTIONS: Record<AlertTier, TierDisplay[]> = {
  breaking: ["banner", "list", "silent"],
  signal: ["badge", "list", "silent"],
  analysis: ["list", "silent"],
};

export function Popup() {
  const [st, dispatch] = useReducer(reducer, { s: DEFAULTS, draft: "", busy: false });
  const [apiDraft, setApiDraft] = useState<string | null>(null);

  useEffect(() => {
    void read().then((s) => dispatch({ type: "snapshot", s }));
    return watch((s) => dispatch({ type: "snapshot", s }));
  }, []);

  const { s, draft, busy } = st;
  const licence = s.licence;
  const apiBase = apiBaseOf(s);
  const overridden = !!s.apiBase && s.apiBase !== BUILT_API_BASE;
  const hasKey = licence.kind !== "unactivated";

  const run = async (fn: () => Promise<unknown>) => {
    dispatch({ type: "busy", v: true });
    try {
      await fn();
    } finally {
      dispatch({ type: "busy", v: false });
    }
  };

  return (
    <div className="vh popup stack">
      <div className="row">
        <span className="brand">Vision Hub</span>
        <span className="grow" />
        <LicencePill />
        <SocketPill status={s.socketStatus} />
      </div>

      <StateCard />

      {!apiBase && (
        <div className="notice error">
          This build has no API address, so the key cannot be checked. Set one under Settings.
        </div>
      )}
      {apiBase && overridden && (
        <div className="notice warn">Checking against {apiBase} -- a local override, not this build's server.</div>
      )}

      <div className="card stack">
        <div className="field">
          <label>{hasKey ? "Replace the key" : "Licence key"}</label>
          <input
            className="input mono"
            value={draft}
            placeholder={`${KEY_PREFIX}…`}
            spellCheck={false}
            autoComplete="off"
            onChange={(e) => dispatch({ type: "draft", v: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft.trim()) void run(() => send({ type: "licence.activate", key: draft }));
            }}
          />
        </div>
        <div className="row">
          <button
            className="btn primary"
            disabled={busy || !draft.trim() || !apiBase}
            onClick={() => run(() => send({ type: "licence.activate", key: draft })).then(() => dispatch({ type: "draft", v: "" }))}
          >
            Activate
          </button>
          {hasKey && (
            <>
              <button className="btn" disabled={busy} onClick={() => run(() => send({ type: "licence.recheck" }))}>
                Check again
              </button>
              <button className="btn ghost" disabled={busy} onClick={() => run(() => send({ type: "licence.deactivate" }))}>
                Remove key
              </button>
            </>
          )}
        </div>
        <p className="faint" style={{ margin: 0, fontSize: 11 }}>
          The key is kept in this extension's own storage, which pages cannot read. Re-checked every six hours.
        </p>
      </div>

      <div className="card stack">
        <span className="eyebrow">Alerts</span>
        {(Object.keys(TIER_LABEL) as AlertTier[]).map((tier) => (
          <div className="row" key={tier}>
            <span className="grow">{TIER_LABEL[tier]}</span>
            <select
              className="select"
              value={s.tierSettings[tier]}
              onChange={(e) =>
                void send({
                  type: "alerts.tiers",
                  tiers: { ...s.tierSettings, [tier]: e.target.value as TierDisplay },
                })
              }
            >
              {TIER_OPTIONS[tier].map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </div>
        ))}
        <p className="faint" style={{ margin: 0, fontSize: 11 }}>
          {s.alerts.length ? `${s.alerts.length} kept · last ${timeAgo(s.alerts[s.alerts.length - 1]!.created_at)}` : "No alerts received yet."}
        </p>
      </div>

      <div className="card stack">
        <span className="eyebrow">Settings</span>
        <div className="field">
          <label>API address {BUILT_API_BASE ? `(build: ${BUILT_API_BASE})` : "(none built in)"}</label>
          <div className="row">
            <input
              className="input mono grow"
              value={apiDraft ?? s.apiBase ?? ""}
              placeholder={BUILT_API_BASE ?? "https://api.example.com"}
              spellCheck={false}
              onChange={(e) => setApiDraft(e.target.value)}
            />
            <button
              className="btn sm"
              disabled={apiDraft === null}
              onClick={() => {
                void send({ type: "config.apiBase", apiBase: apiDraft });
                setApiDraft(null);
              }}
            >
              Save
            </button>
          </div>
        </div>
        {SITE_URL && (
          <a className="btn ghost" href={`${SITE_URL}/account`} target="_blank" rel="noreferrer">
            Open my account page
          </a>
        )}
      </div>
    </div>
  );

  function LicencePill() {
    const tone =
      licence.kind === "active" ? "ok" : licence.kind === "offline" ? "warn" : licence.kind === "checking" ? "sync" : licence.kind === "invalid" ? "bad" : "off";
    const label =
      licence.kind === "active" ? "Licensed" : licence.kind === "offline" ? "Offline" : licence.kind === "checking" ? "Checking" : licence.kind === "invalid" ? "Invalid" : "No key";
    return <span className={`pill ${tone}`}>{label}</span>;
  }

  function StateCard() {
    switch (licence.kind) {
      case "unactivated":
        return (
          <div className="card">
            <span className="eyebrow">No key</span>
            <p className="dim" style={{ margin: "4px 0 0" }}>
              Paste your licence key below. It is checked with Vision Hub and the panel on your chart unlocks.
            </p>
          </div>
        );
      case "checking":
        return (
          <div className="card">
            <span className="eyebrow">Checking</span>
            <p className="dim mono" style={{ margin: "4px 0 0" }}>{shortKey(licence.key)}</p>
          </div>
        );
      case "active":
        return (
          <div className="card">
            <span className="eyebrow">Licence active · {licence.tier === "core_journal" ? "Core + Journal" : "Core"}</span>
            <p className="dim" style={{ margin: "4px 0 0" }}>
              <span className="mono">{shortKey(licence.key)}</span> · checked {timeAgo(licence.checkedAt)}
              {licence.expiresAt ? ` · expires ${new Date(licence.expiresAt).toLocaleDateString()}` : ""}
            </p>
          </div>
        );
      case "offline":
        return (
          <div className="card">
            <span className="eyebrow">Offline</span>
            <p className="dim" style={{ margin: "4px 0 0" }}>
              Vision Hub could not be reached ({licence.error}). Running on the last good check, {timeAgo(licence.lastValidAt)}; seven days of grace.
            </p>
          </div>
        );
      case "invalid":
        return (
          <div className="card">
            <span className="eyebrow" style={{ color: "var(--red)" }}>
              Key {licence.reason}
            </span>
            <p className="dim" style={{ margin: "4px 0 0" }}>{reasonCopy[licence.reason]}</p>
          </div>
        );
    }
  }
}

function SocketPill({ status }: { status: Stored["socketStatus"] }) {
  const tone = status === "live" ? "ok" : status === "connecting" ? "sync" : status === "offline" ? "warn" : "off";
  const label = status === "live" ? "Live" : status === "connecting" ? "Connecting" : status === "offline" ? "Reconnecting" : "Not connected";
  return <span className={`pill ${tone}`}>{label}</span>;
}

export function timeAgo(t: number | string): string {
  const ms = Date.now() - (typeof t === "string" ? Date.parse(t) : t);
  const m = Math.round(ms / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
