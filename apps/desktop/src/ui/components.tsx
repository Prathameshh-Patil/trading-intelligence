import { animate, motion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { AlertIcon, CheckIcon } from "./Icons";
import { pressable, riseIn, softSpring, spring } from "./motion";
import type { RiskLevel } from "../lib/rules";
import { formatDuration, type Feed } from "../lib/feed";
import type { FeedState } from "../lib/engine/types";

/* ------------------------------------------------------------------ */
/* Animated number                                                     */
/* ------------------------------------------------------------------ */

export function CountUp({
  value,
  decimals = 0,
  suffix = "",
  prefix = "",
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
}) {
  const [shown, setShown] = useState(0);
  const previous = useRef(0);

  useEffect(() => {
    const controls = animate(previous.current, value, {
      duration: 0.75,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (latest) => setShown(latest),
    });

    previous.current = value;
    return () => controls.stop();
  }, [value]);

  return (
    <>
      {prefix}
      {shown.toFixed(decimals)}
      {suffix}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Confidence ring                                                     */
/* ------------------------------------------------------------------ */

export function ConfidenceRing({ value }: { value: number }) {
  const size = 76;
  const stroke = 7;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(Math.max(value, 0), 100);

  return (
    <div className="ring">
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
          fill="none"
        />

        <defs>
          <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#6366f1" />
          </linearGradient>
        </defs>

        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="url(#ringGrad)"
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - pct / 100) }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>

      <div className="ring-label">
        <CountUp value={pct} suffix="%" />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Rule status pill                                                    */
/* ------------------------------------------------------------------ */

const LEVEL_COPY: Record<RiskLevel, string> = {
  clear: "Rules clear",
  caution: "Check rules",
  breach: "Rule breach",
};

export function RulePill({
  level,
  count,
  onClick,
}: {
  level: RiskLevel;
  count: number;
  onClick: () => void;
}) {
  return (
    <motion.button
      className={`rule-pill ${level}`}
      onClick={onClick}
      whileTap={{ scale: 0.95 }}
      transition={spring}
      title={
        count > 0
          ? `${count} rule${count > 1 ? "s" : ""} need attention`
          : "All trading rules satisfied"
      }
    >
      <motion.span
        className="dot"
        animate={
          level === "clear"
            ? { opacity: 1, scale: 1 }
            : { opacity: [1, 0.35, 1], scale: [1, 0.82, 1] }
        }
        transition={
          level === "clear"
            ? undefined
            : { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
        }
      />
      {LEVEL_COPY[level]}
      {count > 0 && ` · ${count}`}
    </motion.button>
  );
}

/* ------------------------------------------------------------------ */
/* Feed status indicator                                               */
/* ------------------------------------------------------------------ */

/**
 * Four states, told apart three ways at once — hue, glyph shape, and label —
 * because `theme.css` zeroes every animation under `prefers-reduced-motion`
 * and a design that leaned on the blink would collapse `stale` into `live`
 * for exactly the trader who asked for less motion.
 *
 *   live          green   filled circle, steady
 *   connecting    indigo  hollow ring (spins when motion is allowed)
 *   stale         amber   filled circle + a counter of time spent stale
 *   disconnected  red     square
 *
 * `stale` is the one S2 says is easy to get wrong, so it is the only state
 * that carries a number: `Stale 42s` reads as "connected, heard nothing for
 * 42 seconds" from across a desk, where `Stale` alone reads as a quiet market.
 * The number is time in state, not time since a tick — `feed.ts` says why.
 */
const FEED_COPY: Record<FeedState, { label: string; hint: string }> = {
  live: { label: "Live", hint: "Feed connected and receiving ticks" },
  connecting: { label: "Connecting", hint: "Opening the feed connection" },
  stale: {
    label: "Stale",
    hint: "Connected but not receiving. This is not a quiet market — no tick has arrived.",
  },
  disconnected: { label: "No feed", hint: "Not connected to any feed" },
};

export function FeedPill({ feed, onClick }: { feed: Feed; onClick: () => void }) {
  const { state, vendor } = feed.status;
  const copy = FEED_COPY[state];

  const counting = state === "stale";
  const elapsed = formatDuration(feed.inStateMs);

  const title = [
    copy.hint,
    vendor ? `Vendor: ${vendor}` : null,
    counting ? `Stale for ${elapsed}` : null,
    feed.error ? `Connect failed: ${feed.error}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <motion.button
      className={`feed-pill ${state}`}
      onClick={onClick}
      whileTap={{ scale: 0.95 }}
      transition={spring}
      title={title}
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="feed-glyph" aria-hidden />
      {/* Live is the steady state, so it is a steady green dot and nothing
          else -- at 380px the word costs the brand its last syllable, and the
          three states that need a trader's attention stand out more against
          a wordless normal. Screen readers still get the label. */}
      {state === "live" ? <span className="sr-only">{copy.label}</span> : copy.label}
      {/* Announce a change of state, not every second of the stale counter:
          the counter is hidden from the live region and the state is not. */}
      {counting && <span aria-hidden>{`\u00a0${elapsed}`}</span>}
    </motion.button>
  );
}

/* ------------------------------------------------------------------ */
/* Action tile                                                         */
/* ------------------------------------------------------------------ */

export function ActionTile({
  icon,
  title,
  subtitle,
  onClick,
  wide,
  primary,
  badge,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  onClick: () => void;
  wide?: boolean;
  primary?: boolean;
  badge?: number;
}) {
  return (
    <motion.button
      variants={riseIn}
      {...pressable}
      className={`tile${wide ? " wide" : ""}${primary ? " primary" : ""}`}
      onClick={onClick}
    >
      {badge !== undefined && badge > 0 && (
        <motion.span
          className="tile-badge"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={softSpring}
        >
          {badge}
        </motion.span>
      )}

      <div className="tile-icon">{icon}</div>

      <div>
        <div className="tile-title">{title}</div>
        <div className="tile-sub">{subtitle}</div>
      </div>
    </motion.button>
  );
}

/* ------------------------------------------------------------------ */
/* Toggle                                                              */
/* ------------------------------------------------------------------ */

export function Toggle({
  on,
  onChange,
  label,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      className="toggle"
      data-on={on}
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
    >
      <motion.span animate={{ x: on ? 14 : 0 }} transition={spring} />
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Stat                                                                */
/* ------------------------------------------------------------------ */

export function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: ReactNode;
  tone?: "pos" | "neg";
}) {
  return (
    <motion.div className="stat" variants={riseIn}>
      <div className="stat-label">{label}</div>
      <div className={`stat-value${tone ? ` ${tone}` : ""}`}>{value}</div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Toast                                                               */
/* ------------------------------------------------------------------ */

export function Toast({
  message,
  tone = "info",
}: {
  message: string;
  tone?: "info" | "breach";
}) {
  return (
    <motion.div
      className={`toast${tone === "breach" ? " breach" : ""}`}
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={spring}
    >
      {tone === "breach" ? (
        <AlertIcon size={15} className="alert" />
      ) : (
        <CheckIcon size={13} />
      )}
      <span>{message}</span>
    </motion.div>
  );
}
