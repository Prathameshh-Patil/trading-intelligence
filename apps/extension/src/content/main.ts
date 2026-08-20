const getSelectedText = (): string => {
  return window.getSelection()?.toString().trim() ?? "";
};

const saveSelection = async (): Promise<void> => {
  const text = getSelectedText();

  if (!text) {
    return;
  }

  await chrome.storage.local.set({
    selectedText: text,
    selectedUrl: window.location.href,
    selectedTitle: document.title,
    selectedAt: Date.now(),
  });

  chrome.runtime.sendMessage({
    type: "TEXT_SELECTED",
    text,
  }).catch(() => {
    // Popup may not be open. This is expected.
  });

  console.log("Trading Intelligence: selected text saved", text);
};

document.addEventListener("mouseup", () => {
  setTimeout(saveSelection, 50);
});

console.log("Trading Intelligence content script loaded");