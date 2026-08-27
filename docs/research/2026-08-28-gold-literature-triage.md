# Reading triage — *Gold Quant Trading Research Papers* (and what it leaves out)

**Written 2026-08-28.** Source document: `Gold Quant Trading Research Papers.pdf`, 23 pages,
untracked at the repo root. Triaged against what `services/signal-data` actually is — GC minute
bars, order-flow features, a 5-minute kill gate, unsupervised regimes, walk-forward — not against
what a gold desk in general might want.

Two claims this file makes, and both matter more than the reading list:

1. **The PDF is an AI-generated survey, not research.** Its tables are a lossy index and several of
   their numbers are unverifiable. **The list of 53 URLs on pp.21–23 is the only load-bearing part.**
2. **The PDF does not contain this project's literature.** It has five pillars and none of them is
   market microstructure. Every feature in `strategies.py` already has a name and a primary source
   somewhere else, and §4 below is where those are. That section is the reason this file exists;
   §1–§3 are triage of what was handed to us.

---

## 0. How to read the source document

It is structured as five "pillars" with fifty numbered entries and a works-cited list.

| Pages | Section | Verdict |
| :--- | :--- | :--- |
| 1–5 | Pillar 1 — Time-series momentum, vol-scaled sizing | Skim. One equation worth keeping (§2) |
| 5–8 | Pillar 2 — GC/SI cointegration, Kalman hedge ratios | **Skip.** Wrong instrument, wrong frequency |
| **8–12** | **Pillar 3 — HF intraday momentum and microstructure** | **Read. This is our domain** |
| 12–16 | Pillar 4 — Volatility forecasting, regime switching | Read the three entries in §3 |
| 16–19 | Pillar 5 — LSTM, Transformers, FinBERT, DBN | **Skip**, one exception in §3 |
| 20 | Applicability — costs, Kelly, capacity | **Read. Two paragraphs, both bear on `backtest.py`** |
| 21–23 | Works cited, 53 URLs | The actual deliverable |

**Reliability.** Entry #23's ORB claim rests on a **studocu bachelor thesis** (cite #29). Cites #5,
#12 and #40 are Scribd re-uploads of other people's papers. Cite #39 is a broken PDF-viewer URL to a
"2026 expected price trends" page and is not research. Cite #42's publisher (SCIRP) is low-tier. The
headline figures in Pillar 5 — "171% in three months", "MAE of 0.21" — trace to arXiv preprints and
ResearchGate uploads with no out-of-sample discipline described. **Chase the primary source or do
not use the claim.** Precedent: the version-lock PDF, whose host-tool versions were fabricated.

---

## 1. Read now — Pillar 3, pp.8–12

The only pillar operating at our frequency on our kind of data.

| Entry | Page | Cite | What to take |
| :--- | :--- | :--- | :--- |
| **#22 Realized semivariance and momentum reversals** | 9 (math), 10 | #33 | `RS⁺ = Σ r²·1(r>0)`, `RS⁻ = Σ r²·1(r<0)`. **Computable from `gc_trades.parquet` today** and shaped exactly like the four rules already in `strategies.py`: fade when RS⁺ reaches an extreme against RS⁻. The closest thing in this document to a fifth Stage 1 candidate |
| **#24 Intraday overreaction, 1-min to 1-hr** | 10 | #34 — `pmc.ncbi.nlm.nih.gov/articles/PMC9759686` | Peer-reviewed, **free full text, and the only cited paper working at our horizon.** Non-parametric turning-point detection is an alternative to the trailing z-score windows in `_window` |
| **#21 Intraday time-series momentum** | 10 | #30 / #35 — MPRA 97134 | First half-hour return predicts last half-hour. Says `regimes.py`'s `session_phase` is a **signal**, not only a conditioning variable |
| **#28 5-minute jumps around macro announcements** | 11 | #38 | **A kill-gate hazard, not a strategy.** July 2026 contains CPI and NFP prints. If Stage 1 entries cluster on announcement bars, a 5-minute edge is an event artifact rather than an order-flow one — and Day 5 already showed the month is a random walk at 5m, which is precisely the condition under which a handful of event bars can carry a whole result. Cheap to check: tag entries by distance to the nearest release and report the split. **Worth doing before Part B is judged, not after** |
| #29 Realized skewness as a factor | 12 | #38 | Same family as #22 and the same data. Second in line behind it |
| #30 Spot-vs-futures lead-lag | 12 | #39, #41 | Recorded only. A2 was cut 25 Aug and spot gold has no centralised volume; nothing here revives it |

## 2. Read now — Applicability, p.20

Two paragraphs, and the first is the most consequential thing in the document for us.

