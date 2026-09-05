import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BackIcon, CrosshairIcon } from "./ui/Icons";
import { RulePill, Toast } from "./ui/components";
import { viewVariants } from "./ui/motion";
import "./ui/theme.css";

import { useClickThrough } from "./lib/clickThrough";
import { computeStats, evaluateRules, riskLevel } from "./lib/rules";
import {
  addJournalEntry,
  deleteJournalEntry,
  getJournal,
  getRules,
  getStrategy,
  isExtension,
  saveRules,
  saveStrategy,
} from "./lib/storage";
import type {
  JournalEntry,
  Strategy,
  TradeRule,
  ViewKey,
} from "./lib/types";

import AnalyzeView from "./views/AnalyzeView";
import FlowView from "./views/FlowView";
import HomeView from "./views/HomeView";
import JournalView from "./views/JournalView";
import RulesView from "./views/RulesView";
import StrategyChangeView from "./views/StrategyChangeView";
import StrategyReviewView from "./views/StrategyReviewView";

const TITLES: Record<ViewKey, string> = {
  home: "Trading Intelligence",
  analyze: "Analyze screen",
  flow: "Order flow",
  rules: "Trade rules",
  "strategy-review": "Review strategy",
  "strategy-change": "Change strategy",
  journal: "Journal",
};

const isSameDay = (a: number, b: number) => {
  const da = new Date(a);
  const db = new Date(b);
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  );
};

