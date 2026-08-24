import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { AlertIcon, RefreshIcon, ScanIcon, SparkIcon } from "../ui/Icons";
import { ConfidenceRing } from "../ui/components";
import { fadeIn, riseIn, spring, stagger } from "../ui/motion";
import { analyze, ApiError, offlineAnalysis } from "../lib/api";
import { captureScreen } from "../lib/capture";
import type {
  AnalyzeResult,
  Capture,
  RuleViolation,
  ViewKey,
} from "../lib/types";

type Phase = "idle" | "capturing" | "ready" | "analyzing" | "done";

interface Props {
  violations: RuleViolation[];
  onNavigate: (view: ViewKey) => void;
}

const verdictClass = (sentiment: string) => {
  const s = sentiment.toLowerCase();
  if (s.includes("bull")) return "bullish";
  if (s.includes("bear")) return "bearish";
  return "neutral";
};

export default function AnalyzeView({ violations, onNavigate }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [capture, setCapture] = useState<Capture | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [degraded, setDegraded] = useState<string | null>(null);

  const hardBreach = violations.some((v) => v.severity === "hard");

  const handleCapture = async () => {
    setPhase("capturing");
    setResult(null);
    setDegraded(null);

    const shot = await captureScreen();

    setCapture(shot);
    setPhase("ready");
  };

  const handleAnalyze = async () => {
    if (!capture) return;

    setPhase("analyzing");
    setDegraded(null);

    const text = capture.text?.trim() ?? "";

    if (!text) {
      // The backend requires non-empty text (min_length=1) and a
      // screenshot-only capture has none — sending it anyway would just
      // earn a guaranteed 422 that then gets misread as "service down".
      // Go straight to the local heuristic instead.
      setResult(offlineAnalysis(""));
      setDegraded(
        "No text was captured — screenshot-only reads use the local heuristic",
      );
      setPhase("done");
      return;
    }

    const payload = {
      text,
      screenshot: capture.screenshot,
      url: capture.url,
      title: capture.title,
    };

    try {
      setResult(await analyze(payload));
    } catch (err) {
      // Keep the flow usable when the service is down — label it clearly
      // rather than presenting a heuristic as a model result. ApiError's
      // own message already distinguishes "unreachable" from "returned
      // <status>", so surface that instead of a hardcoded guess.
      setResult(offlineAnalysis(text));
      setDegraded(
        err instanceof ApiError
          ? err.message
          : "The analysis service is unreachable",
      );
    }

    setPhase("done");
  };

  const hasCapture = phase === "ready" || phase === "analyzing" || phase === "done";

  return (
    <motion.div
      className="view"
      variants={stagger}
      initial="hidden"
      animate="show"
    >
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

      {!hasCapture && (
        <motion.div variants={riseIn} className="stack">
          <p className="lede">
            Grab whatever is on screen — chart, headline, or a passage you have
            highlighted — and get a directional read on it.
          </p>

          <motion.button
            className="btn block"
            onClick={handleCapture}
            disabled={phase === "capturing"}
            whileTap={{ scale: 0.98 }}
            transition={spring}
          >
            {phase === "capturing" ? (
              <>
                <motion.span
                  animate={{ rotate: 360 }}
                  transition={{
                    duration: 0.9,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                  style={{ display: "flex" }}
                >
                  <RefreshIcon size={15} />
                </motion.span>
                Capturing…
              </>
            ) : (
              <>
                <ScanIcon size={16} />
                Capture screen
              </>
            )}
          </motion.button>
        </motion.div>
      )}

      <AnimatePresence>
        {hasCapture && capture && (
          <motion.div
            className="stack"
            variants={fadeIn}
            initial="hidden"
            animate="show"
          >
            {capture.screenshot && (
              <motion.div
                className="capture-frame"
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={spring}
              >
                <img src={capture.screenshot} alt="Captured screen" />
                <span className="capture-tag">VISIBLE TAB</span>
              </motion.div>
            )}

            {capture.text && (
              <div className="card">
                <div className="eyebrow" style={{ marginBottom: 6 }}>
                  Selected text
                </div>
                <p className="capture-text">{capture.text}</p>
              </div>
            )}

            {!capture.screenshot && !capture.text && (
              <div className="empty">
                Nothing to analyze yet. Open a chart or highlight some text,
                then capture again.
              </div>
            )}

            <div className="row">
              <motion.button
                className="btn"
                style={{ flex: 1 }}
                onClick={handleAnalyze}
                disabled={phase === "analyzing"}
                whileTap={{ scale: 0.98 }}
                transition={spring}
              >
                <SparkIcon size={15} />
                {phase === "analyzing" ? "Analyzing…" : "Get prediction"}
              </motion.button>

              <button className="btn ghost sm" onClick={handleCapture}>
                <RefreshIcon size={14} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {phase === "analyzing" && (
          <motion.div
            key="loading"
            className="stack"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="card"
                style={{ height: i === 0 ? 92 : 44 }}
                animate={{ opacity: [0.4, 0.75, 0.4] }}
                transition={{
                  duration: 1.3,
                  repeat: Infinity,
                  delay: i * 0.14,
                  ease: "easeInOut",
                }}
              />
            ))}
          </motion.div>
        )}

        {phase === "done" && result && (
          <motion.div
            key="result"
            className="stack"
            variants={stagger}
            initial="hidden"
            animate="show"
          >
            {degraded && (
              <motion.div variants={riseIn} className="notice warn">
                <AlertIcon size={13} /> {degraded}. Showing a local heuristic —
                start the API for the model result.
              </motion.div>
            )}

            <motion.div variants={riseIn} className="card pad-lg">
              <div className="between" style={{ marginBottom: 14 }}>
                <span className="eyebrow">Prediction</span>
                <span className={`verdict ${verdictClass(result.sentiment)}`}>
                  {result.sentiment.toUpperCase()}
                </span>
              </div>

              <div className="ring-wrap">
                <ConfidenceRing value={result.confidence} />

                <div>
                  <div className="eyebrow">Confidence</div>
                  <p className="lede" style={{ marginTop: 4 }}>
                    {result.summary}
                  </p>
                </div>
              </div>
            </motion.div>

            <motion.div variants={riseIn}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>
                Key signals
              </div>

              <motion.div className="stack" variants={stagger}>
                {result.signals.map((signal) => (
                  <motion.div
                    key={signal}
                    className="signal"
                    variants={riseIn}
                  >
                    <span className="signal-dot" />
                    {signal}
                  </motion.div>
                ))}
              </motion.div>
            </motion.div>

            <motion.button
              variants={riseIn}
              className="btn ghost block"
              onClick={() => onNavigate("journal")}
            >
              Log this idea to the journal
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
