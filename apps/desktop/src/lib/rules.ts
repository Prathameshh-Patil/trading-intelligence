import type {
  JournalEntry,
  RuleViolation,
  StrategyStats,
  TradeRule,
} from "./types";

const MINUTE = 60 * 1000;

const isSameDay = (a: number, b: number): boolean => {
  const da = new Date(a);
  const db = new Date(b);

  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  );
};

/** Minutes since local midnight. */
const minutesIntoDay = (ts: number): number => {
  const d = new Date(ts);
  return d.getHours() * 60 + d.getMinutes();
};

const SESSION_START = 9 * 60 + 30;
const SESSION_END = 11 * 60 + 30;

/** Clamp a ratio into 0..1 for the meters. */
const ratio = (value: number, limit: number): number =>
  limit <= 0 ? 1 : Math.min(Math.max((value - limit) / limit, 0), 1);

/**
 * Evaluate the enabled rules against today's journal.
 *
 * Pure and synchronous so the UI can re-run it on every change without
 * coordinating async state.
 */
export function evaluateRules(
  rules: TradeRule[],
  journal: JournalEntry[],
  now: number = Date.now(),
): RuleViolation[] {
  const violations: RuleViolation[] = [];

  const active = rules.filter((rule) => rule.enabled);
  const byId = new Map(active.map((rule) => [rule.id, rule]));

  const today = journal
    .filter((entry) => isSameDay(entry.openedAt, now))
    .sort((a, b) => a.openedAt - b.openedAt);

  const push = (rule: TradeRule, message: string, overage: number) => {
    violations.push({
      ruleId: rule.id,
      label: rule.label,
      severity: rule.severity,
      message,
      overage,
    });
  };

  /* Max trades per day ------------------------------------------------ */
  const maxTrades = byId.get("max-trades-day");

  if (maxTrades?.limit && today.length > maxTrades.limit) {
    push(
      maxTrades,
      `${today.length} trades taken today against a limit of ${maxTrades.limit}.`,
      ratio(today.length, maxTrades.limit),
    );
  }

  /* Risk per trade ---------------------------------------------------- */
  const maxRisk = byId.get("max-risk");

  if (maxRisk?.limit) {
    const over = today.filter((entry) => entry.riskPct > maxRisk.limit!);

    if (over.length > 0) {
      const worst = Math.max(...over.map((entry) => entry.riskPct));

      push(
        maxRisk,
        `${over.map((e) => e.symbol).join(", ")} risked up to ${worst.toFixed(1)}% against a ${maxRisk.limit}% cap.`,
        ratio(worst, maxRisk.limit),
      );
    }
  }

  /* Consecutive losses ------------------------------------------------ */
  const streakRule = byId.get("consecutive-losses");

  if (streakRule?.limit) {
    let streak = 0;

    for (let i = today.length - 1; i >= 0; i -= 1) {
      if (today[i].outcome === "loss") {
        streak += 1;
      } else if (today[i].outcome === "win") {
        break;
      }
    }

    if (streak >= streakRule.limit) {
      push(
        streakRule,
        `${streak} losses in a row. The rule says stop for the session.`,
        ratio(streak, streakRule.limit),
      );
    }
  }

  /* Revenge / cooling-off window -------------------------------------- */
  const revenge = byId.get("no-revenge");

  if (revenge?.limit) {
    const windowMs = revenge.limit * MINUTE;

    for (let i = 1; i < today.length; i += 1) {
      const previous = today[i - 1];
      const current = today[i];
      const gap = current.openedAt - previous.openedAt;

      if (previous.outcome === "loss" && gap < windowMs) {
        push(
          revenge,
          `${current.symbol} was entered ${Math.round(gap / MINUTE)} min after a losing trade (needs ${revenge.limit} min).`,
          1 - gap / windowMs,
        );
        break;
      }
    }
  }

  /* Session window ---------------------------------------------------- */
  const session = byId.get("session-window");

  if (session) {
    const outside = today.filter((entry) => {
      const m = minutesIntoDay(entry.openedAt);
      return m < SESSION_START || m > SESSION_END;
    });

    if (outside.length > 0) {
      push(
        session,
        `${outside.length} trade${outside.length > 1 ? "s" : ""} taken outside the 9:30-11:30 window.`,
        Math.min(outside.length / Math.max(today.length, 1), 1),
      );
    }
  }

  /* Journalling ------------------------------------------------------- */
  const journalRule = byId.get("journal-every-trade");

  if (journalRule) {
    const blank = today.filter((entry) => entry.note.trim().length === 0);

    if (blank.length > 0) {
      push(
        journalRule,
        `${blank.length} trade${blank.length > 1 ? "s have" : " has"} no note written yet.`,
        Math.min(blank.length / Math.max(today.length, 1), 1),
      );
    }
  }

  // Hard breaches first, then by how far past the line they are.
  return violations.sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === "hard" ? -1 : 1;
    return b.overage - a.overage;
  });
}

export type RiskLevel = "clear" | "caution" | "breach";

export function riskLevel(violations: RuleViolation[]): RiskLevel {
  if (violations.some((v) => v.severity === "hard")) return "breach";
  if (violations.length > 0) return "caution";
  return "clear";
}

/** Aggregate journal performance for the strategy review screen. */
export function computeStats(journal: JournalEntry[]): StrategyStats {
  const closed = journal.filter((entry) => entry.outcome !== "open");

  const wins = closed.filter((entry) => entry.outcome === "win").length;
  const losses = closed.filter((entry) => entry.outcome === "loss").length;
  const trades = closed.length;

  if (trades === 0) {
    return {
      trades: 0,
      wins: 0,
      losses: 0,
      winRate: 0,
      expectancy: 0,
      avgRisk: 0,
      bestR: 0,
      worstR: 0,
    };
  }

  const rs = closed.map((entry) => entry.rMultiple);
  const totalR = rs.reduce((sum, r) => sum + r, 0);

  return {
    trades,
    wins,
    losses,
    winRate: (wins / trades) * 100,
    expectancy: totalR / trades,
    avgRisk:
      closed.reduce((sum, entry) => sum + entry.riskPct, 0) / trades,
    bestR: Math.max(...rs),
    worstR: Math.min(...rs),
  };
}
