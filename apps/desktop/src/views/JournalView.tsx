import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";

import { AlertIcon, PlusIcon, TrashIcon } from "../ui/Icons";
import { riseIn, spring, stagger } from "../ui/motion";
import { evaluateRules } from "../lib/rules";
import type {
  JournalEntry,
  RuleViolation,
  TradeRule,
  TradeOutcome,
  TradeSide,
} from "../lib/types";

interface Props {
  journal: JournalEntry[];
  rules: TradeRule[];
  currentViolations: RuleViolation[];
  onAdd: (entry: Omit<JournalEntry, "id">) => void;
  onDelete: (id: string) => void;
}

const emptyDraft = {
  symbol: "",
  side: "long" as TradeSide,
  outcome: "open" as TradeOutcome,
  riskPct: 1,
  rMultiple: 0,
  note: "",
  tags: "",
};

const timeLabel = (ts: number) =>
  new Date(ts).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

export default function JournalView({
  journal,
  rules,
  currentViolations,
  onAdd,
  onDelete,
}: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [override, setOverride] = useState(false);

  // Pinned when the form opens so the live rule preview stays stable while
  // the user types. The committed entry re-stamps this on submit.
  const [draftOpenedAt, setDraftOpenedAt] = useState(() => Date.now());

  const set = <K extends keyof typeof emptyDraft>(
    key: K,
    value: (typeof emptyDraft)[K],
  ) => setDraft((prev) => ({ ...prev, [key]: value }));

  const prospective = useMemo((): Omit<JournalEntry, "id"> => {
    return {
      symbol: draft.symbol.trim().toUpperCase() || "NEW",
      side: draft.side,
      outcome: draft.outcome,
      riskPct: Number(draft.riskPct) || 0,
      rMultiple: Number(draft.rMultiple) || 0,
      note: draft.note.trim(),
      openedAt: draftOpenedAt,
      tags: draft.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
  }, [draft, draftOpenedAt]);

  /**
   * Rules this trade is responsible for: ones it breaks outright, plus ones
   * already broken that it pushes further past the line. Comparing overage
   * rather than mere presence matters — logging a 4.5% risk on a day that
   * already has a 2.6% breach is the user's doing, and staying quiet about it
   * because the rule was "already red" would hide the thing they need to see.
   */
  const newViolations = useMemo(() => {
    if (!open) return [];

    const existing = new Map(
      currentViolations.map((v) => [v.ruleId, v.overage]),
    );

    const projected = evaluateRules(rules, [
      { ...prospective, id: "__draft" },
      ...journal,
    ]);

    return projected.filter((v) => {
      const before = existing.get(v.ruleId);
      return before === undefined || v.overage > before + 1e-9;
    });
  }, [open, prospective, journal, rules, currentViolations]);

  const blocking = newViolations.filter((v) => v.severity === "hard");
  const needsOverride = blocking.length > 0 && !override;

  const reset = () => {
    setDraft(emptyDraft);
    setOverride(false);
    setOpen(false);
  };

  const submit = () => {
    if (needsOverride) return;

    onAdd({ ...prospective, openedAt: Date.now() });
    reset();
  };

  const openForm = () => {
    setDraftOpenedAt(Date.now());
    setOpen(true);
  };

  return (
    <motion.div
      className="view"
      variants={stagger}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={riseIn} className="between">
        <div>
          <div className="eyebrow">Journal</div>
          <h2>{journal.length} trades logged</h2>
        </div>

        {!open && (
          <motion.button
            className="btn sm"
            onClick={openForm}
            whileTap={{ scale: 0.96 }}
            transition={spring}
          >
            <PlusIcon size={14} />
            Log trade
          </motion.button>
        )}
      </motion.div>

      <AnimatePresence>
        {open && (
          <motion.div
            className="card pad-lg stack"
            layout
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={spring}
          >
            <div className="row" style={{ gap: 8 }}>
              <div className="field" style={{ flex: 1.2 }}>
                <label>Symbol</label>
                <input
                  className="input"
                  value={draft.symbol}
                  placeholder="NVDA"
                  onChange={(e) => set("symbol", e.target.value)}
                />
              </div>

              <div className="field" style={{ flex: 1 }}>
                <label>Side</label>
                <select
                  className="select"
                  value={draft.side}
                  onChange={(e) => set("side", e.target.value as TradeSide)}
                >
                  <option value="long">Long</option>
                  <option value="short">Short</option>
                </select>
              </div>
            </div>

            <div className="row" style={{ gap: 8 }}>
              <div className="field" style={{ flex: 1 }}>
                <label>Risk %</label>
                <input
                  className="input"
                  type="number"
                  step={0.1}
                  min={0}
                  value={draft.riskPct}
                  onChange={(e) => set("riskPct", Number(e.target.value))}
                />
              </div>

              <div className="field" style={{ flex: 1 }}>
                <label>Result R</label>
                <input
                  className="input"
                  type="number"
                  step={0.1}
                  value={draft.rMultiple}
                  onChange={(e) => set("rMultiple", Number(e.target.value))}
                />
              </div>

              <div className="field" style={{ flex: 1 }}>
                <label>Outcome</label>
                <select
                  className="select"
                  value={draft.outcome}
                  onChange={(e) =>
                    set("outcome", e.target.value as TradeOutcome)
                  }
                >
                  <option value="open">Open</option>
                  <option value="win">Win</option>
                  <option value="loss">Loss</option>
                </select>
              </div>
            </div>

            <div className="field">
              <label>Note</label>
              <textarea
                className="textarea"
                value={draft.note}
                placeholder="What was the setup, and did it match the plan?"
                onChange={(e) => set("note", e.target.value)}
              />
            </div>

            <div className="field">
              <label>Tags (comma separated)</label>
              <input
                className="input"
                value={draft.tags}
                placeholder="momentum, planned"
                onChange={(e) => set("tags", e.target.value)}
              />
            </div>

            {/* The warning indicator: fires as the draft is edited, before
                anything is committed. */}
            <AnimatePresence>
              {newViolations.length > 0 && (
                <motion.div
                  layout
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={spring}
                >
                  <motion.div
                    className={`notice ${blocking.length > 0 ? "error" : "warn"}`}
                    animate={
                      blocking.length > 0
                        ? { borderColor: [
                            "rgba(248,113,113,0.28)",
                            "rgba(248,113,113,0.7)",
                            "rgba(248,113,113,0.28)",
                          ] }
                        : {}
                    }
                    transition={{
                      duration: 1.8,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  >
                    <div
                      className="row"
                      style={{ gap: 7, marginBottom: 6, alignItems: "center" }}
                    >
                      <AlertIcon size={14} />
                      <strong>
                        This trade breaks{" "}
                        {newViolations.length === 1
                          ? "a rule"
                          : `${newViolations.length} rules`}
                      </strong>
                    </div>

                    <div className="stack" style={{ gap: 5 }}>
                      {newViolations.map((v) => (
                        <div key={v.ruleId}>
                          <strong>{v.label}</strong> — {v.message}
                        </div>
                      ))}
                    </div>

                    {blocking.length > 0 && (
                      <label
                        className="row"
                        style={{
                          gap: 7,
                          marginTop: 10,
                          cursor: "pointer",
                          alignItems: "center",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={override}
                          onChange={(e) => setOverride(e.target.checked)}
                        />
                        <span>
                          Log it anyway and record the override
                        </span>
                      </label>
                    )}
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="row" style={{ gap: 8 }}>
              <button className="btn ghost" style={{ flex: 1 }} onClick={reset}>
                Cancel
              </button>

              <motion.button
                className={`btn${needsOverride ? " danger" : ""}`}
                style={{ flex: 1 }}
                onClick={submit}
                disabled={needsOverride || !draft.symbol.trim()}
                whileTap={{ scale: 0.98 }}
                transition={spring}
              >
                {needsOverride ? "Blocked by rules" : "Save trade"}
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {journal.length === 0 && !open && (
        <motion.div variants={riseIn} className="empty">
          No trades yet. Everything logged here feeds the rule checks and the
          strategy review.
        </motion.div>
      )}

      <motion.div className="stack" variants={stagger}>
        <AnimatePresence initial={false}>
          {journal.map((entry) => (
            <motion.div
              key={entry.id}
              className="entry"
              layout
              variants={riseIn}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -20, transition: { duration: 0.18 } }}
              transition={spring}
            >
              <div className="between">
                <div className="row" style={{ gap: 8 }}>
                  <span className="symbol">{entry.symbol}</span>
                  <span className="side">{entry.side}</span>
                </div>

                <div className="row" style={{ gap: 10 }}>
                  {entry.outcome === "open" ? (
                    <span className="side">open</span>
                  ) : (
                    <span
                      className={`r-badge ${entry.rMultiple >= 0 ? "pos" : "neg"}`}
                    >
                      {entry.rMultiple > 0 ? "+" : ""}
                      {entry.rMultiple}R
                    </span>
                  )}

                  <button
                    className="icon-btn"
                    style={{ width: 24, height: 24 }}
                    onClick={() => onDelete(entry.id)}
                    aria-label={`Delete ${entry.symbol} entry`}
                  >
                    <TrashIcon size={12} />
                  </button>
                </div>
              </div>

              <div
                className="row"
                style={{
                  gap: 10,
                  marginTop: 4,
                  fontSize: 11,
                  color: "var(--text-faint)",
                }}
              >
                <span>{timeLabel(entry.openedAt)}</span>
                <span>·</span>
                <span>{entry.riskPct}% risk</span>
              </div>

              {entry.note && <p className="entry-note">{entry.note}</p>}

              {entry.tags.length > 0 && (
                <div className="chips">
                  {entry.tags.map((tag) => (
                    <span key={tag} className="chip">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
