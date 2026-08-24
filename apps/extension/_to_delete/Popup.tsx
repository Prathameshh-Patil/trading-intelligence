import { useCallback, useEffect, useState } from "react";
import "./Popup.css";

const API_BASE = "http://127.0.0.1:8000/api/v1";

interface AnalyzeResult {
  sentiment: string;
  confidence: number;
  summary: string;
  signals: string[];
}

interface StoredSelection {
  selectedText?: string;
  selectedUrl?: string;
  selectedTitle?: string;
  selectedAt?: number;
}

const hasChromeStorage = () =>
  typeof chrome !== "undefined" && !!chrome.storage?.local;

const hasChromeRuntime = () =>
  typeof chrome !== "undefined" && !!chrome.runtime?.onMessage;

function sentimentClass(sentiment: string): "bullish" | "bearish" | "neutral" {
  const s = sentiment.toLowerCase();
  if (s.includes("bull")) return "bullish";
  if (s.includes("bear")) return "bearish";
  return "neutral";
}

function hostnameFromUrl(url?: string): string {
  if (!url) return "";

  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function Popup() {
  const [selection, setSelection] = useState<StoredSelection>({});
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const loadSelection = useCallback(() => {
    if (!hasChromeStorage()) return;

    chrome.storage.local.get(
      ["selectedText", "selectedUrl", "selectedTitle", "selectedAt"],
      (items) => {
        setSelection(items as StoredSelection);
      },
    );
  }, []);

  useEffect(() => {
    loadSelection();

    if (!hasChromeRuntime()) return;

    const handleMessage = (message: { type?: string }) => {
      if (message?.type === "TEXT_SELECTED") {
        loadSelection();
        setResult(null);
        setStatus("idle");
        setError(null);
      }
    };

    chrome.runtime.onMessage.addListener(handleMessage);

    return () => {
      chrome.runtime.onMessage.removeListener(handleMessage);
    };
  }, [loadSelection]);

  const handleAnalyze = async () => {
    if (!selection.selectedText) return;

    setStatus("loading");
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: selection.selectedText,
          url: selection.selectedUrl,
          title: selection.selectedTitle,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }

      const data = (await response.json()) as AnalyzeResult;
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach the analysis service.",
      );
      setStatus("error");
    }
  };

  const hasSelection = Boolean(selection.selectedText);
  const hostname = hostnameFromUrl(selection.selectedUrl);
  const confidencePct = result
    ? Math.min(Math.max(result.confidence, 0), 100)
    : 0;

  return (
    <main className="popup">
      <header className="popup-header">
        <div className="brand">
          <div className="brand-icon">T</div>
          <span>Trading Intelligence</span>
        </div>
      </header>

      {!hasSelection && (
        <div className="empty-state">
          <p>No text selected yet.</p>
          <p className="hint">
            Highlight financial news or commentary on any webpage, then
            reopen this popup to analyze it.
          </p>
        </div>
      )}

      {hasSelection && (
        <div className="analysis-card">
          <div className="analysis-label">SELECTED MARKET TEXT</div>

          <p className="selected-text">{selection.selectedText}</p>

          {(hostname || selection.selectedTitle) && (
            <div className="source-row">
              from {selection.selectedTitle || hostname}
            </div>
          )}

          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Analyzing…" : "Analyze"}
            <span>✦</span>
          </button>

          {status === "error" && error && (
            <div className="error-box">
              {error}. Is the API running on http://127.0.0.1:8000?
            </div>
          )}

          {result && (
            <div className="result">
              <div className="result-header">
                <span>AI Analysis</span>
                <span className={sentimentClass(result.sentiment)}>
                  {result.sentiment.toUpperCase()}
                </span>
              </div>

              <div className="confidence">
                <div>
                  <small>Confidence</small>
                  <strong>{Math.round(result.confidence)}%</strong>
                </div>

                <div className="confidence-bar">
                  <div style={{ width: `${confidencePct}%` }} />
                </div>
              </div>

              <div className="result-summary">
                <small>Summary</small>
                <p>{result.summary}</p>
              </div>

              <div className="signals">
                <small>Key Signals</small>

                {result.signals.map((signal) => (
                  <div className="signal" key={signal}>
                    {signal}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <footer className="popup-footer">
        <span>v0.1.0</span>
      </footer>
    </main>
  );
}

export default Popup;
