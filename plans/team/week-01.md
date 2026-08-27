# Week 1 · rescheduled — Sat 5 Sep – Fri 11 Sep

**Supersedes the dates in [`phase-1-kill-week.md`](phase-1-kill-week.md), not its content.** The
kill week is the same week; it happens seven days later, because **nobody is working 29 Aug – 4 Sep.**

This file is the two-engineer schedule. It merges `phase-1-kill-week.md`'s gate with
`planfortoday.md`'s five layers, which are the concrete form the signal work has taken since that
file was written. Shreyas's lane is unchanged and is tracked in [`shreyas/`](shreyas/README.md).

| | |
| :--- | :--- |
| **Last working day before the gap** | Fri 28 Aug — today. Four things, below, and they are what make the gap free |
| **Gap** | Sat 29 Aug – Fri 4 Sep. Nobody works. No branch is left open across it |
| **Week 1** | Sat 5 Sep – Fri 11 Sep, seven consecutive days, both engineers full-time |
| **Gate** | Fri 11 Sep, 16:00 — the Week 1 gate from [`gates.md`](gates.md), unchanged in content |

**Everything downstream shifts one week right.** Week 12 ends **Fri 27 Nov**, not 20 Nov. The phase
files still carry the old dates; the shift table at the bottom of this file is authoritative until
they are rewritten.

---

## 1 · Today, Fri 28 Aug — the four things that make a seven-day gap cost nothing

A gap is only expensive if it lands in the middle of a dependency. Right now there are exactly two
dependencies between the two of you, and both can be closed today in about half a day each.

### Together · 30 minutes · freeze S2

Write `apps/desktop/src/lib/engine/types.ts` from [`contracts.md`](contracts.md) §S2 and commit it.
This was W1D1's joint half-hour. **Do it today instead**, because if it waits, Prathamesh's first
day back begins with a meeting and Varad's does not — which is the one thing this plan exists to
prevent.

⚠️ **`FeedCreds` is still undefined** — `plans/current.md` (Day 3, evening) records it as the reason
S2 could not be fully frozen. It is named in the `Engine` interface and typed nowhere. Define it in
the same half hour. It is a vendor credential bag; `{ vendor: string; user: string; secret: string }`
plus whatever quantfeed's answer adds later is enough to freeze, and a fake never needs more.

### Varad · ~4 hours

| | Work | Why it cannot wait a week |
| :--- | :--- | :--- |
| 1 | **The Week 0 gate, 16:00** — the four votes in [`varad/2026-08-28-gate-note.md`](varad/2026-08-28-gate-note.md) | Three of them have been carried since 25 Aug for a room with all three in it. This is that room, and the next one is 5 Sep |
| 2 | **Commit Part B** of `thresholds_selector.md` | `strategies.py` raises `TypeError` until it exists. Nothing is backtested before it, so it gates every one of Varad's seven days |
| 3 | **Commit the pre-written threshold** — see §2, it is not the number in `planfortoday.md` | The mechanism is the git timestamp. A threshold committed on 9 Sep, after Layer 4 has printed a hit rate, is a story |
| 4 | **Revoke the Anthropic key** — `current.md` item #0, ten minutes | It has been open since 25 Aug and it was in a chat transcript. It should not sit live through a week when nobody is watching |

### Prathamesh · ~4 hours

