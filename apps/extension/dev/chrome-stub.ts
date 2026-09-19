/**
 * Enough of `chrome.*` for the harness page: storage over `localStorage`
 * with `onChanged`, `runtime.sendMessage` wired straight to the worker's
 * `onMessage` listener (the worker's module is imported into the same page),
 * `alarms` over `setTimeout`, and `action.setBadgeText` into a DOM badge.
 * Dev only; never bundled into `dist/`.
 */

type Listener = (...args: unknown[]) => unknown;

const KEY = "vh.harness.storage";

function load(): Record<string, unknown> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Record<string, unknown>;
  } catch {
    return {};
  }
}

const changed = new Set<Listener>();
const messages = new Set<Listener>();
const alarms = new Set<Listener>();
const timers = new Map<string, number>();

export function installChromeStub(): void {
  // A normal Chrome page already has a `chrome` object (runtime.id and
  // little else); only a real extension context has `storage`.
  const existing = (globalThis as { chrome?: { storage?: unknown } }).chrome;
  if (existing?.storage) return;
  const chromeStub = {
    storage: {
      local: {
        async get(defaults: Record<string, unknown>) {
          return { ...defaults, ...load() };
        },
        async set(patch: Record<string, unknown>) {
          localStorage.setItem(KEY, JSON.stringify({ ...load(), ...patch }));
          for (const l of changed) l(patch, "local");
        },
      },
      onChanged: {
        addListener: (l: Listener) => changed.add(l),
        removeListener: (l: Listener) => changed.delete(l),
      },
    },
    runtime: {
      onInstalled: { addListener: () => {} },
      onStartup: { addListener: () => {} },
      onMessage: {
        addListener: (l: Listener) => messages.add(l),
        removeListener: (l: Listener) => messages.delete(l),
      },
      sendMessage(req: unknown) {
        return new Promise((resolve) => {
          for (const l of messages) l(req, {}, resolve);
        });
      },
    },
    alarms: {
      async create(name: string, info: { when?: number; delayInMinutes?: number }) {
        clearTimeout(timers.get(name));
        const ms = info.when ? Math.max(0, info.when - Date.now()) : (info.delayInMinutes ?? 0) * 60_000;
        timers.set(
          name,
          setTimeout(() => {
            for (const l of alarms) l({ name });
          }, ms) as unknown as number,
        );
      },
      async clear(name: string) {
        clearTimeout(timers.get(name));
        timers.delete(name);
      },
      onAlarm: {
        addListener: (l: Listener) => alarms.add(l),
        removeListener: (l: Listener) => alarms.delete(l),
      },
    },
    action: {
      async setBadgeText({ text }: { text: string }) {
        const el = document.getElementById("harness-badge");
        if (el) el.textContent = text ? `badge ${text}` : "badge —";
      },
      async setBadgeBackgroundColor() {},
    },
  };
  (globalThis as { chrome?: unknown }).chrome = chromeStub;
}