export default function SidePanel() {
  const [view, setView] = useState<ViewKey>("home");
  const [direction, setDirection] = useState(1);

  const clickThrough = useClickThrough();

  // Diagnostic aid: an opaque panel makes click-through untestable, because
  // there is nothing under it to aim at. Faded while armed so what is being
  // clicked is actually visible; see the CSS rule for the caveat.
  useEffect(() => {
    document.body.classList.toggle("click-through-armed", clickThrough.enabled);
  }, [clickThrough.enabled]);

  const [rules, setRules] = useState<TradeRule[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loaded, setLoaded] = useState(false);

  const [toast, setToast] = useState<{
    message: string;
    tone: "info" | "breach";
  } | null>(null);

  /**
   * Clock the rule engine reads from. Several rules are time-sensitive (the
   * cooling-off window, the session window), so this ticks rather than being
   * sampled once during render.
   */
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const toastTimer = useRef<number | undefined>(undefined);

  const flash = useCallback(
    (message: string, tone: "info" | "breach" = "info") => {
      setToast({ message, tone });
      window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(null), 3200);
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const [r, j, s] = await Promise.all([
        getRules(),
        getJournal(),
        getStrategy(),
      ]);

      if (cancelled) return;

      setRules(r);
      setJournal(j);
      setStrategy(s);
      setLoaded(true);
    })();

    return () => {
      cancelled = true;
      window.clearTimeout(toastTimer.current);
    };
  }, []);

  // Outside Chrome, frame the panel so it reads as a docked side panel.
  useEffect(() => {
    if (!isExtension()) {
      document.body.classList.add("standalone");
    }
  }, []);

  const violations = useMemo(
    () => evaluateRules(rules, journal, now),
    [rules, journal, now],
  );

  const level = riskLevel(violations);
  const stats = useMemo(() => computeStats(journal), [journal]);

  const todayCount = useMemo(
    () => journal.filter((entry) => isSameDay(entry.openedAt, now)).length,
    [journal, now],
  );

  const navigate = useCallback(
    (next: ViewKey) => {
      setDirection(next === "home" ? -1 : view === "home" ? 1 : 1);
      setView(next);
    },
    [view],
  );

  const goHome = useCallback(() => {
    setDirection(-1);
    setView("home");
  }, []);

  /* -------------------------------------------------------------- */
  /* Mutations                                                       */
  /* -------------------------------------------------------------- */

  const handleToggleRule = async (id: string, enabled: boolean) => {
    const next = rules.map((rule) =>
      rule.id === id ? { ...rule, enabled } : rule,
    );

    setRules(next);
    await saveRules(next);
  };

  const handleSaveStrategy = async (next: Strategy) => {
    setStrategy(next);
    await saveStrategy(next);

    flash("Strategy updated");
    setDirection(-1);
    setView("strategy-review");
  };

  const handleAddEntry = async (entry: Omit<JournalEntry, "id">) => {
    const updated = await addJournalEntry(entry);
    setJournal(updated);

    const after = evaluateRules(rules, updated);
    const hard = after.filter((v) => v.severity === "hard").length;

    if (hard > 0) {
      flash(`Logged — ${hard} hard rule breach open`, "breach");
    } else {
      flash(`${entry.symbol} logged`);
    }
  };

  const handleDeleteEntry = async (id: string) => {
    setJournal(await deleteJournalEntry(id));
    flash("Entry removed");
  };

  /* -------------------------------------------------------------- */

  if (!loaded || !strategy) {
    return (
      <div className="shell">
        <div className="topbar" data-tauri-drag-region>
          <div className="brand">
            <div className="brand-mark">T</div>
            Trading Intelligence
          </div>
        </div>
      </div>
    );
  }

  const renderView = () => {
    switch (view) {
      case "analyze":
        return <AnalyzeView violations={violations} onNavigate={navigate} />;

      case "flow":
        return <FlowView />;

      case "rules":
        return (
          <RulesView
            rules={rules}
            violations={violations}
            onToggle={handleToggleRule}
          />
        );

      case "strategy-review":
        return (
          <StrategyReviewView
            strategy={strategy}
            stats={stats}
            journal={journal}
            onEdit={() => navigate("strategy-change")}
          />
        );

      case "strategy-change":
        return (
          <StrategyChangeView
            strategy={strategy}
            onSave={handleSaveStrategy}
            onCancel={() => navigate("strategy-review")}
          />
        );

      case "journal":
        return (
          <JournalView
            journal={journal}
            rules={rules}
            currentViolations={violations}
            onAdd={handleAddEntry}
            onDelete={handleDeleteEntry}
          />
        );

      default:
        return (
          <HomeView
            stats={stats}
            todayCount={todayCount}
            violations={violations}
            level={level}
            strategyName={strategy.name}
            onNavigate={navigate}
          />
        );
    }
  };

  return (
    <div className="shell">
      {/*
        The window is borderless (`decorations: false`), so there is no titlebar
        to grab and the topbar has to be the drag handle. Tauri starts a drag
        only when the mousedown target *itself* carries the attribute, so the
        back button and the rule pill inside stay clickable — the draggable area
        is the topbar's own background and the spacer.
      */}
      <div className="topbar" data-tauri-drag-region>
        <AnimatePresence mode="wait" initial={false}>
          {view === "home" ? (
            <motion.div
              key="brand"
              className="brand"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.16 }}
            >
              <div className="brand-mark">T</div>
              Trading Intelligence
            </motion.div>
          ) : (
            <motion.div
              key="back"
              className="row"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.16 }}
            >
              <button
                className="back-btn"
                onClick={goHome}
                aria-label="Back to home"
              >
                <BackIcon size={15} />
              </button>

              <span className="topbar-title">{TITLES[view]}</span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="spacer" data-tauri-drag-region />

        <button
          className={`click-through-btn${clickThrough.enabled ? " armed" : ""}`}
          onClick={clickThrough.toggle}
          title={
            clickThrough.enabled
              ? "Click-through armed — every click reaches MT5 behind this window. Press ⌘⇧K anywhere to disarm."
              : "Arm click-through — pass every click on this window through to MT5"
          }
          aria-pressed={clickThrough.enabled}
        >
          <CrosshairIcon size={14} />
        </button>

        <RulePill
          level={level}
          count={violations.length}
          onClick={() => navigate("rules")}
        />
      </div>

      <div className="content">
        <AnimatePresence mode="wait" custom={direction} initial={false}>
          <motion.div
            key={view}
            custom={direction}
            variants={viewVariants}
            initial="enter"
            animate="center"
            exit="exit"
            style={{ position: "absolute", inset: 0 }}
          >
            {renderView()}
          </motion.div>
        </AnimatePresence>

        <AnimatePresence>
          {toast && <Toast message={toast.message} tone={toast.tone} />}
        </AnimatePresence>
      </div>
    </div>
  );
}