| | Work | Why it cannot wait a week |
| :--- | :--- | :--- |
| 1 | **Back up `data/gc_trades.parquet` off your machine** | 1,616,772 trades, $2.52, **the only copy on any machine**, and it underwrites every delta number in the project. It is about to sit through seven unattended days on one disk. Encrypted external drive or private object storage — not the repo, it stays gitignored |
| 2 | **Regenerate `analysis/regimes/` and commit the fresh labels** — the re-run command is in [`analysis/regimes/README.md`](../../services/signal-data/analysis/regimes/README.md) | **This is the hard blocker.** Varad's entire week reads that CSV, the committed one is off a five-feature matrix that no longer exists *and* off the straddling-window bug `d3c896f` fixed, and only you have the month. Ten minutes of compute; without it Varad's Day 1 is blocked on you |
| 3 | **Export the fixture session to JSON** for `engine/mock.ts` | Your Day 2 needs it and you can produce it yourself from the committed parquet. Do it today and Day 2 starts on code, not on data plumbing |
| 4 | **Fresh-clone check** — `git clone` into `/tmp`, `pnpm install`, `pnpm build:all`, `cargo build` | An hour now, a day in Week 6. ⛔ **Not `git clean -xdf` in this working copy** — `-x` deletes exactly the parquet in row 1 |

**Do not commit anything to `analysis/regimes/` by overwriting the old files silently.** They are the
§6.2 pre-commitment. The README already marks them superseded; land the new run alongside under a
distinct name (`..._k3_v2.csv` or a dated directory) so both exist.

### The rule for the gap

**Nothing is left half-finished on a branch.** Everything either lands on `main` today or is not
started. Both of you should be able to open a laptop cold on 5 Sep and start on Day 1's first line
without reading a handoff note or asking the other a question.

**Two things worth asking Shreyas to do *during* the gap**, because they are phone calls with long
turnarounds and he may not be blacked out: the three distribution-licence emails (nominally Mon 31
Aug — send them, replies land by 5 Sep) and the quantfeed / C1 vendor answer. Licensing in writing
from ≥1 vendor is a Week 1 gate line, and it is the one line neither engineer can move.

---

## 2 · The one number in `planfortoday.md` that has to change

`planfortoday.md` sets `hit_70_rate ≥ 25%` as the success metric, reasoning that 3.5:1 R/R
break-even sits at 23%. **Both numbers are right and the conclusion does not follow.**

For a driftless random walk, the probability of touching `+a` before `−b` is exactly `b/(a+b)`:

```
P(hit +70 before −20)  =  20/(70+20)  =  22.22%
break-even at 3.5:1    =  1/(1+3.5)   =  22.22%
```

These are the same number, and not by coincidence — **a fixed target/stop pair on a driftless random
walk always lands exactly on its own break-even.** So a 22.2% hit rate is what the tape hands you
for free, from a coin flip, with no signal in it at all. And `horizon.py` has already measured this
month to be a random walk at 5, 15 and 30 minutes, to within 0.1% on dispersion and within 0.01 on
overlap correlation.

Add costs and it gets worse. One tick of slippage each way plus commission is about $25 round turn
on a $700 winner and a $200 loser:

| Round-turn cost | Break-even hit rate |
| :--- | ---: |
| $0 | 22.2% |
| $15 | 23.9% |
| **$25** | **25.0%** |
| $40 | 26.7% |

**`planfortoday.md`'s 25% target is the break-even line after realistic costs.** Hitting it exactly
means the strategy earns zero and you have paid a month of work for a coin flip.

### What the threshold has to be instead

The bar is not an absolute hit rate. It is a **margin over the measured null, large enough to be
separable at the number of signals you actually get.** Against a null of 22.2%:

| Signals in the month | 1 s.e. | Smallest hit rate provable at 2σ |
| ---: | ---: | ---: |
| 50 | 5.88 pp | **34.0%** |
| 100 | 4.16 pp | **30.5%** |
| 150 | 3.39 pp | **29.0%** |
| 250 | 2.63 pp | 27.5% |
| 500 | 1.86 pp | 25.9% |
| 900 | 1.39 pp | 25.0% |

`planfortoday.md` targets 50–150 signals per month. **At that count nothing below ~29% is provable**,
and a true edge of 25% cannot be demonstrated on one month no matter how good it is.

**Drafted wording for the pre-written threshold, to commit today:**

