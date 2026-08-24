# Phase 2 · Weeks 2–4 — Make it real, locally

**Mon 7 Sep – Fri 25 Sep**

No backend. No auth. No website. No payments. **One goal: an app on your own machines that shows
correct live delta over a real chart.** If you can't sell that, no amount of billing code helps,
and every hour spent on billing before this works is an hour spent decorating something unproven.

---

# Week 2 · Sep 07 – Sep 11 — Engine and shell become real code

The throwaway spikes from kill week get rewritten **once**, properly, with tests. Resist the urge
to salvage. Rewriting from a notebook you understand takes two days; untangling a notebook you
half-remember takes five.

---

#### W2D1 · Mon Sep 07

**P** — Overlay behaviour, part one: **click-through and position memory**. Click-through means the
transparent regions pass clicks to MT5 underneath and the opaque regions don't — get the hit-test
region right, because "sometimes swallows a click on a live chart" is the kind of bug that loses a
subscriber in Week 10 and gets reported as "it feels laggy". Position memory means the window
reopens where the trader left it, per monitor, surviving a monitor being unplugged.

**V** — Scaffold `services/engine/` as a real Rust crate. Port the delta and CVD arithmetic out of
the notebook. **First test on day one**: `cargo test` asserting our CVD against
`docs/qa/reference-session.md` at every 15-minute mark, reading `gc_ticks_1session.parquet`. That
test is the project's spine — it is the only thing standing between you and a plausible wrong number,
and it must be red before it is green so you know it can fail.

**S** — Redesign the panel for a **380px floating window**, not a browser side panel. These are
genuinely different problems: no browser chrome, no scroll gutter, the trader's eye is on the chart
behind it and only flicks to us. Density matters more than hierarchy. Deliver a Figma or even paper
— P implements from it Wednesday, so it needs to be decided by Tuesday evening, not perfect.

*Float:* chase any vendor who hasn't replied to the Week 1 licensing email. Whoever is free. Do not
let this go quiet — the architecture rests on it and Week 3 is the deadline for a written answer.

*Why nobody is blocked:* V is in Rust with a committed fixture; P is in the window manager; S is in
a design tool. P's UI still talks to `engine/mock.ts` and will until Wednesday of next week.

---

#### W2D2 · Tue Sep 08

**P** — Overlay behaviour, part two: **global hotkey** to summon and dismiss, working while MT5 has
focus. That last clause is the whole difficulty — a hotkey that only works when our window is
already focused is not a hotkey. Register at OS level on both platforms and pick a default that
doesn't collide with anything MT5 or cTrader bind.

**V** — Ring buffer for the live tick stream, **fixed memory**. This is the piece that decides
whether the app is still healthy at hour six of a session. Size it from the measured tick rate of
the busiest hour in your month of data — not a guess, a number you can point at. Then decide and
document what happens on overflow: drop oldest, and surface it in `FeedStatus.gapCount` so it is
visible rather than silent.

**S** — Write the **test protocol**: what "correct" means, session by session. Not "check delta is
right" — a numbered procedure someone else could run: which session, which reference tool, which
timestamps to compare, what tolerance counts as agreement, what to do when it disagrees. You will
run this yourself every day of Week 3, and by Week 7 a beta trader will run a version of it. Write
it so a stranger could.

*Float:* if P lands the hotkey by lunch, start porting the six views into the Tauri build against
S's design — it is Wednesday's work and Wednesday is heavy.

*Why nobody is blocked:* S's design lands tonight for P's Wednesday. Nothing V does today touches
anything P does today.

---

#### W2D3 · Wed Sep 10

**P** — Port all six views into the Tauri build against S's 380px design. Not a redesign — a port
plus a density pass. The UI survived a browser-extension rewrite already; trust it, adjust it,
don't restart it. Everything still renders from `engine/mock.ts`.

**V** — CVD and footprint aggregation at **configurable bar sizes**. Configurable is the
requirement, not a nicety: Shreyas will want 1-minute during Week 3 grading and beta traders will
want 5-minute, and hardcoding a bar size in Week 2 means an engine change in Week 8. Test each bar
size against the reference session independently — an aggregation bug that only appears at 15m is
exactly the kind that hides.

**S** — Chase vendors, hard. It is Wednesday of Week 2 and `contracts.md`'s entire premise is
unconfirmed in writing. If Databento, Rithmic and Tradovate have all gone quiet, escalate: call
instead of email, or ask on their public forum where a support engineer answers publicly. A written
"no distribution licence needed" is worth more than anything else produced this week.

*Float:* if V finishes aggregation early, define the **Rust↔JS command layer** — the `invoke`
handlers matching `contracts.md` S2, returning hardcoded data. It is Thursday's work and it makes
Thursday's integration trivial.

