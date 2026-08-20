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

// Firefox exposes the promise-based API as `browser`; its `chrome` shim is
// callback-based and would make every `await` below resolve to undefined.
// Chrome only has `chrome`, and the two are shape-compatible for what we use.
const g = globalThis as { browser?: typeof chrome; chrome?: typeof chrome }
const ext = g.browser ?? g.chrome

// Runs in the page, not here — it must not close over anything in this file.
const readSelection = () => window.getSelection()?.toString().trim() ?? ''

function App() {
  const [selection, setSelection] = useState<Selection>({ text: '' })
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // `pnpm dev` serves the popup as a plain page, where neither API exists.
    if (!ext?.scripting) {
      return
    }

    // Opening the popup is the gesture that activates activeTab, so the page can
    // only be read from here — there is no standing permission on any site.
    const load = async () => {
      const [tab] = await ext.tabs.query({ active: true, currentWindow: true })

      if (!tab?.id) {
        return
      }

      const [injected] = await ext.scripting.executeScript({
        target: { tabId: tab.id },
        func: readSelection,
      })

      setSelection({
        text: injected.result ?? '',
        url: tab.url,
        title: tab.title,
      })
    }

    // Chrome refuses injection into chrome://, the Web Store and PDF viewers.
    load().catch(() =>
      setError('This page does not allow reading the selection.'),
    )
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
