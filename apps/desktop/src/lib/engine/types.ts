/**
 * S2 · Engine IPC — the seam between Varad's Rust engine and this UI.
 *
 * Transcribed from `plans/team/contracts.md` S2. This file is the contract;
 * `contracts.md` is the prose about it. If they ever disagree, that is a bug in
 * one of them, not a judgement call.
 *
 * Why this file exists on day one: the engine does not exist until Week 3, and
 * the Analyze view cannot be built against nothing. Two implementations sit
 * behind these types —
 *
 *   engine/mock.ts   replays the S1 fixture and misbehaves on demand   (Prathamesh, W1D2)
 *   engine/real.ts   thin wrapper over Tauri invoke/listen             (Varad, W3D1)
 *   engine/index.ts  picks one on VITE_ENGINE=mock|real, default mock
 *
 * FROZEN: W1D1, owned jointly. Changing anything here is a contract change —
 * all three agree in standup, and the type, the fake, the real implementation
 * and every consumer move in ONE commit. Never half.
 */

/** Which side of the book a trade hit. */
export type Side = "bid" | "ask";

/**
 * One time bar of order-flow state.
 *
 * `delta` and `cvd` are the numbers a screenshot can never contain — they need
 * the aggressor side of every individual trade, and a rendered candle threw
 * that away when it was drawn. Two sessions with identical OHLC can have
 * opposite CVD. Everything here comes from the feed, never from capture.
 */
export interface DeltaBar {
  /** Bar open, epoch ms. */
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  volume: number;
  /** askVol - bidVol, signed. */
  delta: number;
  /** Running session total. Resets on the CME session boundary, 18:00 ET. */
  cvd: number;
  bidVol: number;
  askVol: number;
}

/** What kind of order-flow event the engine thinks it saw. */
export type OutlierKind = "absorption" | "trapped" | "cluster";

export interface Outlier {
  id: string;
  t: number;
  price: number;
  size: number;
  side: Side;
  kind: OutlierKind;
  clusterLow: number;
  clusterHigh: number;
  /** 0-100, comparable across instruments. */
  score: number;
}

/**
 * `stale` is the state that matters and the one that is easy to get wrong:
 * connected but not receiving. It looks identical to a quiet market and is not.
 * Render the four distinctly enough to tell apart from three feet away.
 */
export type FeedState = "disconnected" | "connecting" | "live" | "stale";

export interface FeedStatus {
  state: FeedState;
  vendor: string | null;
  /** Epoch ms of the last tick received, or null if none yet. */
  lastTickAt: number | null;
  gapCount: number;
}

/**
 * ⚠️ THE ONE HOLE IN S2 — not frozen, decide before W3D3.
 *
 * `contracts.md` names `FeedCreds` in the Engine interface and never defines
 * it; grepped 25 Aug, it appears exactly once in the whole repo, at
 * contracts.md:119. So there is nothing to transcribe here.
 *
 * It is left deliberately open rather than invented, because the credential
 * fields are a function of the vendor and **the vendor is an open question** —
 * `current.md` C1 proposes Databento → quantfeed and says plainly that nothing
 * about that vendor is confirmed. Guessing a shape now means guessing it wrong
 * and freezing the guess.
 *
 * This blocks nothing before Week 3: `mock.ts` ignores creds entirely, so all
 * of Weeks 1-2 build fine against it. Close it when the vendor is settled.
 */
export interface FeedCreds {
  /** Which adapter these credentials are for. */
  vendor: string;
  /** Vendor-specific fields — shape pinned once the vendor is chosen. */
  [field: string]: string | undefined;
}

/**
 * S6 · Capture context — the narrowest seam in the project, narrow on purpose.
 *
 * **Capture produces context. Capture never produces a number that appears in
 * a signal.** Not delta, not CVD, not volume, not an outlier. The absence of a
 * numeric field here other than `levels` and `confidence` IS the enforcement —
 * adding one is a contract change needing all three in standup, because this is
 * exactly the mistake that becomes tempting in Week 8 when a vision model
 * returns something that looks like volume and it would be so convenient.
 */
export interface CaptureContext {
  /**
   * 'GC', or free text when unrecognised. Deliberately not a 'GC' literal:
   * capture reads whatever chart the trader has open, which is frequently
   * something we have no feed for. That unrecognised case is a real UI state
   * to render honestly (W3D4), not an error.
   */
  symbol: string;
  /** '1m' | '5m' | '15m' | ... */
  timeframe: string;
  /** Price levels the trader has drawn. */
  levels: number[];
  /** 0-100, how sure the extraction is. */
  confidence: number;
  capturedAt: number;
}

/** Unsubscribe. Every `on*` returns one; call it on unmount or you leak. */
export type Unsubscribe = () => void;

export interface Engine {
  connect(creds: FeedCreds): Promise<FeedStatus>;
  status(): Promise<FeedStatus>;
  setContext(ctx: CaptureContext): Promise<void>;
  onBar(cb: (b: DeltaBar) => void): Unsubscribe;
  onOutlier(cb: (o: Outlier) => void): Unsubscribe;
  onStatus(cb: (s: FeedStatus) => void): Unsubscribe;
}
