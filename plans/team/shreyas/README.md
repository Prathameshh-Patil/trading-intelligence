# Shreyas — your twelve weeks

**Product, QA, ops · the most underrated seat here.**

You are not an engineer and nothing here asks you to become one. **Two of the three highest-risk
items in this project are phone calls, not code**, and both are yours. A third — *is this signal
actually right* — is yours because neither engineer can grade their own homework.

| | |
| :--- | :--- |
| **Domain validation** | [`grading.md`](grading.md) — **your "no" stops the sprint** |
| **AI-assisted code review** | [`review-rubric.md`](review-rubric.md) |
| **Vendor + compliance calls** | §"The calls you own" below. If licensing comes back wrong, no amount of Rust helps |
| **Test protocol + release QA** | §"Release QA" below |
| **Beta recruitment + onboarding** | Three testers in Week 7, then a call with **every single subscriber** |
| **Copy, docs, support** | Landing page, docs, the support inbox |

You open **issues**. You do not open PRs against `services/` or `apps/*/src`. `docs/`, `plans/` and
copy are yours to edit directly.

**Your failure mode:** being treated as a helper rather than an owner. **The two engineers cause
this, not you.** Watch for it in standup — if two days pass where you only report on things they
asked for, the seat is being misused, and you are the only person who can say so.

---

## Week 0 · Aug 26–28 — learn the domain

| Day | Work |
| :--- | :--- |
| **Wed 26** | **Three hours on footprint charts** — see [`grading.md`](grading.md). Highest-leverage thing you do all quarter, because in Week 3 you are the person who decides whether the numbers are right. Write `docs/qa/glossary.md` **in your own words.** Also: open ATAS demo and Sierra Chart trial accounts today — both take time to approve. |
| **Thu 27** | Draft the vendor licensing email — one precise question, **identically worded** to Databento, Rithmic and Tradovate. Do not soften it, do not add context, do not ask three questions. Reviewed at Friday standup, sent Monday 08:00. Also: **book the CA call for Week 1 Tuesday — book it now**, CAs are not available on two days' notice. |
| **Fri 28** | **Own the reference-chart problem and pick a path today.** It is a tooling and access question, not an engineering one, which is what makes it yours. Our delta has never been compared to another platform's rendering of the same session, and ATAS and Sierra are Windows-only on an ARM Mac. Three ranked options are in [`../week-00.md`](../week-00.md) — TradingView web works today and free; a screenshot from anyone with a footprint platform is better; a Windows machine or Parallels is the real answer. **Run option 1 this week regardless** — it costs nothing and would catch a timezone or contract error three weeks before the Week 3 gate. Then: start beta recruitment. Three traders, from the communities where this strategy actually lives — futures order-flow forums, ATAS and Jigsaw communities. **Not friends.** A friend tells you it's great, and a friend's yes cannot pass the Week 8 gate. Soft commitment to test in Week 7, which is seven weeks out, so start warm now. |

---

## Week 1 · Aug 31 – Sep 4 — kill week

| Day | Work |
| :--- | :--- |
| **Mon 31** | **Send the three emails, 08:00, before anything else.** Record every reply **verbatim** in `docs/qa/licensing.md` — not a summary, the actual words, because a summary of a licensing answer is worthless when a lawyer reads it in Week 7. **The most valuable thing anyone does today**: the entire architecture rests on the bring-your-own-feed reading being correct, and right now it's a reasoned inference, not a written answer. |
| **Tue 01** | **Grade Varad's delta validation independently.** He has three internal-consistency checks already (a 48.32/47.79 aggressor split, 83% tick-rule agreement, a +0.50 delta↔return correlation). **None of those is what you are grading.** You are grading whether our number matches *somebody else's* number for the same session — which is the one thing internal checks structurally cannot do. He shows you our CVD and ATAS's side by side; you say whether they agree. Then write `docs/qa/reference-session.md` — session date, instrument, reference tool, CVD at every 15-minute mark. **That file settles every future "is the delta right" argument, for the rest of the project.** Afternoon: the CA call — export-of-services structure with LUT, and **whether the product as described triggers SEBI Research Analyst registration.** Get the SEBI answer in writing. |
| **Wed 02** | Recruit the three beta traders to a soft Week 7 commitment. Second pass on the glossary now that you've watched a real footprint chart next to our numbers — the definitions you wrote before seeing it are probably slightly wrong, and **fix them now while you can still tell.** |
| **Thu 03** | **Payments reality check.** Open Razorpay and Lemon Squeezy accounts. Ask Razorpay **directly — a human, not the docs** — whether international cards work on recurring subscriptions for our entity type. Confirm which one can actually pay out to an Indian account. **No crypto** — it breaks the compliant export path. Then prepare tomorrow's decision-record template so Friday is a decision, not a drafting session. |
| **Fri 04** | Go/no-go. **Ask the uncomfortable questions about the distribution — that is the job.** Varad hands you [`../varad/thresholds.md`](../varad/thresholds.md) before he shows you anything else; check the git timestamp is earlier than the results. |

