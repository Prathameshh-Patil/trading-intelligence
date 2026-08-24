import type { JournalEntry, Strategy, TradeRule } from "./types";

/**
 * Single seam between the UI and persistence.
 *
 * In the extension this is chrome.storage.local. On a plain localhost dev
 * server (or any page without the chrome APIs) it transparently falls back to
 * window.localStorage and seeds demo data, so the whole UI stays interactive
 * outside of Chrome. Swapping either backend for real HTTP calls later means
 * editing only this file.
 */

const NS = "ti:";

export const isExtension = (): boolean =>
  typeof chrome !== "undefined" && !!chrome.storage?.local;

async function readRaw<T>(key: string): Promise<T | undefined> {
  if (isExtension()) {
    const items = await chrome.storage.local.get(key);
    return items[key] as T | undefined;
  }

  try {
    const raw = window.localStorage.getItem(NS + key);
    return raw ? (JSON.parse(raw) as T) : undefined;
  } catch {
    return undefined;
  }
}

async function writeRaw<T>(key: string, value: T): Promise<void> {
  if (isExtension()) {
    await chrome.storage.local.set({ [key]: value });
    return;
  }

  try {
    window.localStorage.setItem(NS + key, JSON.stringify(value));
  } catch {
    // Storage full or blocked (private window). Non-fatal for a preview.
  }
}

/** Read a key, writing and returning `fallback` the first time it is missing. */
async function readOrSeed<T>(key: string, fallback: T): Promise<T> {
  const existing = await readRaw<T>(key);

  if (existing === undefined) {
    await writeRaw(key, fallback);
    return fallback;
  }

  return existing;
}

const KEYS = {
  rules: "rules",
  journal: "journal",
  strategy: "strategy",
} as const;

/* ------------------------------------------------------------------ */
/* Defaults                                                            */
/* ------------------------------------------------------------------ */

export const DEFAULT_RULES: TradeRule[] = [
  {
    id: "max-trades-day",
    label: "Max 3 trades per day",
    detail: "Overtrading is the fastest way to give back an edge.",
    severity: "hard",
    enabled: true,
    limit: 3,
  },
  {
    id: "max-risk",
    label: "Risk 2% per trade",
    detail: "No single idea should be able to define the month.",
    severity: "hard",
    enabled: true,
    limit: 2,
  },
  {
    id: "consecutive-losses",
    label: "Stop after 2 consecutive losses",
    detail: "Two in a row means the read is wrong, not the size.",
    severity: "hard",
    enabled: true,
    limit: 2,
  },
  {
    id: "no-revenge",
    label: "No re-entry within 30 min of a loss",
    detail: "Creates a cooling-off gap between an exit and the next entry.",
    severity: "soft",
    enabled: true,
    limit: 30,
  },
  {
    id: "session-window",
    label: "Trade only 9:30 - 11:30",
    detail: "Stay inside the window where the plan was actually tested.",
    severity: "soft",
    enabled: true,
  },
  {
    id: "journal-every-trade",
    label: "Journal every trade",
    detail: "An untracked trade cannot be reviewed or improved.",
    severity: "soft",
    enabled: true,
  },
];

export const DEFAULT_STRATEGY: Strategy = {
  id: "default",
  name: "Opening Range Momentum",
  market: "US equities / large-cap tech",
  timeframe: "5m execution, 1h context",
  thesis:
    "Trade continuation out of the first-hour range when a catalyst and relative strength agree. Skip the session entirely when neither is present.",
  entryCriteria: [
    "Price breaks the 30-minute opening range on rising volume",
    "Stock shows relative strength against its index",
    "A catalyst exists (earnings, guidance, sector news)",
  ],
  exitCriteria: [
    "Stop below the opening-range midpoint",
    "Scale 50% at 1R, trail the remainder",
    "Flat before the close - no overnight risk",
  ],
  maxRiskPct: 2,
  updatedAt: Date.now(),
};

const HOUR = 60 * 60 * 1000;

/** Demo journal used for the first run and the standalone preview. */
function seedJournal(): JournalEntry[] {
  const now = Date.now();

  return [
    {
      id: "j1",
      symbol: "NVDA",
      side: "long",
      outcome: "win",
      riskPct: 1.5,
      rMultiple: 2.4,
      note: "Clean break of the opening range with volume confirmation. Scaled at 1R, trailed the rest into the afternoon.",
      openedAt: now - 2 * HOUR,
      tags: ["momentum", "planned"],
    },
    {
      id: "j2",
      symbol: "AAPL",
      side: "long",
      outcome: "loss",
      riskPct: 1.8,
      rMultiple: -1,
      note: "Entered before the range was actually set. Stopped at the midpoint exactly as written in the plan.",
      openedAt: now - 5 * HOUR,
      tags: ["early-entry"],
    },
    {
      id: "j3",
      symbol: "TSLA",
      side: "short",
      outcome: "loss",
      riskPct: 2.6,
      rMultiple: -1.3,
      note: "Sized up to make back the previous loss. Broke the risk rule and it cost more than the original trade.",
      openedAt: now - 6 * HOUR,
      tags: ["revenge", "oversized"],
    },
    {
      id: "j4",
      symbol: "MSFT",
      side: "long",
      outcome: "win",
      riskPct: 1.2,
      rMultiple: 1.8,
      note: "Textbook setup. Catalyst, relative strength, and a tight stop under the midpoint.",
      openedAt: now - 28 * HOUR,
      tags: ["momentum", "planned"],
    },
    {
      id: "j5",
      symbol: "AMD",
      side: "long",
      outcome: "win",
      riskPct: 1.4,
      rMultiple: 0.9,
      note: "Took the scale at 1R and the runner gave most of it back. Fine - the rule fired correctly.",
      openedAt: now - 32 * HOUR,
      tags: ["momentum"],
    },
  ];
}

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

export const getRules = () => readOrSeed(KEYS.rules, DEFAULT_RULES);
export const saveRules = (rules: TradeRule[]) => writeRaw(KEYS.rules, rules);

export const getStrategy = () => readOrSeed(KEYS.strategy, DEFAULT_STRATEGY);
export const saveStrategy = (strategy: Strategy) =>
  writeRaw(KEYS.strategy, { ...strategy, updatedAt: Date.now() });

export const getJournal = () => readOrSeed(KEYS.journal, seedJournal());
export const saveJournal = (entries: JournalEntry[]) =>
  writeRaw(KEYS.journal, entries);

export async function addJournalEntry(
  entry: Omit<JournalEntry, "id">,
): Promise<JournalEntry[]> {
  const entries = await getJournal();

  const next: JournalEntry = {
    ...entry,
    id: `j${Date.now().toString(36)}`,
  };

  const updated = [next, ...entries];
  await saveJournal(updated);

  return updated;
}

export async function deleteJournalEntry(id: string): Promise<JournalEntry[]> {
  const entries = await getJournal();
  const updated = entries.filter((entry) => entry.id !== id);

  await saveJournal(updated);
  return updated;
}
