cd ~/trading-intelligence/apps/web

cat > src/App.tsx <<'EOF'
import './App.css'

function App() {
  return (
    <main className="site">

      {/* NAVBAR */}
      <nav className="navbar">
        <div className="brand">
          <div className="brand-icon">T</div>
          <span>Trading Intelligence</span>
        </div>

        <div className="nav-links">
          <a href="#features">Features</a>
          <a href="#how-it-works">How it works</a>
          <a href="#about">About</a>
        </div>

        <a className="nav-button" href="#download">
          Get Extension
        </a>
      </nav>

      {/* HERO */}
      <section className="hero-section">
        <div className="hero-content">

          <div className="badge">
            <span className="badge-dot" />
            AI-powered market intelligence
          </div>

          <h1>
            Turn financial news
            <br />
            into <span>market intelligence.</span>
          </h1>

          <p className="hero-description">
            Trading Intelligence analyzes financial news, market commentary,
            and selected text directly from your browser — helping you
            understand market sentiment and potential signals faster.
          </p>

          <div className="hero-actions">
            <a className="primary-button" href="#download">
              Get the Chrome Extension
              <span>→</span>
            </a>

            <a className="secondary-button" href="#how-it-works">
              See how it works
            </a>
          </div>

          <div className="trust-row">
            <span>✓ AI-assisted analysis</span>
            <span>✓ Real-time workflow</span>
            <span>✓ Built for traders</span>
          </div>

        </div>

        {/* PRODUCT PREVIEW */}
        <div className="hero-card">

          <div className="window-top">
            <div className="window-dots">
              <span />
              <span />
              <span />
            </div>

            <div className="window-title">
              Trading Intelligence
            </div>
          </div>

          <div className="analysis-card">

            <div className="analysis-label">
              SELECTED MARKET TEXT
            </div>

            <p className="selected-text">
              Apple reported stronger than expected earnings, driven by
              resilient iPhone demand and improving services revenue.
            </p>

            <button className="analyze-btn">
              Analyze
              <span>✦</span>
            </button>

            <div className="result">

              <div className="result-header">
                <span>AI Analysis</span>
                <span className="bullish">
                  BULLISH
                </span>
              </div>

              <div className="confidence">
                <div>
                  <small>Confidence</small>
                  <strong>87%</strong>
                </div>

                <div className="confidence-bar">
                  <div />
                </div>
              </div>

              <div className="result-summary">
                <small>Summary</small>

                <p>
                  Positive market signals detected. Earnings strength may
                  support favorable sentiment.
                </p>
              </div>

              <div className="signals">

                <small>Key Signals</small>

                <div className="signal">
                  Positive earnings catalyst
                </div>

                <div className="signal">
                  Strong demand indicators
                </div>

                <div className="signal">
                  Validate with price &amp; volume
                </div>

              </div>

            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="features-section">

        <div className="section-heading">
          <span>WHY TRADING INTELLIGENCE</span>

          <h2>
            Information is everywhere.
            <br />
            Signal is not.
          </h2>
        </div>

        <div className="feature-grid">

          <div className="feature-card">
            <div className="feature-number">
              01
            </div>

            <h3>
              Select &amp; Analyze
            </h3>

            <p>
              Highlight financial text on any supported webpage and send it
              directly to Trading Intelligence.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-number">
              02
            </div>

            <h3>
              AI Market Analysis
            </h3>

            <p>
              Get sentiment, confidence, summaries, and important market
              signals from the selected information.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-number">
              03
            </div>

            <h3>
              Make Better Decisions
            </h3>

            <p>
              Combine AI-generated signals with price, volume, and your own
              research before making a trading decision.
            </p>
          </div>

        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="workflow-section">

        <div className="workflow-copy">

          <span className="section-label">
            HOW IT WORKS
          </span>

          <h2>
            From article to insight in seconds.
          </h2>

          <p>
            Trading Intelligence sits alongside your research workflow.
            Instead of copying financial news into another AI tool, analyze
            it directly where you find it.
          </p>

        </div>

        <div className="steps">

          <div className="step">
            <span>01</span>

            <div>
              <h3>
                Find information
              </h3>

              <p>
                Read financial news, reports, commentary or analysis.
              </p>
            </div>
          </div>

          <div className="step">
            <span>02</span>

            <div>
              <h3>
                Select the text
              </h3>

              <p>
                Highlight the information you want to investigate.
              </p>
            </div>
          </div>

          <div className="step">
            <span>03</span>

            <div>
              <h3>
                Analyze
              </h3>

              <p>
                Receive AI-powered sentiment and market signals.
              </p>
            </div>
          </div>

        </div>
      </section>

      {/* DOWNLOAD */}
      <section id="download" className="download-section">

        <div>
          <span className="section-label">
            EARLY ACCESS
          </span>

          <h2>
            Build your research
            <br />
            workflow with AI.
          </h2>

          <p>
            Trading Intelligence is currently being developed as an
            AI-assisted market research platform.
          </p>
        </div>

        <a className="primary-button large" href="#">
          Get the Extension
          <span>→</span>
        </a>

      </section>

      {/* FOOTER */}
      <footer id="about" className="footer">

        <div className="brand">
          <div className="brand-icon">
            T
          </div>

          <span>
            Trading Intelligence
          </span>
        </div>

        <p>
          AI-assisted market intelligence.
        </p>

        <span>
          © 2026 Trading Intelligence
        </span>

      </footer>

    </main>
  )
}

export default App
EOF