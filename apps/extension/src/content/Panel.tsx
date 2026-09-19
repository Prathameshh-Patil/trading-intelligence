/**
 * The panel that floats over the chart.
 *
 * The same gate as the desktop: unless the licence is `active` or `offline`,
 * it shows one sentence pointing at the popup and nothing else. Unlocked, it
 * shows the chart the trader synced (client-side only -- see `sites/index.ts`)
 * and the alerts, each tier the way the trader's settings say.
 *
 * State comes from `chrome.storage` and nowhere else; the panel writes back
 * only its own position and "I have read the signals".
 */

import { useEffect, useMemo, useReducer, useRef, useState } from "react";

import type { Alert } from "@vision-hub/contracts";
import { unlocked } from "@vision-hub/core";

import { send } from "../messages";
import { DEFAULTS, read, watch, type PanelPos, type Stored } from "../storage";
import { clamp, draggable, type Point } from "./drag";
import { adapterFor, readChart, type ChartRead } from "./sites";

const BANNER_MS = 60_000;
const LIST_MAX = 20;

type Action =
  | { type: "snapshot"; s: Stored }
  | { type: "pos"; p: Point }
  | { type: "collapsed"; v: boolean }
  | { type: "chart"; c: ChartRead | null; failed: boolean }
  | { type: "manual"; v: string }
  | { type: "dismiss"; id: number }
  | { type: "open"; v: boolean };

interface State {
  s: Stored;
  pos: Point;
  collapsed: boolean;
  chart: ChartRead | null;
  chartFailed: boolean;
  manual: string;
  dismissed: Set<number>;
  listOpen: boolean;
}

function reducer(st: State, a: Action): State {
  switch (a.type) {
    case "snapshot":
      return { ...st, s: a.s };
    case "pos":
      return { ...st, pos: a.p };
    case "collapsed":
      return { ...st, collapsed: a.v };
    case "chart":
      return { ...st, chart: a.c, chartFailed: a.failed };
    case "manual":
      return { ...st, manual: a.v };
    case "dismiss":
      return { ...st, dismissed: new Set(st.dismissed).add(a.id) };
    case "open":
      return { ...st, listOpen: a.v };
  }
}

// `data-vh-host` lets the dev harness stand in for a real site. A page that
// sets it on itself only picks which read-only adapter runs against it.
const HOST = document.documentElement.dataset.vhHost ?? location.host;