*Why nobody is blocked:* P has S's design from last night. V is in the crate. S is on the phone.

---

#### W2D4 · Thu Sep 11

**P** — Finish the view port. Then, with V, **define the Rust↔JS command layer** — the actual
`invoke` names, the actual event channel names, the serde shapes matching `contracts.md` S2. Ninety
minutes together. The Rust side returns hardcoded data today; that is fine and expected.

**V** — Implement those `invoke` handlers over the real engine, reading the fixture parquet rather
than a live feed. **By end of day, `VITE_ENGINE=real` should render the fixture session in the real
window through the real Rust engine.** No live feed involved. This is the S2 integration, done a
week early against a file instead of a network, which is why it will take an afternoon instead of
three days.

**S** — Run your own test protocol against that build, as a rehearsal. You are not grading the
signal yet — you are grading the protocol. Anywhere the procedure is ambiguous, fix the procedure.
Finding out in Week 3 that step 4 is unclear costs a session.

*Float:* whoever finishes first writes the `daily_updates/` entry, with the `VITE_ENGINE=real`
screenshot in it.

*Why nobody is blocked:* the joint 90 minutes is scheduled, and after it both sides implement
independently against a type they just agreed on.

---

#### W2D5 · Fri Sep 11

**P** — Overlay compositing measurement, if it didn't happen in Week 1. Frame timing on MT5 with
the overlay on and off, numbers written down. **The overlay must not stutter a live chart** — a
trader will forgive a wrong signal before they forgive a laggy chart, because the second one is
their fault to fix and they'll fix it by uninstalling.

**V** — Harden the crate: `cargo clippy` clean, the fixture test green at every bar size, and a
property test on the delta arithmetic (delta always equals askVol − bidVol; CVD always equals the
running sum; both hold for any input, including empty bars and single-tick bars).

**S** — Test protocol finalised and committed. Vendor status written up: who answered, what they
said verbatim, who is still silent and what you'll do about it.

**ABC · 16:00 — Week 2 gate.**

### Gate — Week 2
- [ ] `cargo test` green against the reference session, at every configured bar size
- [ ] Click-through into MT5 demonstrated
- [ ] Position memory survives a restart, including a monitor being unplugged
- [ ] Global hotkey works **with MT5 focused**
- [ ] `VITE_ENGINE=real` renders the fixture session through the real engine
- [ ] Test protocol written well enough that a stranger could run it

---

# Week 3 · Sep 14 – Sep 18 — Live numbers on screen

**The milestone that matters most in the whole quarter.** Everything before this was preparation
and everything after is packaging. This is the week the product either exists or doesn't.

---

#### W3D1 · Mon Sep 14

**P** — Feed credential entry and connection status UI. The status indicator has four states from
`contracts.md` S2 — `disconnected`, `connecting`, `live`, `stale` — and **`stale` is the one that
matters**: connected but not receiving, which looks identical to a quiet market and is not. Make
those visually distinct at a glance from three feet away, because that is the actual viewing
distance. Credentials go to the OS keychain, never to disk in plaintext, and never to our servers.

**V** — Feed adapter for the vendor chosen on 4 Sep. Connect, authenticate, subscribe, decode. Get
ticks flowing into the ring buffer. Reconnect and gap detection are tomorrow — today is the happy
path, end to end.

**S** — Book your sessions. You will sit a full live session **every day this week** with the
overlay, grading it. Block the time in a calendar now, tell both engineers, and treat it as
immovable. Prepare `docs/qa/disagreements.md` with the columns you'll fill: timestamp, what it
flagged, what you'd have called it, why, and severity.

*Float:* if P finishes the status UI early, wire capture into `setContext` — it is Wednesday's work
and Wednesday is the integration day.

*Why nobody is blocked:* P builds against `engine/mock.ts`, which can already produce every one of
the four states on demand — including `stale`, which a real feed would make him wait hours for.

---

#### W3D2 · Tue Sep 15

**P** — Wire the **Analyze view to the local engine** instead of the stub API. Delete the
`http://localhost:8000` call from the desktop app's signal path entirely. Under the corrected
architecture no signal number crosses a network — it is computed on the trader's machine from the
trader's own feed. The remaining API call from desktop is chart-context extraction only, and it
sends a screenshot, never a tick.

**V** — Reconnect and gap detection. Connections drop mid-session — a WiFi blip, a vendor restart,
a laptop sleeping. Detect the gap, reconnect, backfill if the vendor allows it, and **mark the CVD
as discontinuous if you couldn't backfill.** A CVD with a silent hole in it is a wrong number that
looks right, which is the failure mode this whole project is trying to avoid.

