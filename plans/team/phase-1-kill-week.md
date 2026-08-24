# Phase 1 · Week 1 — Kill week

**Mon 31 Aug – Fri 4 Sep**

Five days whose only purpose is to find out whether this project should exist. **Every line of code
written this week is throwaway and you should treat it that way** — no abstractions, no tests
beyond what proves the number, no file you'd be sad to delete. Week 2 rewrites all of it properly.
If Friday's answer is no, you have spent one week instead of six months.

The one thing this week that is *not* throwaway: `contracts.md`. The types get frozen Monday and
they survive the rewrite.

---

#### W1D1 · Mon Aug 31

**P** — `apps/desktop`: strip the Tauri window to the overlay skeleton. No overlay behaviour yet —
today is only about the shell rendering the six ported views at 380px wide, which is a floating
window, not a browser side panel. **Then, jointly with V, freeze S2** — write
`apps/desktop/src/lib/engine/types.ts` from `contracts.md` and commit it. Thirty minutes, both of
you, one file. This is the single most valuable half hour of the week.

**V** — ~~The research spike~~ — **`compute_delta_cvd.py` already does this**, on `main` since
24 Aug: per-trade delta, session-reset CVD, 1-minute bars, price-level footprint, 439 lines. Read
it, run it, and spend the day on **what it doesn't do — the outlier rules from `strategy.md`**,
which was Wednesday's task and is now Monday's. You start the week a day ahead; don't spend that day
re-deriving CVD. **Then freeze S2 with P.**

**S** — Send the three vendor emails, 08:00, before anything else. Record every reply **verbatim**
in `docs/qa/licensing.md` — not a summary, the actual words, because a summary of a licensing
answer is worthless when a lawyer reads it in Week 7. This is the most valuable thing anyone does
today: the entire architecture rests on the bring-your-own-feed reading being correct, and right
now it is a reasoned inference, not a written answer.

*Float:* register the domain on Cloudflare and set up Zoho mailboxes — 90 minutes, and whoever
finishes first takes it. It has to happen this week and it belongs to nobody in particular.

*Why nobody is blocked:* the S2 freeze is 30 minutes of joint work, then P builds against a type
and V builds against a notebook. Neither needs the other's output.

---

#### W1D2 · Tue Sep 01