---

## Week 2 · Sep 7–11 — design and protocol

| Day | Work |
| :--- | :--- |
| **Mon 07** | **Redesign the panel for a 380px floating window**, not a browser side panel. Genuinely different problems: no browser chrome, no scroll gutter, and the trader's eye is on the chart *behind* it and only flicks to us. **Density matters more than hierarchy.** Figma or paper — Prathamesh implements Wednesday, so decided by Tuesday evening, not perfect. |
| **Tue 08** | **Write the test protocol:** what "correct" means, session by session. Not "check delta is right" — a numbered procedure a stranger could run. Which session, which reference tool, which timestamps, what tolerance counts as agreement, what to do when it disagrees. You run it yourself every day of Week 3; by Week 7 a beta trader runs a version of it. |
| **Wed 10** | **Chase vendors, hard.** It's Wednesday of Week 2 and the whole premise is unconfirmed in writing. If all three have gone quiet, escalate: call instead of email, or ask on their public forum where a support engineer answers publicly. A written *"no distribution licence needed"* is worth more than anything else produced this week. |
| **Thu 11** | Run your own test protocol against Prathamesh's build, as a rehearsal. **You are grading the protocol, not the signal.** Anywhere the procedure is ambiguous, fix the procedure. |
| **Fri 11** | Protocol finalised and committed. Vendor status written up: who answered, what they said verbatim, who is silent and what you'll do about it. |

---

## Week 3 · Sep 14–18 — grading, every day

**Your core week.** Block the sessions in a calendar now and treat them as immovable.

| Day | Work |
| :--- | :--- |
| **Mon 14** | Book your sessions — a **full live session every day this week.** Tell both engineers. Prepare `docs/qa/disagreements.md` with the columns from [`grading.md`](grading.md). |
| **Tue 15** | First full grading session, **against the mock**, as a dress rehearsal. Some entries will be "the mock is unrealistic here" — that's a useful finding, log it and tell Prathamesh. |
| **Wed 16** | **Grade the live overlay for a full session, for real.** Every flag gets a verdict: agree, disagree, or **unsure**. Unsure is legitimate and you should use it — a forced binary from someone who genuinely can't tell is noise dressed as data. |
| **Thu 17** | Second live session. **Compare against yesterday's log — did the changes help, or move the problem?** You are the only person who can answer that. |
| **Fri 18** | Third live session, then the week's verdict in one paragraph: does what it flags match what an order-flow trader would call an outlier? **You have the authority to say no, and if you say no the gate is not met.** |

---

## Week 4 · Sep 21–25 — dogfood