**S** — First full grading session, against the mock, as a dress rehearsal for tomorrow. Fill
`disagreements.md` properly. Some entries will be "the mock is unrealistic here" — that is a useful
finding, log it and tell P.

*Float:* if V lands reconnect early, start the outlier detector on the live stream — it is
Wednesday's and Wednesday is the heaviest day of the quarter.

*Why nobody is blocked:* still two lanes, one shared type. **This is the last day of the split** —
tomorrow they join.

---

#### W3D3 · Wed Sep 16 — **integration day**

**The second and last scheduled integration point in twelve weeks.** Both of you, same room or same
call, all day.

**P + V** — Switch `VITE_ENGINE=real`, point it at the live feed, and get **live delta streaming
into the app at sub-second latency**. Then V runs the outlier detector against the live stream and
P renders what it fires. Budget the whole day. Expect the first three hours to be serde mismatches
and timezone bugs; that is normal and it is why the day is reserved rather than squeezed.

Measure the latency, don't assert it. Tick received → number on screen, in milliseconds, at the
99th percentile during the busiest hour, not the median during lunch.

**S** — Grade the live overlay for a full session, for real this time. Every flagged outlier gets a
verdict: agree, disagree, or unsure. **Unsure is a legitimate answer and you should use it** — a
forced binary from someone who genuinely can't tell is noise dressed as data.

*Float:* none. Today is the integration.

---

#### W3D4 · Thu Sep 17

**P** — Capture feeding `symbol` and `timeframe` into the engine's context (S6). The overlay now
knows which instrument the trader is looking at and stays in sync when they switch charts. Then
handle the ugly cases: symbol not recognised, MT5 window minimised, trader on a chart we don't have
a feed for. Each needs a visible, honest state — never a wrong number, and never a confident one.

**V** — Tune against S's disagreement log from yesterday. **Read it before you touch a threshold.**
If Shreyas called five flagged prints wrong, the question is not "how do I filter those five" —
it's "what did those five have in common", and the honest answer is sometimes "nothing, the rule is
wrong." Re-run the backtest after every threshold change; a threshold that improves live grading
and destroys the backtest is overfitting to one session.

**S** — Second full live grading session. Compare against yesterday's log — did the changes help,
or did they move the problem? You are the only person who can answer that, and neither engineer can
grade their own homework.

*Float:* if P finishes capture early, take the "what happens on a chart we have no feed for" empty
state — it is small, it is user-facing, and it will otherwise ship as a blank panel.

*Why nobody is blocked:* back to two lanes, now over a live engine.

---

#### W3D5 · Fri Sep 18

**P** — Polish pass on the live states: connecting, live, stale, reconnecting, gap-detected. Five
states, five clear appearances, tested by unplugging the network cable and watching.

**V** — Third grading session's tuning, then write down where the outlier thresholds landed for the
launch instrument **and why** — the Week 4 backtest harness will re-derive them and you need
something to compare against.

**S** — Third full grading session, then the week's verdict in one paragraph: does what it flags
match what an order-flow trader would call an outlier? **You have the authority to say no here, and
if you say no the gate is not met.**

**ABC · 16:00 — Week 3 gate.** This one is not judged from a description. Record the screen: our
overlay and ATAS side by side, same session, CVD agreeing at every 15-minute mark. If the recording
doesn't exist, the gate isn't met.

### Gate — Week 3
- [ ] **Live delta on screen, matching a reference footprint chart, for a full session** — recorded
- [ ] Sub-second latency measured at p99 during the busiest hour, not asserted
- [ ] Reconnect and gap detection survive a real network drop
- [ ] Three full grading sessions logged in `disagreements.md`
- [ ] Shreyas says, in writing, that the flags look right
- [ ] Licensing answer received in writing — **this was due Week 3 and there is no more slack**

---

# Week 4 · Sep 21 – Sep 25 — Rules, journal, and dogfood

**All three of you use it every session. Nobody else yet.** The gate is not "it works" — it is
"we would miss it if it vanished", and that is a feeling you can only earn by five days of use.

---

#### W4D1 · Mon Sep 21

**P** — Port the rule engine to local storage. **The same logic you already wrote** for the
extension — this is a port, not a rewrite, and the storage shim from Day 2 (`storage.ts` → tauri
store) is the only thing that should change. Both apps' rule behaviour must stay identical; if it
diverges, one of them is now wrong and nobody will notice for a month.

**V** — Backtest harness, day one. The requirement is **a rule change replayed over a month in
minutes**, and "minutes" is a hard requirement, not a hope: if it takes an hour, you will run it
once a week instead of ten times a day, and threshold tuning stops being empirical. Parallelise
over days, cache the parsed parquet, and measure the wall clock.