> Stage 1 passes if, on the held-out half, `hit_70_rate` exceeds the measured random-entry null by
> at least `2 × sqrt(p₀(1−p₀)/N)` where `N` is the achieved signal count and `p₀` the measured null
> — and `N ≥ 100`. Below `N = 100` the result is **inconclusive**, which is reported and not acted
> on. `avg_mfe_mae_ratio ≥ 2.0` is descriptive and is never the thing the gate turns on.

Two things this preserves that a flat "≥25%" does not: the null is **measured, not assumed**
(`backtest.random_entries` already exists — do not write a second one), and *inconclusive* stays a
first-class outcome, which is what §6 of the design predicted in writing before any of this ran.

**It is also the third independent argument for buying more months.** `horizon.py` got there from
variance, §6 from cell counts, this from binomial power. Six months at roughly $15 puts 300–900
signals in reach, where the provable bar falls to 25–27%. That decision is item 4 of today's gate
and it is gated on the vendor, not on the money.

---

## 3 · The week · Sat 5 Sep – Fri 11 Sep

Two lanes. **Varad touches only `services/signal-data/`. Prathamesh touches only `apps/desktop/`.**
No shared file, no shared branch, no merge conflict possible. Two scheduled contacts in seven days:
neither is a handoff.

Every day below ends with one commit and one number you can say out loud.

---

### D1 · Sat 5 Sep

**V — Layers 1 and 2.** Load the regenerated month bar table. Build
`services/signal-data/features/regime_filter.py`: regime survival ≥ 0.92, an ATR(14) gate, a
session-edge filter dropping the first and last 5 minutes, and EMA(15) trend alignment. Tests per
gate. **Reuse `strategies.py`'s `_window` / `_align` machinery** — it already solves session-grouped
trailing windows, the empty-minute trap and the overnight-straddle trap, and re-solving them in a
second file is how the two quietly disagree.

> **Number:** X of 6,276 bars pass. Target band 15–25% (941–1,569). Above 50% the filter is
> decorative; below 5% there is nothing left to signal on.
>
> **Also measure and write down: the median 5-minute bar range in ticks.** `thresholds_selector.md`
> records 15 ticks at *minute* bars; the 5-minute figure is unmeasured, and a 20-tick stop against
> it is the single number that decides whether Day 4's measurement is even well-posed.

**P — the overlay skeleton.** Strip the Tauri window to the shell: six ported views at **380px
wide**, transparent, borderless, always-on-top. No overlay *behaviour* yet — today is the window.
`types.ts` was frozen on 28 Aug, so there is nothing to wait for.

> **Number:** six views render, zero console errors in the real webview, window geometry matching
> `tauri.conf.json` to the pixel.

*Nobody is blocked:* V reads a CSV committed on 28 Aug; P builds against a type committed on 28 Aug.

---

### D2 · Sun 6 Sep

**V — Layer 3's features.** `features/orderflow.py` (delta z, CVD slope, absorption ratio, VWAP)
and `features/expansion.py` (ATR, bar range, body ratio). **Most of orderflow already exists** as
`delta_z` and `cvd_slope` in `strategies.py` — import them, do not re-derive. New code is VWAP,
the absorption ratio and the expansion trio.

> **Number:** every feature's trailing distribution over the month — median, σ, and the NaN count in
> each session's opening bars. A feature that is NaN for the first 40 bars of every session has
> silently deleted the London open.

**P — `engine/mock.ts`, S2's fake.** Replay the fixture session at 10×, emit `DeltaBar` and
`Outlier`. **The part that matters is that it misbehaves on demand:** go `stale`, drop the
connection, emit a 7-digit CVD, emit a 40-character symbol. You write this and not Varad, because
you are the one who needs to find out today that the layout breaks on a 7-digit CVD rather than in
Week 3 against a live feed.

> **Number:** four failure modes triggerable from the UI, and a screenshot of the layout under each.

*Nobody is blocked:* the fixture JSON was exported on 28 Aug.

---

### D3 · Mon 7 Sep

