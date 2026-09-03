/**
 * Order flow — the first surface built against S2's engine seam (W1D2).
 *
 * Its job this week is not to be a finished design. It is to be **the layout
 * that the mock's four failure modes are aimed at**, so that a 7-digit CVD or a
 * 40-character vendor breaks something on a Sunday in Week 1 rather than in
 * Week 3 against a live feed.
 *
 * Everything rendered here comes from `Engine`, never from capture — the S6
 * comment in `engine/types.ts` is the reason: capture produces context, capture
 * never produces a number that appears in a signal.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { getEngine, getMockControls } from "../lib/engine";
import { unsignedVolume } from "../lib/engine/mock";
import type { DeltaBar, FeedStatus, Outlier } from "../lib/engine/types";

const STATE_COPY: Record<FeedStatus["state"], { label: string; tone: string }> = {
  live: { label: "Live", tone: "ok" },
  connecting: { label: "Connecting", tone: "warn" },
  // The state S2 calls out as easy to get wrong: connected but not receiving,
  // which looks exactly like a quiet market and is not one.
  stale: { label: "Stale — no ticks", tone: "warn" },
  disconnected: { label: "Disconnected", tone: "bad" },
};

const KIND_COPY: Record<Outlier["kind"], string> = {
  absorption: "Absorption",
  trapped: "Trapped",
  cluster: "Cluster",
};

const fmt = (n: number) => n.toLocaleString("en-US");
const signed = (n: number) => `${n > 0 ? "+" : ""}${fmt(n)}`;

const clock = (t: number) =>
  new Date(t).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/New_York",
  });

export default function FlowView() {
  const engine = useMemo(() => getEngine(), []);
  const controls = useMemo(() => getMockControls(), []);

  const [status, setStatus] = useState<FeedStatus | null>(null);
  const [bar, setBar] = useState<DeltaBar | null>(null);
  const [outliers, setOutliers] = useState<Outlier[]>([]);
  const [symbol, setSymbol] = useState("GC");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const offBar = engine.onBar(setBar);
    const offStatus = engine.onStatus(setStatus);
    const offOutlier = engine.onOutlier((o) =>
      setOutliers((prev) => [o, ...prev].slice(0, 8)),
    );

    engine
      .connect({ vendor: "mock" })
      .then(setStatus)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));

    return () => {
      offBar();
      offStatus();
      offOutlier();
    };
  }, [engine]);

  const state = status?.state ?? "disconnected";
  const copy = STATE_COPY[state];

  // contracts.md's pending 'N' amendment: any consumer reporting delta must
  // report the unsigned share beside it. No contract change was needed —
  // `volume` counts every trade while the two legs count only attributed ones.
  const unsigned = bar ? unsignedVolume(bar) : 0;
  const unsignedPct = bar && bar.volume ? (100 * unsigned) / bar.volume : 0;

  const longSymbol = () => {
    const long = "GC-CONTINUOUS-FRONT-MONTH-ADJUSTED-XX".padEnd(40, "X").slice(0, 40);
    setSymbol(long);
    void engine.setContext({
      symbol: long,
      timeframe: "1m",
      levels: [],
      confidence: 0,
      capturedAt: Date.now(),
    });
    controls?.emitLongVendor();
  };

  return (
    <div className="view">
      <div className="eyebrow">ORDER FLOW</div>

      <div className={`feed-row feed-${copy.tone}`}>
        <span className="feed-dot" />
        <span className="feed-state">{copy.label}</span>
        <span className="feed-vendor" title={status?.vendor ?? ""}>
          {status?.vendor ?? "—"}
        </span>
      </div>

      <div className="feed-meta">
        <span>{symbol}</span>
        <span>·</span>
        <span>1m</span>
        <span>·</span>
        <span>{status?.gapCount ?? 0} gaps</span>
        <span>·</span>
        <span>{status?.lastTickAt ? clock(status.lastTickAt) : "no ticks"} ET</span>
      </div>

      {error && <div className="feed-error">{error}</div>}

      <motion.div className="cvd-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div className="cvd-label">SESSION CVD</div>
        <div className={`cvd-value ${(bar?.cvd ?? 0) >= 0 ? "pos" : "neg"}`}>
          {bar ? signed(bar.cvd) : "—"}
        </div>
        <div className="cvd-sub">
          bar delta {bar ? signed(bar.delta) : "—"}
        </div>
      </motion.div>

      <div className="flow-grid">
        <div className="flow-cell">
          <div className="flow-k">ASK VOL</div>
          <div className="flow-v pos">{bar ? fmt(bar.askVol) : "—"}</div>
        </div>
        <div className="flow-cell">
          <div className="flow-k">BID VOL</div>
          <div className="flow-v neg">{bar ? fmt(bar.bidVol) : "—"}</div>
        </div>
        <div className="flow-cell">
          <div className="flow-k">VOLUME</div>
          <div className="flow-v">{bar ? fmt(bar.volume) : "—"}</div>
        </div>
        <div className="flow-cell">
          <div className="flow-k">CLOSE</div>
          <div className="flow-v">{bar ? bar.c.toFixed(1) : "—"}</div>
        </div>
      </div>

      {/*
        Required by the 'N' amendment, not decoration. Delta is least complete
        exactly when the active contract underneath it is rolling, and a UI that
        shows delta without this is hiding that.
      */}
      <div className="unsigned-note">
        {unsigned > 0
          ? `${fmt(unsigned)} contracts unsigned (${unsignedPct.toFixed(2)}% of volume) — excluded from delta`
          : "no unsigned volume this bar"}
      </div>

      <div className="eyebrow">RECENT OUTLIERS</div>

      {outliers.length === 0 ? (
        <div className="empty-note">Nothing flagged yet.</div>
      ) : (
        <div className="outlier-list">
          {outliers.map((o) => (
            <div key={o.id} className="outlier-row">
              <span className={`outlier-kind k-${o.kind}`}>{KIND_COPY[o.kind]}</span>
              <span className="outlier-price">{o.price.toFixed(1)}</span>
              <span className={`outlier-side s-${o.side}`}>{o.side}</span>
              <span className="outlier-size">{fmt(o.size)}</span>
              <span className="outlier-score">{o.score}</span>
            </div>
          ))}
        </div>
      )}

      {controls && (
        <>
          <div className="eyebrow">MOCK — BREAK IT ON PURPOSE</div>
          <div className="mock-note">
            Replaying 2026-07-16 at 10×. These controls exist only while the
            engine is the fake.
          </div>
          <div className="mock-controls">
            <button className="mock-btn" onClick={() => controls.goStale()}>
              Go stale
            </button>
            <button className="mock-btn" onClick={() => controls.drop()}>
              Drop feed
            </button>
            <button className="mock-btn" onClick={() => controls.emitWideCvd()}>
              7-digit CVD
            </button>
            <button className="mock-btn" onClick={longSymbol}>
              40-char symbol
            </button>
            <button className="mock-btn primary" onClick={() => controls.resume()}>
              Resume
            </button>
          </div>
        </>
      )}
    </div>
  );
}
