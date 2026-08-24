import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { PlusIcon, TrashIcon } from "../ui/Icons";
import { riseIn, spring, stagger } from "../ui/motion";
import type { Strategy } from "../lib/types";

interface Props {
  strategy: Strategy;
  onSave: (next: Strategy) => void;
  onCancel: () => void;
}

type ListKey = "entryCriteria" | "exitCriteria";

export default function StrategyChangeView({
  strategy,
  onSave,
  onCancel,
}: Props) {
  const [draft, setDraft] = useState<Strategy>(strategy);

  const set = <K extends keyof Strategy>(key: K, value: Strategy[K]) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  const updateItem = (key: ListKey, index: number, value: string) =>
    setDraft((prev) => {
      const list = [...prev[key]];
      list[index] = value;
      return { ...prev, [key]: list };
    });

  const addItem = (key: ListKey) =>
    setDraft((prev) => ({ ...prev, [key]: [...prev[key], ""] }));

  const removeItem = (key: ListKey, index: number) =>
    setDraft((prev) => ({
      ...prev,
      [key]: prev[key].filter((_, i) => i !== index),
    }));

  const dirty = JSON.stringify(draft) !== JSON.stringify(strategy);

  const handleSave = () =>
    onSave({
      ...draft,
      entryCriteria: draft.entryCriteria.filter((s) => s.trim()),
      exitCriteria: draft.exitCriteria.filter((s) => s.trim()),
    });

  const criteriaBlock = (key: ListKey, label: string) => (
    <motion.div variants={riseIn} className="field">
      <label>{label}</label>

      <div className="stack" style={{ gap: 8 }}>
        <AnimatePresence initial={false}>
          {draft[key].map((item, index) => (
            <motion.div
              key={`${key}-${index}`}
              className="criteria-row"
              layout
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={spring}
            >
              <input
                className="input"
                value={item}
                placeholder="Describe the condition"
                onChange={(e) => updateItem(key, index, e.target.value)}
              />

              <button
                className="icon-btn"
                onClick={() => removeItem(key, index)}
                aria-label="Remove criterion"
              >
                <TrashIcon size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>

        <button className="btn ghost sm" onClick={() => addItem(key)}>
          <PlusIcon size={14} />
          Add condition
        </button>
      </div>
    </motion.div>
  );

  return (
    <motion.div
      className="view"
      variants={stagger}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={riseIn}>
        <div className="eyebrow">Edit</div>
        <h2>Change strategy</h2>
        <p className="lede" style={{ marginTop: 6 }}>
          Changes apply to future analysis and rule checks. Past journal entries
          keep the plan they were taken under.
        </p>
      </motion.div>

      <motion.div variants={riseIn} className="field">
        <label>Name</label>
        <input
          className="input"
          value={draft.name}
          onChange={(e) => set("name", e.target.value)}
        />
      </motion.div>

      <motion.div variants={riseIn} className="row" style={{ gap: 10 }}>
        <div className="field" style={{ flex: 1 }}>
          <label>Market</label>
          <input
            className="input"
            value={draft.market}
            onChange={(e) => set("market", e.target.value)}
          />
        </div>

        <div className="field" style={{ flex: 1 }}>
          <label>Timeframe</label>
          <input
            className="input"
            value={draft.timeframe}
            onChange={(e) => set("timeframe", e.target.value)}
          />
        </div>
      </motion.div>

      <motion.div variants={riseIn} className="field">
        <label>Thesis</label>
        <textarea
          className="textarea"
          value={draft.thesis}
          onChange={(e) => set("thesis", e.target.value)}
        />
      </motion.div>

      <motion.div variants={riseIn} className="field">
        <label>Max risk per trade (%)</label>
        <input
          className="input"
          type="number"
          min={0.1}
          max={10}
          step={0.1}
          value={draft.maxRiskPct}
          onChange={(e) =>
            set("maxRiskPct", Number(e.target.value) || 0)
          }
        />
      </motion.div>

      {criteriaBlock("entryCriteria", "Entry criteria")}
      {criteriaBlock("exitCriteria", "Exit criteria")}

      <motion.div variants={riseIn} className="row" style={{ gap: 8 }}>
        <button className="btn ghost" style={{ flex: 1 }} onClick={onCancel}>
          Cancel
        </button>

        <motion.button
          className="btn"
          style={{ flex: 1 }}
          onClick={handleSave}
          disabled={!dirty}
          whileTap={{ scale: 0.98 }}
          transition={spring}
        >
          Save changes
        </motion.button>
      </motion.div>
    </motion.div>
  );
}
