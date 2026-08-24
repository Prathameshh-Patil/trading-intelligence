# Phase 4 · Weeks 9–12 — Ten people who pay

**Mon 26 Oct – Fri 20 Nov**

The engineering slows down and distribution starts. **This is the month founders under-plan**, which
is why it gets the most explicit targets in the whole folder. There is no technical gate left to
pass — everything from here is whether ten specific human beings hand you money.

Ten subscribers at $39 (plus some at $43.99 with the journal) is **$390–440/month** against a run
rate of $84–126. That covers costs three to four times over. You need **ten people, not ten
thousand** — which is why "founder-led distribution" below is a list of conversations, not a funnel.

---

# Week 9 · Oct 26 – Oct 30 — Open the doors

Convert the beta. Turn on the journal add-on.

---

#### W9D1 · Mon Oct 26

**P** — Pricing page live with the **founding-price offer**, and say plainly that it is permanent
for the first ten. Plainly means on the page, in the checkout, and in the confirmation email — not
in a footnote. That plainness is what buys honest feedback instead of polite feedback for the rest
of the year.

**V** — Journal add-on gated behind its own entitlement, server side. The `tier` field in the
key-validate response has carried `core | core_journal` since `contracts.md` was frozen in Week 1,
so this is populating a value, not changing a contract.

**S** — Convert beta trader 1 to paid, at the founding price, on a call. **Ask for the money
directly.** They said yes to $39 unprompted in Week 8; the only thing between that and a payment is
someone asking. If they hesitate now, that hesitation is more valuable information than the
original yes, so listen to it rather than rescuing it.

*Float:* if V lands entitlements early, take install-friction work from Wednesday. **A second
instrument is not on the table this quarter** — NQ was dropped on 25 Aug, and adding one in Week 9
means a new feed adapter, re-derived thresholds and a second reference session to validate, in the
month where the engineering is supposed to be slowing down.

---

#### W9D2 · Tue Oct 27

**P** — In-app upgrade path, core → core-plus-journal. **This is your entitlement gating**, front to
back: you read the tier, you gate the UI, you handle the moment the tier changes mid-session without
a restart. Third route module you own.

**V** — Signal quality against live telemetry, and reconnect hardening pulled forward from Thursday.
*(This was "second instrument if Week 8 was clean". NQ was dropped on 25 Aug and nothing replaced it
— a second instrument needs a new feed adapter, thresholds re-derived through the harness, and its
own validated reference session, which is a Week 2-shaped job landing in the month the engineering
is meant to be slowing down. If it ever happens: **re-derive the thresholds, never scale Week 1's by
eyeball.**)*

**S** — Convert beta trader 2. Then publish the demo recording **where order-flow traders actually
gather** — the futures forums, the ATAS and Jigsaw communities, the Discord servers you recruited
from. Not LinkedIn. Not a launch post on a general startup site. The audience is small, specific,
and already knows what a footprint chart is; talk to them like it.

---

#### W9D3 · Wed Oct 28

**P** — Download and install friction pass, from the Week 7 confusion logs. Every step you can
delete between "decided to buy" and "seeing a signal" is worth more than a feature this month.

**V** — Signal quality review against live telemetry — the first one with real subscriber data in
it. Set up the weekly cadence now, because from next week this is the shape of your job.

**S** — Convert beta trader 3. Then answer the community thread from yesterday. **Answer every reply,
including the sceptical ones, especially the sceptical ones** — order-flow traders are a suspicious
audience by disposition and the scepticism is not hostility, it is the audience doing exactly what
you want them to do with a signal.

---

#### W9D4 · Thu Oct 29

**P** — Ship the first weekly visible improvement and tell your subscribers about it, however many
there are. **Start this rhythm at one subscriber**, not at ten. A product that visibly improves
every week retains; a silent one churns at month two regardless of quality.

**V** — Harden the feed adapter. Reconnects will be your **top support ticket** — a trader's WiFi
blips, their vendor restarts, their laptop sleeps, and every one of those looks to them like your
software broke. Make reconnect silent, make gaps visible, make neither require a restart.

**S** — Track **why people say no.** Every no gets a sentence. That list is the product roadmap and
it is worth more than every feature request you receive, because a feature request tells you what
someone imagines they want and a no tells you what actually stopped them.

---

#### W9D5 · Fri Oct 30