| Day | Work |
| :--- | :--- |
| **Mon 21** | Dogfood log, day one, **for all three of you.** One file per person per day, three prompts: what did it tell me, what did I do, was it right. Ten minutes each at end of session. **Chase the engineers for theirs** — they will skip it, and the log is the only evidence the Week 4 gate has. |
| **Tue 22** | Day two. Start drafting landing copy **from what the tool actually does, not what you hoped.** You've watched it four sessions; you're the only person who has seen it with fresh eyes and can still remember what was confusing. |
| **Wed 23** | Day three. **Sit with Prathamesh's rule-violation warning for a full session** and say honestly whether it helps or nags. **You are allowed to say "this is annoying" and it is a real finding.** |
| **Thu 24** | Day four. **Install both installers on a machine that has never had the dev environment on it.** That is the only honest install test, and it catches the missing runtime dependency every single time. |
| **Fri 25** | Day five, then the gate question, asked of each engineer **separately so nobody influences anyone**: *would you miss this if it vanished tomorrow?* |

---

## Week 5 · Sep 28 – Oct 2 — onboarding and support

| Day | Work |
| :--- | :--- |
| **Mon 28** | **Write the onboarding flow end to end, as prose, before any of it exists**: purchase → key → install → first signal. Every screen, every email, every click. Writing it now is how you find out that step 6 assumes something untrue — much cheaper today than in Week 7 with a trader on a call watching you discover it. |
| **Tue 29** | Support inbox, docs skeleton, **refund policy — written before the first sale, not after the first refund request.** Keep it generous: at ten subscribers, one unhappy person telling a forum you were difficult about $39 costs more than the $39. |
| **Wed 30** | Walk your onboarding prose against the real thing, step by step. Mark every step that doesn't match. **Do not fix the prose to match the product — mark it, and let the team decide which is wrong.** Usually it's the product. |
| **Thu 01** | Docs skeleton filled: install, connect your feed, read the overlay, journal, troubleshooting. **Troubleshooting is the one that matters** — write it from four weeks of dogfood logs, because those contain every real problem you have actually hit. |
| **Fri 02** | Onboarding finalised against reality. Refund policy published. Support inbox live and monitored. |

---

## Week 6 · Oct 5–9 — copy, the recording, and the purchase flow

| Day | Work |
| :--- | :--- |
| **Mon 05** | Final copy. Then **record a real screen recording of the overlay working** — not a mockup, not a slide, the actual product on a live session flagging a real outlier. **This is the single most important marketing asset you will make**; it's what gets posted in Week 9, and it needs a real session behind it. |
| **Tue 06** | Test the whole purchase flow against the dev `issue-key` route. Every step, as a stranger would, with the onboarding prose open beside you. Mark every mismatch. |
| **Wed 07** | Rehearse purchase → key → install → first signal **twice, timing each step.** If it takes more than ten minutes from card to first signal, say which step is the problem. |
| **Thu 08** | Docs finished. **Support macros** for the five questions you already know are coming (below). |
| **Fri 09** | Gate: one of you buys with a real card, then processes a real refund. **Watch for "well, I had to paste the key manually but that's basically it" — that is a manual step**, and see §"The three sentences". |

---

## Week 7 · Oct 12–16 — you lead the beta

**You lead every call. Prathamesh watches muted. Varad is not on them.**

| Day | Work |
| :--- | :--- |
| **Mon 12** | Confirm all three traders. Schedule three calls. |
| **Tue 13** | **Trader 1.** Screen shared, they install unaided. Write down **every moment of confusion. Do not explain it away** — not in the moment beyond what's needed to unstick them, and especially not afterwards to yourself. *"They were just confused because they didn't read it"* is the sentence that turns a fixable UX bug into a permanent one. Notice which words you needed to say; each one goes in the docs. |
| **Wed 14** | **Trader 2.** Same shape. |
| **Thu 15** | **Trader 3.** Same shape. |
| **Fri 16** | Consolidate three confusion logs into one ranked list. **Rank by how many of the three hit it**, not by how bad it felt. Something all three tripped on is a design flaw; something one person tripped on may be that person. |

---

## Week 8 · Oct 19–23 — rank, and ask the question