**P** — Write `engine/mock.ts` (**S2's fake**). Replay the committed fixture session at 10x, emit
`DeltaBar` and `Outlier` events, and — the part that matters — make it *misbehave on demand*: go
`stale`, drop the connection, emit a 7-digit CVD, emit a 40-character symbol. **You write the mock,
not Varad**, because you are the one who needs to find out today that your layout breaks on a
7-digit CVD, rather than in Week 3 with a real feed. Then: transparent, borderless, always-on-top,
floating over MT5. Install the MT5 demo terminal if nobody has it. Confirm click-through into MT5.

**V** — **Validate delta against a real footprint chart — the open hard gate.** The 2026-07-16
GCQ6 session is already cut and plotted; what has never happened is comparing it to somebody else's
rendering of the same session. **Unvalidated delta is worse than no delta** — it is a plausible
number that is silently wrong, and every downstream decision inherits the error.

ATAS and Sierra are Windows-only and the machine is an ARM Mac, so Shreyas picks the path on Week 0
Friday: TradingView web now, a real footprint platform before the Week 3 gate. **If it doesn't
match, check in this order — timezone, then contract (GCQ6→GCZ6 rolls 29 Jul), then the mapping.**
That inverts the usual advice on purpose: the mapping already has three independent confirmations,
so it is now the least likely culprit.

**S** — Grade V's validation **independently**. He shows you our CVD and the reference CVD side by
side; you say whether they agree. Then write `docs/qa/reference-session.md` — the session date, the
instrument, the reference tool, and the CVD at each 15-minute mark. That file becomes the thing
every future "is the delta right" argument is settled against, for the rest of the project.
Afternoon: the CA call — two questions, **export-of-services structure with LUT**, and **whether the
product as described triggers SEBI Research Analyst registration**. Get the SEBI answer in writing.

*Float:* if P gets click-through working before lunch, take the overlay compositing measurement
early (it is nominally W2) — watch MT5's frame timing with the overlay on and off. Nobody has
published numbers on a transparent webview compositing over a fast-redrawing chart. It is probably
fine. Find out in Week 1 rather than Week 8.

*Why nobody is blocked:* V validates against ATAS; P validates against his own mock; S grades V.
The one handoff — V showing S the numbers — is 20 minutes and scheduled.

---

#### W1D3 · Wed Sep 02

**P** — Capture, properly. Wire `xcap` to capture **the MT5 window by window handle**, not the whole
screen. Confirm it works whether or not MT5 has focus — this is the part that breaks, because a
trader clicking our overlay takes focus away from MT5 at exactly the moment we need to read it.
On Mac, walk the Screen Recording permission prompt and write down every click, because you will
write that into onboarding docs in Week 5 and you will not remember it then.

**V** — *(Started Monday, since the CVD spike was already done.)* Finish the outlier detection from
`strategy.md`, **for GC only** — NQ is dropped, so the ≥60 NQ and ≥200 ES figures in that document
are now the *derivation source* you scale from, not thresholds you implement. **Write down how you
scaled to GC**, because that number is going to be argued about in Week 4 and "it looked right" will
not survive it. Output for one session: a
timestamped list of outlier prints with price levels and cluster boundaries.

The 2026-07-16 session hands you a free test case: **price fell 89 points while CVD closed +1,842**,
with the 08:00 ET hour showing delta +1,083 against a 47.7-point drop. That is textbook absorption —
buyers aggressing into heavy resting supply — and **if your outlier detector doesn't flag that hour,
it doesn't work.**

**S** — Recruit the three beta traders to a soft commitment for Week 7. Warm the ones you started
in Week 0. Then a second pass on `docs/qa/glossary.md` now that you have watched a real footprint
chart next to our numbers — the definitions you wrote before seeing it are probably slightly wrong,
and that is fine, but fix them now while you can still tell.

*Float:* the domain and Zoho mailboxes, if nobody took it Monday. It stops being optional Friday.

*Why nobody is blocked:* three separate machines, three separate problems.

---

#### W1D4 · Thu Sep 03

**The most important day of the twelve weeks.**

**V — morning, before anything else: write down the threshold.** Commit it. What forward return,
over what horizon, at what hit rate, would make this a real edge? A threshold chosen after seeing
the distribution is not a threshold — it is a story. This is the specific way this project fails,
and the only defence is a git commit with a timestamp earlier than the results.

**V** — Then the edge test. Apply the strategy's location-and-reaction rule to your outliers —
absorption into structure lows, trapped buyers into highs — and measure forward returns over 5, 15
and 30 minutes across the full month. **Produce a distribution, not an anecdote.** A histogram, a
median, a spread, and the null: what does a random entry at a random time in the same month return?
If your signal doesn't beat the null, you don't have one.

**P** — Live feed spike. From Rust, hold an open connection to a real live feed for a **full 30
minutes** and print trades with aggressor side without dropping or desyncing. Reconnection handling
can wait; continuity cannot. *(This is nominally V's lane — it is P's today because V's entire day
is the edge test and this is the second fatal-risk item in the plan. It is also the right week for
P to touch Rust for the first time, on something small, before the Week 5 backend ramp.)*

**S** — Payments reality check. Open Razorpay and Lemon Squeezy accounts. Ask Razorpay **directly**
whether international cards work on recurring subscriptions for our entity type — not the docs, a
human. Confirm which processor can actually pay out to an Indian account. No crypto: it breaks the
compliant export path. Then prepare tomorrow's decision record template so Friday is a decision,
not a drafting session.

*Float:* none today. Everyone has a fatal-risk item. If you finish, help S with the payment calls —
they are phone calls and two people can make twice as many.

*Why nobody is blocked:* V has the month of data; P has the vendor connection; S has a phone.

---

#### W1D5 · Fri Sep 04

**ABC — all three, one room, the whole day if it takes it.**

**Morning:** V presents the forward-return distribution against Thursday morning's committed
threshold. Not the best-looking cut of it — the one he committed to. S asks the uncomfortable
questions; that is the job. P stays quiet until the number is settled.

**Afternoon — three decisions, one page:**

1. ~~**Launch instrument**~~ — **already decided: GC.** NQ was dropped on 25 Aug and this row is
   kept only so nobody reopens it on Friday. One instrument, one set of thresholds, one reference
   session.
2. **Feed vendor** — Rithmic, Tradovate or CQG, based on whose licensing answer came back cleanest
   and whose adapter P found least hostile on Thursday.
3. **Go or no-go** — and if go, `docs/decisions/2026-09-04-week-1.md` naming what you chose and
   **what would change your mind**. The second half is the part people skip and the part that
   matters in Week 8 when someone says "we should have picked a different instrument."

**If the edge test came back flat:** the honest move is to spend Week 2 testing a **second
formulation from `strategy.md`**, not to proceed to build. Say it out loud on Friday if it happens,
because on Monday it will feel like giving up and it isn't. Two weeks of research beats six months
of building the wrong thing. Everything else in this folder shifts one week right; nothing is lost.

---

### Gate — Week 1

- [ ] A measured forward-return distribution exists and clears a **pre-written** threshold
- [ ] A live feed held for 30 minutes without desync
- [ ] A Tauri window floated over MT5, with click-through into MT5 confirmed
- [ ] Licensing answered **in writing** by at least one vendor
- [ ] S1, S2, S3 frozen and committed; `engine/mock.ts` behaving badly on demand
- [ ] `docs/qa/reference-session.md` exists and someone other than V signed off on it
- [ ] The outlier detector flags the 2026-07-16 08:00 ET absorption hour

## What carries into Week 2

Nothing but the contracts, the fixture, the reference session, the decision record, and what you
learned. **Delete the notebooks. Delete the spikes.** Week 2 rewrites them once, properly, with
tests, and it goes faster if there is nothing tempting to salvage.
