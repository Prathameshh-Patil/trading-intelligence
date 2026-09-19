/**
 * `@vision-hub/core`'s licence store over `chrome.storage`, with an alarm
 * for the six-hourly re-check.
 *
 * An alarm rather than `setTimeout` because the service worker does not live
 * six hours -- Chrome stops it after thirty idle seconds -- and an alarm
 * wakes it. `RECHECK_MS` is the same six hours the desktop uses.
 */

import { createLicenceStore, type LicenceStorage, type LicenceState } from "@vision-hub/core";

import { ext } from "../browser";
import { apiBaseOf, read, write } from "../storage";

const RECHECK_ALARM = "vh.licence.recheck";

const storage: LicenceStorage = {
  loadKey: async () => (await read()).licenceKey,
  saveKey: (licenceKey) => write({ licenceKey }),
  clearKey: () => write({ licenceKey: null }),
  loadLastValidAt: async () => (await read()).lastValidAt,
  saveLastValidAt: (lastValidAt) => write({ lastValidAt }),
};

// The store asks synchronously; the override is cached from storage on start
// and on every change so the answer is current without an await.
let apiBase: string | null = null;
export async function refreshApiBase(): Promise<void> {
  apiBase = apiBaseOf(await read());
}

export const store = createLicenceStore({
  storage,
  apiBase: () => apiBase,
  setTimer: (fn, ms) => {
    void ext.alarms.create(RECHECK_ALARM, { when: Date.now() + ms });
    const listener = (a: chrome.alarms.Alarm) => {
      if (a.name === RECHECK_ALARM) fn();
    };
    ext.alarms.onAlarm.addListener(listener);
    return () => {
      ext.alarms.onAlarm.removeListener(listener);
      void ext.alarms.clear(RECHECK_ALARM);
    };
  },
});

/** Mirror the state into storage so popup and panels read it without a round trip. */
export function publishState(listener: (s: LicenceState) => void): void {
  store.subscribe(() => listener(store.getState()));
  listener(store.getState());
}