| Day | Work |
| :--- | :--- |
| **Mon 19** | **Rank the feedback ruthlessly. Five items.** Then write the **"not now" list and defend it** — by name, with a reason each, so that in Week 10 when someone says "we should just quickly—", the answer already exists in writing. |
| **Tue 20** | Ask each beta trader the only question that matters, **unprompted and separately**: *would you pay $39 for this today?* Do not preface it. Do not explain the value first. Do not ask it in a group. **Record the exact words — including the hedges, especially the hedges.** |
| **Wed 21** | Consolidate into `docs/qa/beta-verdict.md`, **verbatim. Verbatim means verbatim** — *"yeah I'd probably pay for it if it also did X"* is not a yes, and writing it down as one is how a team convinces itself it has a business. |
| **Thu 22** | Week 9 distribution prep: where the demo recording goes, which communities, what the post says. **Draft it now** — Week 9 is heavy and this is the part that gets dropped. |
| **Fri 23** | **The decision gate.** Read `beta-verdict.md` out loud. Count the unprompted yeses. Two or three → Week 9 proceeds. One or zero → Week 9 is **not** "open the doors", it is finding out what would make it a yes, and **the answer is in the hedges you wrote down Wednesday.** |

---

## Week 9 · Oct 26–30 — convert and publish

| Day | Work |
| :--- | :--- |
| **Mon 26** | **Convert beta trader 1 to paid, on a call. Ask for the money directly.** They said yes to $39 unprompted; the only thing between that and a payment is someone asking. **If they hesitate now, that hesitation is more valuable than the original yes** — listen to it rather than rescuing it. |
| **Tue 27** | Convert trader 2. **Publish the demo recording where order-flow traders actually gather** — futures forums, ATAS and Jigsaw communities, the Discords you recruited from. **Not LinkedIn.** Not a general startup launch site. The audience is small, specific, and already knows what a footprint chart is; talk to them like it. |
| **Wed 28** | Convert trader 3. **Answer every reply on the thread, including the sceptical ones, especially the sceptical ones** — order-flow traders are suspicious by disposition, and the scepticism is not hostility, it is the audience doing exactly what you want them to do with a signal. |
| **Thu 29** | **Track why people say no. Every no gets a sentence.** That list is the product roadmap and it's worth more than every feature request you receive — a feature request tells you what someone imagines they want; a no tells you what actually stopped them. |
| **Fri 30** | Gate: subscriber #1. If all three converted you're ahead. **If none converted despite three unprompted yeses, that gap is the most important thing to understand this quarter** — spend the whole afternoon on it. |

---

## Weeks 10–11 · Nov 2–13 — distribution. Target: 7 by Nov 13.

| Day | Work |
| :--- | :--- |
| **Mon** | Write the week's **order-flow teardown**. |
| **Tue** | Publish it. **Answer every reply.** |
| **Wed–Thu** | Onboarding calls with every new subscriber. **Log every no with its reason.** |
| **Fri** | Count: subscribers, why each bought, why each no said no. |

**The teardown rule.** *One genuinely useful order-flow teardown per week — not an ad.* A teardown
is: here's a real session, here's what the delta did at this level, here's what that meant, here's
what happened next. **It is useful whether or not the reader ever buys anything.** If it doesn't
stand alone as something worth reading, it's an ad with a chart in it, and this audience recognises
that instantly and stops reading you. Mention the product once, at the end, or not at all — the
Week 6 recording does the selling.

**The onboarding rule.** Every new subscriber gets a call. Every single one, all ten. **This does not
scale and it is not supposed to** — you're buying the thing that only exists at this size: watching
ten people's first hour and understanding exactly why they bought. That understanding is the Week 11
gate, and no analytics substitutes for it.

| Target | End W10 · Nov 06 | End W11 · Nov 13 |
| :--- | :--- | :--- |
| Paying subscribers | 5 | **7** |
| Teardowns published | 1 | 2 |
| Onboarding calls | every subscriber | every subscriber |
| Nos logged with reasons | all | all |

**At three on 6 Nov** → distribution reach is the problem, not product; you've proven people pay.
Double the teardown cadence, add a second community.
**At seven but three have stopped opening the app** → distribution isn't the problem and Week 12's
retention check is going to hurt. Deal with it in Week 11.

---