**ABC · 16:00 — Week 9 gate: subscriber #1 exists and paid real money.** From someone who is not
one of you.

If all three beta traders converted, you are at three and ahead of plan. If none converted despite
three unprompted yeses in Week 8, **that gap is the most important thing to understand this
quarter** — spend the whole afternoon on it, because a yes that doesn't convert means the price, the
moment, or the ask was wrong, and all three are fixable if you find out now.

### Gate — Week 9
- [ ] Subscriber #1 exists and paid real money
- [ ] Journal add-on gated, upgrade path works mid-session
- [ ] Demo recording published where the audience actually is
- [ ] The weekly-improvement rhythm has started

---

# Weeks 10–11 · Nov 02 – Nov 13 — Founder-led distribution

**Two subscribers a week. Every one hand-won.** Target: seven by Friday 13 Nov.

These two weeks are written as a **repeating weekly shape** rather than ten invented days, because
they genuinely are the same week twice and pretending otherwise would be planning theatre. The
targets are real; the day-by-day is not, because it depends entirely on who replies to Shreyas.

### The weekly shape

| Day | Prathamesh · Shell | Varad · Signal | Shreyas · Product |
| :--- | :--- | :--- | :--- |
| **Mon** | Pick this week's visible improvement from the support log. Small, visible, shippable by Thursday | Weekly signal-quality review against live telemetry. Write the one-paragraph verdict | Write the week's order-flow teardown |
| **Tue** | Build it | Feed adapter hardening — whatever last week's reconnect tickets pointed at | Publish the teardown. Answer every reply |
| **Wed** | Build it | Threshold tuning through the harness. Regression test must stay green | Onboarding calls with new subscribers |
| **Thu** | **Ship it, and tell every subscriber** | Support escalations that need engine knowledge | Onboarding calls. Log every no with its reason |
| **Fri** | Install-friction fix from the week's support tickets | Write the week's accuracy note | Count: subscribers, why each bought, why each no said no |

### The teardown rule

**One genuinely useful order-flow teardown per week — not an ad.** A teardown is: here is a real
session, here is what the delta did at this level, here is what that meant, here is what happened
next. It is useful **whether or not the reader ever buys anything.** If it does not stand alone as
something worth reading, it is an ad with a chart in it and this audience will recognise that
instantly and stop reading you.

Mention the product once, at the end, or not at all. The recording from Week 6 does the selling.

### The onboarding rule

**Every new subscriber gets a call.** Every single one, all ten. This does not scale and it is not
supposed to — you are buying the thing that only exists at this size: watching ten people's first
hour and understanding exactly why they bought. That understanding is the Week 11 gate, and no
amount of analytics substitutes for it.

### Distribution targets

| | End of W10 · Nov 06 | End of W11 · Nov 13 |
| :--- | :--- | :--- |
| Paying subscribers | 5 | **7** |
| Teardowns published | 1 | 2 |
| Onboarding calls done | every subscriber | every subscriber |
| Nos logged with reasons | all of them | all of them |

**If you are at three on 6 Nov**, the problem is distribution reach, not product — you have proven
people pay. Double the teardown cadence and go to a second community in Week 11.

**If you are at seven but three have stopped opening the app**, the problem is not distribution and
Week 12's retention check is going to hurt. Deal with it in Week 11, not Week 12.

### Gate — Weeks 10–11
- [ ] **Seven paying subscribers**
- [ ] Seven one-paragraph "why they bought" notes, one per subscriber, from Shreyas's calls
- [ ] Two teardowns published; both stand alone as useful
- [ ] Two visible improvements shipped and announced
- [ ] Every no logged with a reason

---

# Week 12 · Nov 16 – Nov 20 — Count what's true

Ten subscribers, and an honest look at the unit economics. **The temptation this week is to count
generously.** Resist it — the whole value of a twelve-week plan is that at the end you know
something true, and a flattering number tells you nothing you can act on.

---

#### W12D1 · Mon Nov 16

**P** — Pay down the worst technical debt from the sprint months. **Worst**, not most. Pick from:
the `storage.ts` and `capture.ts` shims marked temporary back on 24 Aug and never revisited · any
place the desktop and extension rule engines have diverged · whatever you have been working around
by hand for six weeks. One item done properly beats five started.

**V** — Begin the **internal accuracy report**: how did the signal actually do live, across weeks 9
through 11, on real subscriber sessions. Compare against the Week 1 pre-written threshold. **This
report is for the three of you, not for marketing**, which is exactly what makes it worth writing
honestly.