**S** — Dogfood log, day one, for all three of you. One file per person per day. Three prompts:
what did it tell me, what did I do, was it right. Ten minutes each, end of session. Chase the
engineers for theirs — they will skip it, and the log is the only evidence the Week 4 gate has.

*Float:* if P finishes the rule port early, start the journal port — it's Tuesday's.

*Why nobody is blocked:* P is in TypeScript and local storage; V is in Rust and Python; S is
writing. Zero shared files.

---

#### W4D2 · Tue Sep 22

**P** — Port the journal to local storage. **Local-first, per `contracts.md` S4** — it works
completely offline, forever, with no backend in existence. Sync is a Week 6 addition that changes
nothing about how it behaves when the network is gone. Build it as if the backend will never exist
and you will not have to rebuild it when the backend is late.

**V** — Backtest harness, day two: wire the outlier rules in and reproduce Week 3's live results
from the recorded ticks. **If the backtest and the live run disagree on the same session, one of
them is lying and you need to know which before you tune anything.** This reconciliation is the
harness's real acceptance test.

**S** — Dogfood day two. Then start drafting landing page copy — **from what the tool actually does,
not what you hoped it would do.** You have now watched it for four sessions; you are the only person
on the team who has seen it with fresh eyes and can still remember what was confusing.

*Float:* CA follow-up — the entity structure and SEBI answer, in writing. Whoever is free chases it;
it has been open since Week 1 and it decides what the landing copy is allowed to say.

---

#### W4D3 · Wed Sep 23

**P** — Rule-violation warning firing on **live trades**, not on replayed ones. This is the feature
that most directly changes trader behaviour, and it is also the one most likely to be annoying:
get the timing right, get the dismissal right, and make sure it cannot fire twice for the same
violation. Ask Shreyas to sit with it before you consider it done.

**V** — Tune the GC outlier thresholds against S's full disagreement log — now three
sessions of Week 3 plus two of dogfood. *(One instrument, so this is one set of numbers. Keep the
scaling derivation next to them anyway — a second instrument in quarter two starts from it.)* Run every candidate through the harness. Write the final
numbers and the reasoning into `docs/decisions/`.

**S** — Dogfood day three. Sit with P's rule warning for a full session and say honestly whether it
helps or nags. **You are allowed to say "this is annoying" and it is a real finding.**

*Float:* if V's tuning converges early, start the Mac installer — it's Thursday's and code signing
always takes longer than expected.

---

#### W4D4 · Thu Sep 24

**P** — First installers, Mac and Windows. **Mac must be signed and notarized** — Gatekeeper blocks
an unsigned build outright, it does not merely warn, and $99/yr Apple Developer is already in the
budget. **Windows ships unsigned for now**, deliberately: Microsoft's cheap Azure signing service
doesn't validate Indian organisations, and a traditional OV certificate is $215–260/yr plus a
hardware token. Unsigned means a "Windows protected your PC → More info → Run anyway" prompt.
For ten subscribers you personally onboard, that is one sentence in an email. Write that sentence
today and put it in the install notes. Buy the certificate at ~50 users.

**V** — Harness performance and correctness: replay the full month in minutes, reproduce Week 3
exactly, and commit the reproduction as a regression test. From here on, a threshold change that
breaks the reproduction is a bug, not a tuning decision.

**S** — Dogfood day four. Install both installers **on a machine that has never had the dev
environment on it** — that is the only honest install test, and it is the test that catches the
missing runtime dependency every single time.

*Float:* whoever is free writes the install notes for both platforms, including the Windows
"Run anyway" sentence and every Mac Screen Recording permission click P wrote down in Week 1.

---

#### W4D5 · Fri Sep 25

**P** — Fix whatever S's clean-machine install found. There will be something. There always is.

**V** — Write the month-one internal accuracy note: what the signal did across four weeks of live
grading and one month of backtest. Honest version, including the sessions where it was wrong.

**S** — Dogfood day five, then the gate question, asked of each of you separately so nobody
influences anyone: **would you miss this if it vanished tomorrow?**

**ABC · 16:00 — Week 4 gate, and the month-one review.** If the answer to Shreyas's question is
"not really" from any of the three of you, do not proceed to Week 5. Spend Week 5 finding out why.
Building a checkout for something you wouldn't miss is the most expensive mistake available to you
at this point in the plan.

### Gate — Week 4
- [ ] All three ran it live for **five consecutive sessions**
- [ ] All three say they would miss it — separately, unprompted
- [ ] Installers built for Mac (signed, notarized) and Windows (unsigned, documented)
- [ ] Clean-machine install succeeded on both platforms
- [ ] Rule-violation warning fired on a real live trade
- [ ] Backtest reproduces a live session exactly, and that reproduction is a committed test