## Week 12 · Nov 16–20 — count what's true

| Day | Work |
| :--- | :--- |
| **Mon 16** | **Retention check. Is anyone still using it in week four of their subscription?** Telemetry per subscriber: sessions opened, signals acted on, journal entries written. **Someone who paid and stopped opening it is a churn in six weeks that you can still prevent this week.** |
| **Tue 17** | **Call every subscriber who has gone quiet. Not a survey — a call.** Ask what happened. The answer is almost never "it was bad"; it's usually something specific and fixable they didn't consider worth reporting. |
| **Wed 18** | Consolidate the "why they said no" list from Weeks 9–11 into ranked themes. **That is the quarter-two roadmap, and it was written by the market rather than by the three of you.** |
| **Thu 19** | Quarter-two decision, all three. Your numbers answer question 2 (do people keep using it) and question 4 (what did the nos say). **Below 50% at week four means the product is a demo, however good the signal.** |
| **Fri 20** | Final gate and the write-up. |

---

## The calls you own

Ask the **exact** question. Do not soften it, do not add context, do not bundle three into one — a
softened licensing question gets a softened answer, and a softened answer is worthless.

**Feed licensing** · Week 1 Day 1, identically worded to all three vendors:

> *"Our software runs on the end user's machine and connects using the user's own data entitlement.
> Market data does not pass through our servers. Do we need a distribution licence?"*

Verbatim replies into `docs/qa/licensing.md`. **Must be answered in writing by Week 3.**

**SEBI Research Analyst** · Week 1, with the CA. The distinction that decides it: *charging for
analytics a trader interprets* is different from *charging for recommendations*. **Our copy decides
which side we land on** — and copy is cheap to change before launch, expensive after. **You write
the copy, so this is genuinely your call to make** with the CA's answer in hand.

**Export structure with LUT** · same call.

**Razorpay** · Week 1 Day 4, to a **human**: do international cards work on recurring subscriptions
for our entity type? If not — merchant-of-record for global cards at ~5%, Razorpay for domestic UPI.
**No crypto**, it breaks the compliant export path.

---

## Release QA — run before every release

1. Install **on a machine that has never had the dev environment on it.** The only honest install
   test; catches the missing runtime dependency every time.
2. Mac: does Gatekeeper let it through **silently**? Windows: does the "Run anyway" note match what
   actually appears, **word for word**?
3. Paste a key. Then one with trailing whitespace, one with the wrong prefix, and one twice.
4. **Pull the network cable.** Does it degrade to *offline* — keeps working, retries quietly — and
   **not** to *lapsed*? These must look different.
5. Connect a feed, run a full session, compare CVD against ATAS at every 15-minute mark.
6. Write a journal entry offline, reconnect, confirm it synced and **nothing was lost.**
7. Trigger a rule violation on a live trade.
8. Check Sentry received nothing it shouldn't have — **no ticks, no prices, no screenshots.**

---

## The five support questions you already know are coming

Write the macros in Week 6, before the first sale.

1. **How do I connect my feed?** — they bring their own CME entitlement, ~$12–15/mo non-professional.
2. **Why is my delta different from my broker's?** — different session boundaries or a different
   aggressor convention. Point at the reference session.
3. **My key doesn't work.** — expired, revoked, or whitespace. All three look identical to them.
4. **Windows says the app is unsafe.** — unsigned build, "More info → Run anyway". One sentence, no
   apology. We buy the certificate at ~50 users.
5. **How do I cancel?** — short and easy. Fighting a $39 cancellation costs more in one forum post
   than the $39.

---

## The three sentences that make you useful

> **"I don't think that flag is right."** — Week 3 onward, and it stops the sprint.

> **"That's a manual step."** — Week 6, when someone wants to count a purchase flow that needed a
> human awake.

> **"That's not a yes."** — Week 8, when a beta trader says *"yeah I'd probably pay for it if it
> also did X"* and someone writes it down as a yes.

Each is worth more than a week of anyone's engineering, and each is uncomfortable to say out loud.
**Say them anyway.**