**S** — Retention check. **Is anyone still using it in week four of their subscription?** Pull the
telemetry per subscriber: sessions opened, signals acted on, journal entries written. Someone who
paid and stopped opening it is a churn in six weeks that you can still prevent this week.

---

#### W12D2 · Tue Nov 17

**P** — Debt item two.

**V** — Accuracy report continued. Include the sessions where it was wrong, in detail. A report
without failures in it has not been written honestly, and everyone reading it knows that.

**S** — Call every subscriber who has gone quiet. Not a survey — a call. Ask what happened. The
answer is almost never "it was bad"; it is usually something specific and fixable that they did not
consider worth reporting.

---

#### W12D3 · Wed Nov 18

**P** — Debt item three, or stop and stabilise if three feels like reaching.

**V** — Unit economics, on **one line**: revenue in, run rate out, gross margin. Include the payment
fees (~5% + $0.50 per transaction — real money at $39) and the Apple Developer amortisation. The
budget said $84–126/month; find out what it actually was, and where the estimate was wrong.

**S** — Consolidate the "why they said no" list from Weeks 9–11 into ranked themes. **That is the
quarter-two roadmap**, and it was written by the market rather than by the three of you.

---

#### W12D4 · Thu Nov 19

**ABC — the quarter-two decision, from evidence, not from ambition.**

Four questions, in this order, and answer each before moving to the next:

1. **Did the signal work?** Varad's accuracy report against the Week 1 threshold. Not "did people
   like it" — did it predict anything.
2. **Do people keep using it?** Shreyas's retention numbers. Below 50% at week four means the
   product is a demo, however good the signal.
3. **Does the money work?** Gross margin at ten subscribers, with real fees.
4. **What did the nos say?** The ranked themes, which is where growth actually lives.

Candidates for quarter two, decided against those answers and not before them: MT5 spot gold as a
**context-only mode** (rules, journal and capture work there; delta does not and you must never
claim it does — item A2 from the old plan comes back here, properly scoped) · **a second instrument**,
which is where NQ can legitimately return — with a full feed adapter, re-derived thresholds and its
own validated reference session, not as a flag flip · Windows code signing, which becomes worth its $215–260/yr at around
fifty users · a real onboarding flow that doesn't require Shreyas on a call.

---

#### W12D5 · Fri Nov 20

**ABC · the final gate, and the write-up.**

Write `docs/decisions/2026-11-20-quarter-one.md`: what you set out to prove, what you actually
proved, what you got wrong, and what quarter two is. **Include what you got wrong.** In six months
that section will be the only part anyone rereads.

### Gate — Week 12
- [ ] **Ten paying subscribers**
- [ ] **Positive gross margin** — revenue minus real run rate, with real payment fees
- [ ] **At least half still active after a month**
- [ ] Internal accuracy report published, failures included
- [ ] Quarter-two decision written down, with the evidence it rests on

---

## The four things still open, and when they must close

From section 09 of the artifact. Three are phone calls and one is a decision only you can make.

| Open item | Owner | Must close by | If it closes wrong |
| :--- | :--- | :--- | :--- |
| **Bring-your-own-feed licensing** — in writing, for our specific case | Shreyas | **Week 3.** Asked Week 1 Day 1 | The architecture is wrong and the cheapest honest alternative is ~20× the budget. This is the one that can end the project quietly |
| **Razorpay international recurring** — do non-Indian cards work on subscriptions for our entity | Shreyas | Week 6, when checkout is built | Merchant-of-record at ~5% for global cards, Razorpay for domestic UPI. **No crypto** — it breaks the compliant export path |
| **SEBI Research Analyst registration** | Shreyas + CA | **Week 1.** Raised three times already | Copy decides which side you land on. Charging for analytics a trader interprets ≠ charging for recommendations. Cheap to change before launch, expensive after |
| **Overlay compositing performance** | Prathamesh | Week 2 | Probably fine, genuinely unmeasured. Measure it in Week 1–2 rather than discovering it in Week 8 |

Costs and licensing terms in the source artifact were verified 24 August 2026 and move without
notice. The bring-your-own-feed architecture is a reasoned reading of standard industry practice,
**not legal advice** — confirm it in writing with the data vendor, and take the SEBI and FEMA
questions to a qualified professional.