**V — `signals/engine.py`.** The 3-of-4 checker over conditions A (absorption), B (delta
divergence), C (CVD momentum shift), D (range expansion), gated by Day 1's regime filter. Unit-test
each condition in isolation before the combiner. **If a condition is genuinely hard — absorption is
the likely one — stub it `return False`, commit that, and move on.** Day 4 will tell you whether it
mattered, which is cheaper than deciding today.

> **Number:** total signals; the breakdown by which three of four fired; signals per session.
> **Watch for clustering** — 90 signals in four sessions is not 90 independent observations, and
> Day 5's power arithmetic assumes independence it will not have.
>
> **The free test case, and it is a hard one:** on 2026-07-16 price fell 89 points while CVD closed
> **+1,842**, with the 08:00 ET hour showing delta **+1,083 against a 47.7-point drop**. That is
> textbook absorption. **If the detector does not flag that hour, it does not work** — and this is a
> Week 1 gate line, not an opinion.

**P — click-through.** Install the MT5 demo terminal. Float the overlay over it and get the hit-test
region right: transparent regions pass clicks through to MT5, opaque regions do not. Then, if it
lands early, take the **compositing measurement** (nominally W2): MT5's frame timing with the
overlay on and off. Nobody has published numbers on a transparent webview compositing over a
fast-redrawing chart.

> **Number:** click-through demonstrated into a live MT5 chart. Frame timing on/off, written down.

---

### D4 · Tue 8 Sep

**V — Layer 4, `analysis/mfe_mae.py`.** For each signal: MFE, MAE, `hit_70`, `time_to_70`.

Two decisions to take before writing it, both of which `planfortoday.md` leaves contradictory:

1. **The forward window is 6 bars, not 30.** The file says "look forward 30 bars (30 minutes max
   hold)" — at 5-minute bars, 30 bars is 150 minutes. Its own time stop says 15 minutes (3 bars).
   **6 bars / 30 minutes** is the recommendation: it covers the time stop with headroom, and it
   matches the horizon that was voted on. Thirty bars would let a signal claim credit for a move two
   and a half hours later.
2. **Intra-bar ambiguity is the real methodological risk.** A 20-tick stop is ~1.3× the median
   *minute* bar range; against a 5-minute bar it is well inside one bar, so target and stop are
   frequently both touched within the same bar and OHLC cannot say which came first. **Resolve it by
   measuring, not assuming:** run the tracker at **tick resolution on the committed fixture
   session**, then at bar resolution on the same session, and report the gap. Use **stop-first
   (pessimistic)** on the month and carry the fixture-measured gap as the error bar.

> **Number:** `hit_70_rate` with both bounds (stop-first and target-first), `avg_mfe`, `avg_mae`,
> `avg_mfe_mae_ratio`, and the `time_to_70` distribution. If most hits arrive in bar 1, the signal
> is a momentum detector; in bars 4–6, it is something slower and the 15-minute time stop is wrong.

**P — capture, properly.** Wire `xcap` to capture the MT5 window **by window handle**, not the whole
screen, and confirm it works whether or not MT5 has focus — that is the whole difficulty, because a
trader clicking our overlay takes focus away from MT5 at exactly the moment we need to read it. On
Mac, walk the Screen Recording permission prompt and **write down every click**; you need it for
onboarding docs in Week 5 and you will not remember it then.

> **Number:** a capture of the MT5 window taken while MT5 is unfocused, plus the permission
> walkthrough as a numbered list.

---

### D5 · Wed 9 Sep

**V — the nulls, and the walk-forward split.** The pre-written threshold was committed on 28 Aug,
so today is measurement against it, not negotiation with it.

- **Null 1 — random entry.** `backtest.random_entries` exists; use it. Same bars, same month, same
  forward window, no filter. This is `p₀`.
- **Null 2 — random regime assignment.** The one §6 says matters more: it catches a selector that is
  fitting noise rather than a strategy that is measuring the month.
