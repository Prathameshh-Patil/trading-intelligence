import { useEffect, useState } from 'react'
import './App.css'

const API = 'http://localhost:8000/api/v1/analyze'

type Analysis = {
  sentiment: 'bullish' | 'bearish' | 'neutral'
  confidence: number
  summary: string
  signals: string[]
}

type Selection = {
  text: string
  url?: string
  title?: string
}

// What the content script writes into chrome.storage.local.
type Stored = {
  selectedText?: string
  selectedUrl?: string
  selectedTitle?: string
}

function App() {
  const [selection, setSelection] = useState<Selection>({ text: '' })
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // `pnpm dev` serves the popup as a plain page, where chrome.* does not exist.
    if (typeof chrome === 'undefined' || !chrome.storage) {
      return
    }

    chrome.storage.local
      .get(['selectedText', 'selectedUrl', 'selectedTitle'])
      .then((stored) => {
        // chrome.storage resolves to unknown values; the content script writes strings.
        const { selectedText, selectedUrl, selectedTitle } = stored as Stored

        setSelection({
          text: selectedText ?? '',
          url: selectedUrl,
          title: selectedTitle,
        })
      })
  }, [])

  const analyze = async () => {
    setBusy(true)
    setError('')
    setAnalysis(null)

    try {
      const response = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selection),
      })

      if (!response.ok) {
        throw new Error(`Analysis unavailable (HTTP ${response.status})`)
      }

      setAnalysis(await response.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="popup">
      <header className="popup-header">
        <span className="dot" />
        Trading Intelligence
      </header>

      <section className="selection">
        <h2>Selected text</h2>

        {selection.text ? (
          <p className="selection-text">{selection.text}</p>
        ) : (
          <p className="empty">
            Highlight text on a page, then reopen this popup.
          </p>
        )}

        {selection.title && <p className="source">{selection.title}</p>}
      </section>

      <button
        className="analyze-btn"
        onClick={analyze}
        disabled={!selection.text || busy}
      >
        {busy ? 'Analyzing…' : 'Analyze'}
      </button>

      {error && <p className="error">{error}</p>}

      {analysis && (
        <section className="result">
          <div className={`sentiment ${analysis.sentiment}`}>
            {analysis.sentiment}
          </div>

          <div className="confidence">
            <div className="confidence-row">
              <span>Confidence</span>
              <strong>{analysis.confidence}%</strong>
            </div>

            <div className="confidence-bar">
              <div style={{ width: `${analysis.confidence}%` }} />
            </div>
          </div>

          <p className="summary">{analysis.summary}</p>

          <ul className="signals">
            {analysis.signals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

export default App