export function Panel({ initial }: { initial: PanelPos | undefined }) {
  const [st, dispatch] = useReducer(reducer, {
    s: DEFAULTS,
    pos: initial ? { x: initial.x, y: initial.y } : { x: Math.max(12, window.innerWidth - 392), y: 72 },
    collapsed: initial?.collapsed ?? false,
    chart: null,
    chartFailed: false,
    manual: "",
    dismissed: new Set<number>(),
    listOpen: false,
  });
  const [now, setNow] = useState(Date.now());
  const panelRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const posRef = useRef(st.pos);
  posRef.current = st.pos;

  useEffect(() => {
    void read().then((s) => dispatch({ type: "snapshot", s }));
    return watch((s) => dispatch({ type: "snapshot", s }));
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!headRef.current || !panelRef.current) return;
    return draggable(
      headRef.current,
      panelRef.current,
      () => posRef.current,
      (p) => dispatch({ type: "pos", p }),
      (p) => void send({ type: "panel.save", host: HOST, pos: { ...p, collapsed: st.collapsed } }),
    );
  }, [st.collapsed]);

  useEffect(() => {
    const onResize = () => {
      if (panelRef.current) dispatch({ type: "pos", p: clamp(posRef.current, panelRef.current) });
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const { s, pos, collapsed, chart, chartFailed, manual, dismissed, listOpen } = st;
  const open = unlocked(s.licence);
  const adapter = useMemo(() => adapterFor(HOST), []);

  const banners = s.alerts.filter(
    (a) =>
      a.tier === "breaking" &&
      s.tierSettings.breaking === "banner" &&
      !dismissed.has(a.id) &&
      now - Date.parse(a.created_at) < BANNER_MS,
  );
  const listed = s.alerts
    .filter((a) => {
      const mode = s.tierSettings[a.tier];
      if (mode === "silent") return false;
      if (a.tier === "breaking") return mode === "list" || dismissed.has(a.id) || now - Date.parse(a.created_at) >= BANNER_MS;
      return true;
    })
    .slice(-LIST_MAX)
    .reverse();

  const toggleCollapsed = () => {
    const v = !collapsed;
    dispatch({ type: "collapsed", v });
    void send({ type: "panel.save", host: HOST, pos: { ...pos, collapsed: v } });
  };
  const openList = () => {
    dispatch({ type: "open", v: !listOpen });
    if (!listOpen && s.unreadSignals) void send({ type: "alerts.markRead" });
  };

  return (
    <div
      ref={panelRef}
      className={`vh panel${collapsed ? " collapsed" : ""}`}
      style={{ left: pos.x, top: pos.y }}
      role="dialog"
      aria-label="Vision Hub"
    >
      <div ref={headRef} className="panel-head">
        <span className="brand">Vision Hub</span>
        {open && s.unreadSignals > 0 && s.tierSettings.signal === "badge" && (
          <span className="badge" title={`${s.unreadSignals} new signals`}>{s.unreadSignals}</span>
        )}
        <span className="grow" />
        <LicenceDot kind={s.licence.kind} socket={s.socketStatus} />
        <button className="btn ghost sm" onClick={toggleCollapsed} aria-label={collapsed ? "Expand" : "Collapse"}>
          {collapsed ? "▸" : "▾"}
        </button>
      </div>

      {!collapsed && (
        <div className="panel-body">
          {!open ? (
            <div className="card">
              <span className="eyebrow">Licence</span>
              <p className="dim" style={{ margin: "4px 0 0" }}>
                {s.licence.kind === "checking"
                  ? "Checking your key…"
                  : s.licence.kind === "invalid"
                    ? `Your key is ${s.licence.reason}. Fix it in the Vision Hub popup.`
                    : "Add your key in the Vision Hub popup (the toolbar icon) to unlock this panel."}
              </p>
            </div>
          ) : (
            <>
              {banners.map((a) => (
                <div className="banner" key={a.id}>
                  <div className="row">
                    <span className="title grow truncate">{a.title}</span>
                    <button className="btn ghost sm" onClick={() => dispatch({ type: "dismiss", id: a.id })} aria-label="Dismiss">
                      ×
                    </button>
                  </div>
                  <div style={{ marginTop: 4 }}>{a.body}</div>
                  <div className="meta faint" style={{ marginTop: 4, fontSize: 11 }}>
                    {a.symbol ? `${a.symbol} · ` : ""}breaking · {ago(a.created_at, now)}
                  </div>
                </div>
              ))}

              <div className="card stack">
                <div className="row">
                  <span className="eyebrow grow">Chart · {adapter?.name ?? HOST}</span>
                  <button
                    className="btn sm"
                    onClick={() => {
                      const c = readChart(HOST, document);
                      dispatch({ type: "chart", c, failed: c === null });
                    }}
                  >
                    Sync chart
                  </button>
                </div>
                {chart ? (
                  <div>
                    <div className="row">
                      <span className="chart-v">{chart.symbol}</span>
                      {chart.timeframe && <span className="pill off">{chart.timeframe}</span>}
                    </div>
                    <div className="dim mono">{chart.lastPrice ? `last ${chart.lastPrice}` : "price not shown on this page"}</div>
                    <div className="faint" style={{ fontSize: 11, marginTop: 4 }}>Read from this page, on your click. It stays here.</div>
                  </div>
                ) : chartFailed || manual ? (
                  <div className="field">
                    <label>Could not read the chart -- type the symbol</label>
                    <input
                      className="input mono"
                      value={manual}
                      placeholder="XAUUSD"
                      onChange={(e) => dispatch({ type: "manual", v: e.target.value.toUpperCase() })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && manual.trim())
                          dispatch({ type: "chart", c: { symbol: manual.trim(), timeframe: null, lastPrice: null }, failed: false });
                      }}
                    />
                  </div>
                ) : (
                  <div className="empty">Press Sync chart to read the symbol, timeframe and last price from this page.</div>
                )}
              </div>

              <div className="card stack">
                <div className="row">
                  <span className="eyebrow grow">Alerts</span>
                  <button className="btn ghost sm" onClick={openList}>
                    {listOpen ? "Hide" : `Show${s.unreadSignals ? ` (${s.unreadSignals} new)` : ""}`}
                  </button>
                </div>
                {listOpen &&
                  (listed.length ? (
                    listed.map((a) => <AlertRow key={a.id} a={a} now={now} />)
                  ) : (
                    <div className="empty">Nothing yet. Alerts arrive here as they are published.</div>
                  ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function AlertRow({ a, now }: { a: Alert; now: number }) {
  return (
    <div className={`alert ${a.tier}`}>
      <div className="row">
        <span className="title grow truncate">{a.title}</span>
        <span className="pill off">{a.tier}</span>
      </div>
      <div className="dim" style={{ marginTop: 2 }}>{a.body}</div>
      <div className="meta">
        {a.symbol ? `${a.symbol} · ` : ""}
        {ago(a.created_at, now)}
      </div>
    </div>
  );
}

function LicenceDot({ kind, socket }: { kind: Stored["licence"]["kind"]; socket: Stored["socketStatus"] }) {
  const tone = kind === "active" ? (socket === "live" ? "ok" : "warn") : kind === "offline" ? "warn" : kind === "checking" ? "sync" : "off";
  const label = kind === "active" ? (socket === "live" ? "Live" : socket === "connecting" ? "Connecting" : "Licensed") : kind === "offline" ? "Offline" : kind === "checking" ? "Checking" : "Locked";
  return <span className={`pill ${tone}`}>{label}</span>;
}

function ago(iso: string, now: number): string {
  const m = Math.round((now - Date.parse(iso)) / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}