- **Walk-forward.** Train ≤ the 2026-07-19 split, evaluate on the held out half. `dcbde04` made the
  split cut on the session, not the ET calendar date — 2026-07-19 is a Sunday, so it does not move
  these labels, but any other split date moves by 72 bars.
- **The ±20% delta perturbation** is mandatory, not optional, for `cvd_divergence` and
  `absorption_fade` — the two rules whose thresholds are in contracts and therefore inherit the
  15–20% method dependence. **If a rule's edge dies inside its own known error bar, it was never an
  edge.**

> **Number:** held-out `hit_70_rate`, the measured `p₀`, the achieved `N`, and the margin in standard
> errors. Report the distribution you committed to, not the best-looking cut of it.

**P — the live feed spike, in Rust.** Hold an open connection to a real live feed for a **full 30
minutes**, printing trades with aggressor side, without dropping or desyncing. Reconnection handling
can wait; continuity cannot. *(Nominally Varad's lane — it is yours because his whole day is the
edge test, this is the second fatal-risk item in the plan, and it is the right first contact with
Rust before the Week 5 backend ramp.)*

> **Number:** 30 minutes, wall clock, tick count, zero sequence gaps. This is a Week 1 gate line.

*Nobody is blocked:* V has the month; P has the vendor connection. Neither reads the other's output.

---

### D6 · Thu 10 Sep

**V — Layer 5, threshold tuning, and it is the day most likely to produce a dishonest number.**
Grid-search the four conditions' thresholds **on the training half only**, then evaluate the winner
**once** on the held-out half. Optimise `hit_70_rate × signals_per_month`, not hit rate alone — a
99% hit rate on three signals is three signals.

> Two rules, both from `thresholds_selector.md`, and neither is optional: **a cell under 30 is
> reported and not acted on**, and **one threshold, not a range**. If the held-out number is worse
> than the training number, that gap *is* the overfit and it gets reported, not tuned away.
>
> **Number:** the grid's surface, the chosen point, the training result and the single held-out
> result side by side.

**P — position memory and the global hotkey.** *(Pulled forward from Week 2 — you have seven days
for a five-day week.)* Position memory: reopens where the trader left it, per monitor, surviving a
monitor being unplugged. Hotkey: registered at OS level, **working while MT5 has focus** — that
clause is the entire difficulty; a hotkey that works only when our window is already focused is not
a hotkey. Pick a default that collides with neither MT5 nor cTrader.

> **Number:** hotkey demonstrated with MT5 focused. Position survives a restart and a monitor unplug.

---

### D7 · Fri 11 Sep — gate day

**Morning, separately.** V writes the result up against the 28 Aug commitment. P runs a second
fresh-clone check and drafts the install notes — including the sentence about Windows being
deliberately unsigned, which is easier to write now than in Week 4 under pressure.

**16:00, together with Shreyas — the Week 1 gate** ([`gates.md`](gates.md)):

- [ ] A measured forward-return / `hit_70` distribution clearing a **pre-written** threshold
- [ ] A live feed held 30 minutes without desync
- [ ] A Tauri window floated over MT5, click-through into MT5 confirmed
- [ ] Licensing answered **in writing** by at least one vendor *(Shreyas — sent during the gap)*
- [ ] S1, S2, S3 frozen and committed; `engine/mock.ts` misbehaving on demand
- [ ] `docs/qa/reference-session.md` exists and someone other than V signed off on it *(Shreyas)*
- [ ] The outlier detector flags the 2026-07-16 08:00 ET absorption hour

**Then `docs/decisions/2026-09-11-week-1.md`** — the feed vendor, go/no-go, and **what would change
your mind.** The second half is the part people skip and the part that matters in Week 8.

**If the result is inconclusive rather than negative** — which §6 predicted in writing and §2 above
now predicts quantitatively — the honest move is not to build and not to give up. It is to buy five
more months for ~$15 and re-run Days 4–6 against 300–900 signals, which is one week, not six months
of the wrong thing.

---

## 4 · Why neither of you can block the other

