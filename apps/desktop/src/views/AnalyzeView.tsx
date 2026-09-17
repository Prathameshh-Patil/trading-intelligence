/**
 * Analyze — capture the chart, learn what it is, then read the engine for it.
 *
 * W3D2 rewrote this view. Before, it POSTed the capture to `/analyze` and
 * rendered the sentiment and confidence that came back as a **prediction** —
 * a "BULLISH 78%" derived from headline text, with an offline heuristic
 * standing in when the API was down. That was the browser extension's flow
 * and it is exactly what `contracts.md` S6 forbids: a number that appears in
 * a signal, produced by capture.
 *
 * Now there are two seams and nothing else:
 *
 *   lib/context.ts   screenshot → CaptureContext     (the one allowed network call)
 *   lib/engine       CaptureContext → bars, outliers  (local, never a network)
 *
 * and the view's job is mostly to render the states between them honestly.
 * W3D4's list — *symbol not recognised, MT5 minimised, trader on a chart we
 * have no feed for* — is each a branch below, and each shows **no number**.
 * The only figures on this screen come from `Engine`, and only when the
 * extractor is confident, the symbol has a feed, and the feed is live.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import { AlertIcon, RefreshIcon, ScanIcon } from "../ui/Icons";
import { ConfidenceRing } from "../ui/components";
import { fadeIn, riseIn, spring, stagger } from "../ui/motion";
import { captureScreen } from "../lib/capture";
import {
  CONFIDENT,
  ContextError,
  FEED_SYMBOLS,
  getExtractor,
  getMockExtractorControls,
  type MockScenario,
} from "../lib/context";
import { getEngine } from "../lib/engine";
import { unsignedVolume } from "../lib/engine/mock";
import type { CaptureContext, DeltaBar, Outlier } from "../lib/engine/types";
import { formatDuration, useFeed } from "../lib/feed";
import type { Capture, RuleViolation, ViewKey } from "../lib/types";

type Phase = "idle" | "capturing" | "reading" | "read" | "failed";

interface Props {
  violations: RuleViolation[];
  onNavigate: (view: ViewKey) => void;
}

const fmt = (n: number) => n.toLocaleString("en-US");
const signed = (n: number) => `${n > 0 ? "+" : ""}${fmt(n)}`;

const SCENARIOS: { key: MockScenario; label: string }[] = [
  { key: "gc", label: "GC chart" },
  { key: "unknown", label: "No-feed chart" },
  { key: "uncertain", label: "Unsure symbol" },
  { key: "failed", label: "Nothing readable" },
];

export default function AnalyzeView({ violations, onNavigate }: Props) {
  const engine = useMemo(() => getEngine(), []);
  const extractor = useMemo(() => getExtractor(), []);
  const controls = useMemo(() => getMockExtractorControls(), []);
  const feed = useFeed();

  const [phase, setPhase] = useState<Phase>("idle");
  const [capture, setCapture] = useState<Capture | null>(null);
  const [ctx, setCtx] = useState<CaptureContext | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const [bar, setBar] = useState<DeltaBar | null>(null);
  const [outliers, setOutliers] = useState<Outlier[]>([]);

  useEffect(() => {
    const offBar = engine.onBar(setBar);
    const offOutlier = engine.onOutlier((o) =>
      setOutliers((prev) => [o, ...prev].slice(0, 5)),
    );
    return () => {
      offBar();
      offOutlier();
    };
  }, [engine]);

  const hardBreach = violations.some((v) => v.severity === "hard");

  const run = async () => {
    setPhase("capturing");
    setCtx(null);
    setFailure(null);

    let shot: Capture;
    try {
      shot = await captureScreen();
    } catch (e) {
      setFailure(e instanceof Error ? e.message : "Capture failed");
      setPhase("failed");
      return;
    }
    setCapture(shot);
    setPhase("reading");

    try {
      const next = await extractor.extract(shot);
      setCtx(next);
      // Tell the engine what chart the trader is on -- but only a chart it
      // has a feed for. Handing it "NVDA" would be asking a GC engine to
      // condition on a symbol it will never see a tick of.
      if (next.confidence >= CONFIDENT && FEED_SYMBOLS.has(next.symbol)) {
        await engine.setContext(next);
      }
      setPhase("read");
    } catch (e) {
      setFailure(
        e instanceof ContextError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Could not read the capture",
      );
      setPhase("failed");
    }
  };

  const busy = phase === "capturing" || phase === "reading";

  // The three honest branches, in the order they should be checked.
  const unsure = ctx !== null && ctx.confidence < CONFIDENT;
  const noFeed = ctx !== null && !unsure && !FEED_SYMBOLS.has(ctx.symbol);
  const feedDown = ctx !== null && !unsure && !noFeed && feed.status.state !== "live";
  const readable = ctx !== null && !unsure && !noFeed && !feedDown;

  const unsigned = bar ? unsignedVolume(bar) : 0;
  const unsignedPct = bar && bar.volume ? (100 * unsigned) / bar.volume : 0;

  return (
    <motion.div className="view" variants={stagger} initial="hidden" animate="show">
      {hardBreach && (
        <motion.button
          variants={riseIn}
          className="notice error"
          onClick={() => onNavigate("rules")}
          style={{ textAlign: "left", cursor: "pointer", width: "100%" }}
        >
          <strong>Rules say stop.</strong> You have an open hard breach today —
          a good read is not a reason to override it.
        </motion.button>
      )}

      {phase === "idle" && (
        <motion.div variants={riseIn} className="stack">
          <p className="lede">
            Capture the chart in view. The overlay works out which instrument
            and timeframe it is, then reads the order flow for it from the
            feed — never from the pixels.
          </p>
          <CaptureButton busy={false} label="Capture chart" onClick={run} />
        </motion.div>
      )}

      {busy && (
        <motion.div variants={riseIn} className="stack">
          <CaptureButton
            busy
            label={phase === "capturing" ? "Capturing…" : "Reading the chart…"}
            onClick={run}
          />
        </motion.div>
      )}

      {phase === "failed" && (
        <motion.div variants={riseIn} className="stack">
          <div className="notice error">
            <AlertIcon size={13} /> {failure}
          </div>
          <CaptureButton busy={false} label="Capture again" onClick={run} />
        </motion.div>
      )}

      <AnimatePresence>
        {phase === "read" && ctx && (
          <motion.div className="stack" variants={fadeIn} initial="hidden" animate="show">
            {capture?.screenshot && (
              <motion.div
                className="capture-frame"
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={spring}
              >
                <img src={capture.screenshot} alt="Captured chart" />
                <span className="capture-tag">CAPTURE</span>
              </motion.div>
            )}

            {/* What the capture said. These are the only things capture is
                allowed to say, and none of them is a signal. */}
            <div className="card pad-lg">
              <div className="between" style={{ marginBottom: 12 }}>
                <span className="eyebrow">Chart read as</span>
                <span className="context-tf">{ctx.timeframe}</span>
              </div>
              <div className="ring-wrap">
                <ConfidenceRing value={ctx.confidence} />
                <div>
                  <div className="context-symbol" title={ctx.symbol}>
                    {ctx.symbol}
                  </div>
                  <div className="eyebrow" style={{ marginTop: 4 }}>
                    Extraction confidence
                  </div>
                  <div className="context-levels">
                    {ctx.levels.length
                      ? `${ctx.levels.length} drawn level${ctx.levels.length > 1 ? "s" : ""}: ${ctx.levels.map((l) => l.toFixed(1)).join(", ")}`
                      : "No drawn levels"}
                  </div>
                </div>
              </div>
            </div>

            {unsure && (
              <div className="notice warn">
                <AlertIcon size={13} /> Not sure this is {ctx.symbol} — extraction
                confidence {ctx.confidence}, below {CONFIDENT}. No numbers until
                the chart is read cleanly. Bring it to the front and capture again.
              </div>
            )}

            {noFeed && (
              <div className="notice warn">
                <AlertIcon size={13} /> No feed for {ctx.symbol}. This overlay
                reads order flow for {[...FEED_SYMBOLS].join(", ")}; nothing here
                can say anything about {ctx.symbol}, and it will not pretend to.
              </div>
            )}

            {feedDown && (
              <div className="notice warn">
                <AlertIcon size={13} />{" "}
                {feed.status.state === "stale"
                  ? `Feed is connected but has sent nothing for ${formatDuration(feed.inStateMs)}. That is not a quiet market — no read until ticks resume.`
                  : feed.status.state === "connecting"
                    ? "Feed is still connecting. No read yet."
                    : "No feed connected. Nothing to read from."}
              </div>
            )}

            {readable && (
              <>
                <motion.div className="cvd-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <div className="cvd-label">SESSION CVD · {ctx.symbol}</div>
                  <div className={`cvd-value ${(bar?.cvd ?? 0) >= 0 ? "pos" : "neg"}`}>
                    {bar ? signed(bar.cvd) : "—"}
                  </div>
                  <div className="cvd-sub">
                    bar delta {bar ? signed(bar.delta) : "—"}
                    {bar && ` · ${fmt(bar.volume)} contracts`}
                  </div>
                </motion.div>

                {/* The 'N' amendment: delta is never shown without the share
                    of volume it could not attribute. */}
                <div className="unsigned-note">
                  {bar
                    ? unsigned > 0
                      ? `${fmt(unsigned)} contracts unsigned (${unsignedPct.toFixed(2)}% of volume) — excluded from delta`
                      : "no unsigned volume this bar"
                    : "waiting for the first bar"}
                </div>

                <div className="eyebrow">FLAGGED ON THIS CHART</div>
                {outliers.length === 0 ? (
                  <div className="empty-note">Nothing flagged yet.</div>
                ) : (
                  <div className="outlier-list">
                    {outliers.map((o) => (
                      <div key={o.id} className="outlier-row">
                        <span className={`outlier-kind k-${o.kind}`}>{o.kind}</span>
                        <span className="outlier-price">{o.price.toFixed(1)}</span>
                        <span className={`outlier-side s-${o.side}`}>{o.side}</span>
                        <span className="outlier-size">{fmt(o.size)}</span>
                        <span className="outlier-score">{o.score}</span>
                      </div>
                    ))}
                  </div>
                )}

                <button className="btn ghost block" onClick={() => onNavigate("flow")}>
                  Open order flow
                </button>
              </>
            )}

            <div className="row">
              <button className="btn ghost" style={{ flex: 1 }} onClick={run}>
                <RefreshIcon size={14} /> Capture again
              </button>
              {readable && (
                <button className="btn ghost" style={{ flex: 1 }} onClick={() => onNavigate("journal")}>
                  Log to journal
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {controls && (
        <>
          <div className="eyebrow">MOCK — WHAT THE NEXT CAPTURE READS AS</div>
          <div className="mock-note">
            The extractor is the fake. Pick a scenario, then capture. These
            controls exist only while it is.
          </div>
          <div className="mock-controls">
            {SCENARIOS.map((s) => (
              <button
                key={s.key}
                className={`mock-btn${controls.scenario === s.key ? " primary" : ""}`}
                onClick={() => {
                  controls.setScenario(s.key);
                  void run();
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </>
      )}
    </motion.div>
  );
}

function CaptureButton({
  busy,
  label,
  onClick,
}: {
  busy: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <motion.button
      className="btn block"
      onClick={onClick}
      disabled={busy}
      whileTap={{ scale: 0.98 }}
      transition={spring}
    >
      {busy ? (
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
          style={{ display: "flex" }}
        >
          <RefreshIcon size={15} />
        </motion.span>
      ) : (
        <ScanIcon size={16} />
      )}
      {label}
    </motion.button>
  );
}
