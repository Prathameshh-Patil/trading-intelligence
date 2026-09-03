export type Sentiment = "Bullish" | "Bearish" | "Neutral";

export type RuleSeverity = "hard" | "soft";

export type TradeSide = "long" | "short";

export type TradeOutcome = "win" | "loss" | "open";

export interface AnalyzeRequest {
  text?: string;
  screenshot?: string;
  url?: string;
  title?: string;
}

export interface AnalyzeResult {
  sentiment: Sentiment | string;
  confidence: number;
  summary: string;
  signals: string[];
}

export interface Capture {
  text?: string;
  screenshot?: string;
  url?: string;
  title?: string;
  capturedAt?: number;
}

export interface TradeRule {
  id: string;
  label: string;
  detail: string;
  severity: RuleSeverity;
  enabled: boolean;
  /** Threshold the rule is measured against, when numeric. */
  limit?: number;
}

export interface RuleViolation {
  ruleId: string;
  label: string;
  severity: RuleSeverity;
  message: string;
  /** 0..1 — how far past the limit we are, for the meter. */
  overage: number;
}

export interface JournalEntry {
  id: string;
  symbol: string;
  side: TradeSide;
  outcome: TradeOutcome;
  riskPct: number;
  rMultiple: number;
  note: string;
  openedAt: number;
  tags: string[];
}

export interface Strategy {
  id: string;
  name: string;
  market: string;
  timeframe: string;
  thesis: string;
  entryCriteria: string[];
  exitCriteria: string[];
  maxRiskPct: number;
  updatedAt: number;
}

export interface StrategyStats {
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  expectancy: number;
  avgRisk: number;
  bestR: number;
  worstR: number;
}

export type ViewKey =
  | "home"
  | "analyze"
  | "flow"
  | "rules"
  | "strategy-review"
  | "strategy-change"
  | "journal";