| Thing | Owner | Lands | Consumer |
| :--- | :--- | :--- | :--- |
| `engine/types.ts` (S2) + `FeedCreds` | both, jointly | **Fri 28 Aug** | P, all seven days |
| Regenerated month bar table | **P** | **Fri 28 Aug** | V, all seven days |
| Fixture session as JSON | P | Fri 28 Aug | P (self) |
| Part B thresholds | V | Fri 28 Aug | V (self) |
| Pre-written success threshold | V | Fri 28 Aug | the gate |

**Every cross-person dependency in the week is discharged before the week starts.** After 28 Aug the
lanes touch in exactly one place — the room on Fri 11 Sep — and that is a meeting, not a handoff.

```
V   D1 ── D2 ── D3 ── D4 ── D5 ── D6 ── D7 ┐
                                            ├─ gate, Fri 11 Sep 16:00
P   D1 ── D2 ── D3 ── D4 ── D5 ── D6 ── D7 ┘
```

Directory separation is what enforces it: `services/signal-data/` and `apps/desktop/` have no file
in common, so the two lanes cannot conflict even by accident.

---

## 5 · Corrections to `planfortoday.md`, carried into the week above

| # | It says | Reality |
| :--- | :--- | :--- |
| 1 | `hit_70_rate ≥ 25%` is success | 22.2% is free from a random walk and 25.0% is break-even after ~$25 costs. See §2 — the threshold is a margin over a measured null, and at 50–150 signals nothing below ~29% is provable |
| 2 | Load the CSV with **Polars** | The service is **pandas** + numpy + sklearn. Polars is not a dependency and adding one for a `read_csv` is not worth a lockfile change |
| 3 | The regime CSV is a prerequisite that is ✅ done | It is **stale** — five-feature matrix, and off the straddling-window bug `d3c896f` fixed. Its own README says so. Regenerating it is item 2 of Prathamesh's Friday |
| 4 | "Look forward 30 bars (30 minutes max hold)" | 30 bars at 5-minute bars is 150 minutes. Use **6 bars**, and see D4 |
| 5 | "Author Part B: derive them from July 2026 data" | `thresholds_selector.md` §Status is explicit that an assistant filling these in produces a file that looks like the mechanism working while doing none of what it is for, and Part A is a pre-commitment. **Derive from the training half only, commit, then evaluate held-out.** That satisfies both rules; deriving from the whole month satisfies neither |
| 6 | Prathamesh's parquet is not needed | Not needed for the *fixture*; needed for the *month*, which is what Layers 4 and 5 measure on. Closed by regenerating the bar table on 28 Aug |
| 7 | — | **`strategy.md` does not exist in this repo**, and `phase-1-kill-week.md` and `roles.md` both schedule work against it. `planfortoday.md`'s four conditions are that document's live replacement; the phantom reference should be retired rather than chased |

---

## 6 · Calendar shift

| | Was | Now |
| :--- | :--- | :--- |
| Week 1 · kill week | 31 Aug – 4 Sep | **5 – 11 Sep** |
| Week 2 · engine and shell become real code | 7 – 11 Sep | 12 – 18 Sep |
| Week 3 · live numbers on screen | 14 – 18 Sep | 19 – 25 Sep |
| Week 4 · rules, journal, dogfood | 21 – 25 Sep | 26 Sep – 2 Oct |
| Week 5 · backend | 28 Sep – 2 Oct | 3 – 9 Oct |
| Week 6 · webhooks, purchase flow | 5 – 9 Oct | 10 – 16 Oct |
| Week 8 · beta verdict | ends 23 Oct | ends 30 Oct |
| Week 12 · ten subscribers | ends 20 Nov | **ends 27 Nov** |

**One week was lost and it was lost deliberately, with everyone knowing** — which is what
[`gates.md`](gates.md) asks for and the opposite of a gate sliding one reasonable-sounding Friday at
a time. Nothing else moves. The gates themselves are unchanged in content; only their dates move.