- **Costs, and where they belong.** `backtest.py` reports ticks gross — no spread, no commission.
  The page's point is that the fix for a threshold-triggered strategy is to **widen the threshold to
  cover the round trip**, not to subtract cost from the result at the end. The two are not the same
  operation: the second leaves the entry population unchanged and quietly reports trades that were
  never worth taking. On GC one tick is $10 and `daily_updates/2026-08-28.md` already prices the
  round turn at ~$25 — which moved break-even from 22.2% to 25.0% and was load-bearing in that day's
  finding. **This is the same number arriving in a second place.**
- **Fractional Kelly scaled by a volatility forecast, and capacity.** Not this week. It names what
  `horizon.py`'s σ work eventually feeds, and it is the honest reason Pillar 5's return figures are
  not comparable to anything we will produce.

One equation from **Pillar 1, p.2** is worth carrying even though the pillar is skimmable:
`X_t = S_t · σ_target / σ_t`. Volatility-scaled sizing, and the survey's own claim is that removing
the scaling drops the alpha from 1.27%/month to 0.41%. Whatever the exact numbers, the shape is the
point: **the sizing rule is not a wrapper on the signal, it is most of the result.**

## 3. Read before `regimes.py` is defended — Pillar 4, pp.12–16

We cluster K-Means on trailing state features. The literature's answer to the same question is a
Markov-switching or HAR volatility model. **We do not have to adopt either.** But "why not
MS-GARCH?" is the first question a domain reviewer asks, and §6.2 means the answer wants to be
committed *before* anyone looks at per-regime performance.

- **#31 MRS-GARCH** (p.14, cite #43) — regime-switching volatility, the direct competitor to our
  clustering.
- **#33 HAR-RV** (p.14) — realized volatility as daily + weekly + monthly components. Read the
  primary source instead: **Corsi (2009)**, not the summary.
- **#34 HAR-V-J** (p.14, cite #36) — adds a jump component. Connects straight back to the
  announcement problem in §1.

**The one thing worth reading in Pillar 5**, and it is for the other half of the repo:
**cite #45, "Can FinBERT2-Based Investor Sentiment Predict Gold Futures"**
(`mdpi.com/2227-7072/14/8/225`), plus entry #35 on p.14 (sentiment-driven HAR-RV, asymmetric —
negative sentiment moves volatility, positive does not). `services/api/app/analysis.py` is a
sentiment scorer. If anyone ever claims that score is *predictive* rather than descriptive, this is
the literature that would have to carry it, and it is a much weaker claim than the product copy
would want.

**Skip Pillar 2 entirely** (GC/SI cointegration, Kalman hedge ratios, pp.5–8). Real literature,
wrong problem: daily-bar pairs trading needs SI, we pull GC only, and NQ was dropped 25 Aug.

**Skip the rest of Pillar 5** (LSTM-GWO, Transformers, DBN, EMD-LSTM, pp.16–19). Twenty-three
sessions cannot train any of it, and Stage 1 is deliberately not an ML problem.

---

## 4. What the PDF does not contain

**Every feature in `strategies.py` already has a name in the microstructure literature, and this
survey names none of them.** That is its largest omission and the reason it reads as a gold
document rather than an order-flow one.

### 4.1 Our own features, under their real names

| Ours | Its name in the literature | Primary source |
| :--- | :--- | :--- |
| `absorption` — contracts per tick of range | **Kyle's lambda**, inverted. Price impact per unit of signed volume | Kyle, *Continuous Auctions and Insider Trading*, Econometrica 1985 |
| `delta_z` — bar delta vs its trailing distribution | A coarse **order-flow imbalance (OFI)**. OFI is defined on book events rather than trades and is close to linear in price change | Cont, Kukanov & Stoikov, *The Price Impact of Order Book Events*, J. Financial Econometrics 2014 |
| `absorption_fade` — heavy volume, small range | **Flow toxicity / VPIN.** Also a natural *regime* variable, better motivated than generic realized vol | Easley, López de Prado & O'Hara, *Flow Toxicity and Liquidity in a High-Frequency World*, RFS 2012 |
| `backtest.evaluate` — MFE/MAE at fixed horizons | The **triple-barrier method**, with the vertical barrier only | López de Prado, *Advances in Financial Machine Learning*, Ch. 3 |
| `pull_tbbo_validate.py` — the quote rule | **Lee–Ready**, and the 99.65% agreement has a published comparison set | Lee & Ready, *Inferring Trade Direction from Intraday Data*, JF 1991; Ellis, Michaely & O'Hara, JFQA 2000 |

Naming them costs nothing and buys two things: the mechanism (why signed flow predicts anything at
all) and a defence when Shreyas asks where a feature came from.

