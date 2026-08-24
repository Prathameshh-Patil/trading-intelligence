/**
 * Clicking the toolbar icon opens the side panel instead of a popup.
 * Registered on install and on every service-worker start, since the worker
 * is torn down when idle.
 */
const enableSidePanel = () => {
  chrome.sidePanel
    ?.setPanelBehavior({ openPanelOnActionClick: true })
    .catch(() => {
      // Chrome < 114 has no sidePanel API. Nothing to fall back to here.
    });
};

chrome.runtime.onInstalled.addListener(enableSidePanel);
enableSidePanel();