- **Bouchaud, Bonart, Donier & Gould, *Trades, Quotes and Prices* (CUP, 2018)** is the reference
  text for all of the above — order flow autocorrelation, impact, why aggressor-signed volume
  carries information. If one book gets read for the *signal* side, this is it.

### 4.2 The methodology gap, which is the more urgent one

`thresholds_selector.md` was written to guard against exactly this and cites no literature for it.
**López de Prado, *Advances in Financial Machine Learning* (Wiley, 2018)** is the direct match, and
four chapters map onto open questions in this repo:

- **Ch. 2 — bars.** We use 5-minute time bars. Tick, volume and dollar bars have better statistical
  properties precisely because time bars sample slowly in fast markets. `horizon.py` measured the
  5-minute grid as costing ~1.1% on σ; the chapter says what the alternative would have been.
- **Ch. 4 — sample uniqueness.** **This one is a live defect.** 30-minute horizons on 5-minute bars
  produce heavily overlapping labels; those observations are not independent, and any significance
  test that assumes they are overstates its confidence. `daily_updates/2026-08-28.md` computed the
  separable hit rate from a binomial with N = 50/100/150 — **the effective N is lower than the
  nominal N**, so those bars (34.0% / 30.5% / 29.0%) are optimistic. The chapter gives the
  uniqueness weighting that corrects it.
- **Ch. 7 — purged K-fold with embargo.** Our walk-forward is a single half-split (§6.4, ~11 and ~11
  sessions). With overlapping labels, the boundary leaks unless it is purged and embargoed.
- **Ch. 11 & 14 — backtest overfitting and the deflated Sharpe ratio.**

And on the multiple-testing problem the selector *is* — four strategies × two or three regimes ×
three horizons:

- **Bailey & López de Prado, *The Deflated Sharpe Ratio* (JPM, 2014)** — deflates a Sharpe by the
  number of trials that produced it, and gives the minimum backtest length below which a result is
  not demonstrable. **It answers, in general, the question Day 6 answered by hand for one metric.**
- **Bailey, Borwein, López de Prado & Zhu, *Pseudo-Mathematics and Financial Charlatanism* (Notices
  of the AMS, 2014)** — short, free, and the plainest statement of why a pre-committed threshold is
  the only defence. Worth putting in front of all three of us, not just the signal lane.
- **Harvey & Liu, *Backtesting* (JPM, 2015)** — haircutting a Sharpe for the number of tests run.

### 4.3 Better sources for two things the PDF gestures at

- **Opening Range Breakout.** The PDF's only ORB source is a bachelor thesis. **Zarattini & Aziz**
  have published quantitative ORB studies on SSRN (2023–2024) with explicit cost modelling — a far
  better starting point if ORB ever becomes a candidate.
- **Intraday jumps.** The PDF says "non-parametric detection" without naming a test. **Lee &
  Mykland, *Jumps in Financial Markets* (RFS, 2008)** is a concrete, implementable intraday jump
  statistic, and it is the tool for the §1 announcement check. On the announcement effects
  themselves, **Andersen, Bollerslev, Diebold & Vega** is the standard reference.

### 4.4 Free data that is not price data

- **CFTC Commitments of Traders**, weekly, free. Pillar 1 leans on commercial hedging pressure as
  the *mechanism* behind trend in metals and then never uses the data that measures it. Positioning
  is a regime candidate that costs nothing and is not derived from our own price series — which
  matters, because §2's leakage rule is easiest to satisfy with an exogenous variable.
- **CME's GC contract specifications**, for the settlement window definition. `verify_settlement_close.py`
  already resolved the 12.2-point gap empirically; the spec is the citation for it.

---

## 5. If only three things get read

1. **`pmc.ncbi.nlm.nih.gov/articles/PMC9759686`** — free, peer-reviewed, 1-min to 15-min, our
   instrument class. The one paper in the PDF's bibliography that is about our actual problem.
2. **López de Prado, *AFML*, chapters 3, 4 and 7.** Chapter 4 says our current significance bars are
   optimistic, and that is a correction to a number already committed to `daily_updates/`.
3. **p.20 of the PDF, the costs paragraph** — because widening the threshold and subtracting cost at
   the end are different operations, and `backtest.py` currently does neither.

**Everything in §4 is cited from knowledge, not from a source in the repo. Verify each DOI before
any of it is quoted in a document Shreyas or a vendor sees.** The titles, authors and years are
offered as search terms with a stated confidence, and nothing here has been fetched, read or checked
against a publisher in this session. Nothing in §4 has been implemented, benchmarked, or shown to
help this project — it is a reading list, and that is all it is.
