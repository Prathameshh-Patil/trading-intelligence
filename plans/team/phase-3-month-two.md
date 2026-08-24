# Phase 3 · Weeks 5–8 — Make it sellable

**Mon 28 Sep – Fri 23 Oct**

Now — and **only** now — the backend, the website, and the payment path. This is the part that
looks like a startup and it is the **least risky work in the plan**. Every fatal-risk item was
settled in the first four weeks. If this month feels easier than last month, that is correct and
not a sign you've missed something.

This is also where **Prathamesh's frontend → backend ramp begins.** Week 5 he consumes an API
contract he didn't write. Week 6 he writes his first route. Week 9 he owns entitlement gating.

---

# Week 5 · Sep 28 – Oct 02 — Backend

Small on purpose. **Keys, auth, metering. Nothing else.** Every feature added to the backend this
week is a feature you maintain for twelve weeks and that ten subscribers will not notice.

Remember what this backend is *not*: no market data ever passes through it. That is the entire
licensing argument. If anyone proposes a route that accepts a tick, the answer is no, and the reason
is $1,750/month plus a five-figure CME derived-data licence.

---

#### W5D1 · Mon Sep 28

**P** — Key entry, storage and validation in the desktop app, **pointed at `keys_fake.py` on port
8001** — the fake Varad committed back on 28 Aug. You build the entire key flow today against all
six response branches, including the three failure branches a real backend would take days to let
you reproduce. Store the key in the OS keychain, never in plaintext.

**V** — Postgres schema and Alembic migrations: users, keys, entitlements, usage. Then Clerk auth
wired into FastAPI. You already own `services/api`, migrations are already at head, and the analyze
route's `503` shape is already the house style for upstream failure — match it.

**S** — Write the onboarding flow end to end, as prose, before any of it exists: purchase → key →
install → first signal. Every screen, every email, every click. **Writing it now is how you find
out that step 6 assumes something that isn't true** — which is much cheaper today than in Week 7
with a trader on a call watching you discover it.

*Float:* if P finishes the key flow early, take the auto-update channel — it's Wednesday's, and
update infrastructure is the thing you most want working *before* you need to ship a fix.

*Why nobody is blocked:* P is against a fake that has existed for a month. V is building the real
thing. They meet Wednesday.

---

#### W5D2 · Tue Sep 29

**P** — Graceful degradation: offline, and key lapsed. These are **different** and must look
different. Offline = we can't reach the server, so keep working exactly as normal and retry quietly
— a trader's session must never depend on our uptime. Lapsed = the server told us the key is dead,
so degrade visibly and explain how to fix it. Conflating them either locks out a paying subscriber
on a bad WiFi day or silently gives away the product. This is why `contracts.md` S3 returns
`valid: false` as a 200 rather than a 401.

**V** — API key issue and revoke, plus usage metering. Then the dev-only `POST /api/v1/dev/issue-key`
route (**S5's fixture**), gated on a config flag, with a test asserting the flag is `false` in
production config. That route is what lets Prathamesh build and test the entire Week 6 purchase
flow without a payment processor existing.

**S** — Support inbox, docs skeleton, refund policy. The refund policy needs writing **before** the
first sale, not after the first refund request. Keep it generous — at ten subscribers, one unhappy
person telling a forum you were difficult about $39 costs more than the $39.

*Float:* if V finishes early, rate limiting on Upstash — it's Wednesday's.

---

#### W5D3 · Wed Sep 30 — **S3 swap-in**

**P** — Repoint the desktop app from `keys_fake.py` to the real backend. **Change one URL.** If
anything else needs changing, the contract was violated somewhere and today is the day to find out
— that is exactly what this scheduled swap-in is for. Budget an hour; if it takes a day, say so
loudly, because it means a seam leaked and other seams may have leaked too. Then: auto-update
channel wired up.

**V** — Rate limiting on Upstash. Then harden: what happens when Clerk is down, when Postgres is
down, when a key is validated 10,000 times a minute. Each answer is a `503` in the house shape, not
a traceback. The analyze route already does this correctly — copy it.

**S** — Walk your own onboarding prose against the real thing, step by step, and mark every step
that doesn't match reality. Do not fix the prose to match the product — **mark it, and let the team
decide which one is wrong.** Usually it's the product.

*Float:* if the swap-in goes fast, P starts the four website pages. Week 6 is only three days of
work and starting it Wednesday of Week 5 buys real slack.

---

#### W5D4 · Thu Oct 01

**P** — Auto-update finished and **tested by actually shipping an update** to your own installed
build. Not a dry run. Ship a version bump through the real channel and watch your own machine take
it. Update infrastructure that has never delivered an update is not update infrastructure.

**V** — Usage metering finished, and the end-to-end unlock test written as an automated test: issue
a key via API → validate it → confirm the tier. Then start on the payment webhook handler — Week 6
is short and the webhook is the part with the sharp edges.

**S** — Docs skeleton filled: install, connect your feed, read the overlay, journal, troubleshooting.
Troubleshooting is the one that matters — write it from the four weeks of dogfood logs, because
those contain every real problem you have actually hit.

*Float:* whoever is free tests the offline and lapsed paths by physically pulling the network cable.
Simulated offline is not offline; the OS behaves differently and so does the HTTP stack.

---

#### W5D5 · Fri Oct 02

**P** — Polish the key flow's edge cases: pasted with whitespace, pasted with the wrong prefix,
pasted twice, pasted while offline. All four will happen in Week 7 with a trader watching.

**V** — Backend hardening and deploy to Railway or Fly. **A backend that only runs locally has not
been tested.** Confirm the Postgres connection from the deployed environment and the `503` when it
drops — the `/api/v1/health/db` route already proves this locally, so prove it in production too.

**S** — Onboarding prose finalised against reality. Refund policy published. Support inbox live and
monitored.

**ABC · 16:00 — Week 5 gate.**

### Gate — Week 5
- [ ] A key issued by the backend unlocks the desktop app end to end — recorded
- [ ] Offline degradation demonstrated by **physically** pulling the network cable
- [ ] Lapsed-key degradation visibly different from offline
- [ ] Auto-update delivered a real update to a real installed build
- [ ] Backend deployed, not just local; `503` shapes verified in production
- [ ] The S3 swap-in took an hour, not a day

---

# Week 6 · Oct 05 – Oct 09 — Website: three days, then stop

**Four pages. Landing, pricing, post-purchase key page, login.** Resist everything else.

"Website" feels big because it gets conflated with marketing site plus docs plus dashboard plus
billing portal. At ten subscribers you need four pages and Clerk does most of the login. It is
three days of work and it is the **lowest-risk item in the entire plan** — which is exactly why it
comes in Week 6 and not Week 1.

**Cloudflare Pages, not Vercel.** Vercel's Hobby tier explicitly prohibits commercial use, and
"any method of requesting or processing payment from visitors" counts — a landing page with a
checkout button is commercial. That is $20/month for Pro, avoided. Cloudflare Pages permits
commercial use on the free tier.

**This is Prathamesh's first backend route.** Journal sync (`contracts.md` S4) is deliberately the
first one: he already owns the journal UI, so he is writing a server for a client he understands.

---

#### W6D1 · Mon Oct 05

**P** — Landing and pricing pages on Cloudflare Pages, from Shreyas's Week 4 copy. Static, fast,
honest. The pricing page states $39/mo core, $4.99/mo journal add-on, and the **founding price for
the first ten, permanent, said plainly.** Saying it plainly is what buys honest feedback instead of
polite feedback.

**V** — Payment webhook handler with **idempotency on `event_id`**. Webhooks arrive twice. They
arrive out of order. They arrive months late. The handler is idempotent or it issues two keys and
bills once — and you will find out from a confused subscriber, not from a log.

**S** — Final copy, and record a **real screen recording of the overlay working**. Not a mockup, not
a slide — the actual product on a live session, flagging a real outlier. This recording is the
single most important marketing asset you will make, it is what gets posted in Week 9 where
order-flow traders gather, and it needs a real session behind it.

*Float:* if P lands both pages by mid-afternoon, start the post-purchase key page — it's Tuesday's.

---

#### W6D2 · Tue Oct 06

**P** — Post-purchase key page and login. The key page polls `GET /api/v1/keys/mine` per
`contracts.md` S5: every 2s for 30s, then a support link. **Payments settle asynchronously** — a
key page that assumes the key exists on first load will show an error to roughly one buyer in five,
and that buyer has just paid you.

**V** — Key issuance behind the webhook, plus replay handling. Then a test that fires the same
webhook five times and asserts one key exists.

**S** — Test the whole purchase flow against the dev `issue-key` route. Every step, as a stranger
would, with the onboarding prose open beside you. Mark every mismatch.

*Float:* download links per platform, with the Windows "Run anyway" note written in Week 4 —
whoever is free.

---

#### W6D3 · Wed Oct 07

**P** — Checkout integration with whichever processor Shreyas confirmed in Week 1. **Website work
ends today.** Anything not done by 18:00 goes on a list and stays there — the four pages are done
or they are good enough, and a fifth page is not happening this quarter.

**V** — Keep tuning thresholds against accumulated grading logs. **This is your background task from
here to Week 12** — an hour a day, not a sprint. Signal quality is the product; it does not get a
week, it gets a habit.

**S** — Rehearse the full purchase → key → install → first signal flow twice, timing each step.
If it takes more than ten minutes from card to first signal, say which step is the problem.

*Float:* none — P finishes checkout, V tunes, S rehearses.

---

#### W6D4 · Thu Oct 08 — **Prathamesh's first backend route**

**P** — Build `POST /api/v1/journal` and `GET /api/v1/journal?since=` per `contracts.md` S4.
Last-write-wins by `updated_at`, **and the loser is kept** — a trader's journal entry is never
silently discarded because two devices disagreed. You own this route from today.

You are writing Python against a schema Varad designed, for a client you built yourself. That is
the easiest possible first backend task and it is chosen that way on purpose. Varad reviews it;
he does not write it.

**V** — Review P's route. **Review, not rewrite.** Comment on the migration, the idempotency, the
index on `(user_id, updated_at)`, and let him fix them. If you rewrite it, he does not become a
backend engineer and you own two more route modules for the rest of the year.

Then: end-to-end payment test against the processor's sandbox.

**S** — Docs finished. Support macros written for the five questions you already know are coming:
how do I connect my feed, why is my delta different from my broker's, my key doesn't work, Windows
says the app is unsafe, how do I cancel.

*Float:* if P's route lands early, wire journal sync into the desktop app — his own client, his own
server, closing the loop.

---

#### W6D5 · Fri Oct 09 — **the gate that gets faked**

**One of you buys it with a real card and installs from the email. No manual steps.**

Everyone is tempted to count "well, I had to paste the key manually but that's basically it." **That
is a manual step.** Ten subscribers you onboard personally is fine; a checkout that silently
requires you to be awake is not, and you will not find out until the first sale arrives at 3am from
a different timezone.

**Then process a real refund**, through the real processor, and confirm the key is revoked and the
desktop app degrades to the lapsed state — not the offline state.

**ABC · 16:00 — Week 6 gate.**

### Gate — Week 6
- [ ] A real card was charged — bank statement line exists
- [ ] The email arrived, unprompted, and the install completed from the link in it
- [ ] **Zero manual steps** between payment and working software
- [ ] A real refund processed; key revoked; app showed **lapsed**, not offline
- [ ] The same webhook fired five times produced exactly one key
- [ ] Prathamesh's journal route is merged, reviewed not rewritten

---

# Week 7 · Oct 12 – Oct 16 — Private beta: three outside traders

**The first time someone who doesn't love you uses it.** Everything until now has been graded by
people who want it to work.

---

#### W7D1 · Mon Oct 12

**P** — Signed Mac build with notarization, verified by downloading it on a clean Mac and watching
Gatekeeper let it through silently. Windows build with the install note. Both on the download page.

**V** — Telemetry: which signals fire, which get acted on, which get dismissed. **Privacy line, and
it is not negotiable: no market data, no tick data, no screenshots leave the machine.** Signal IDs,
timestamps, outcomes. Nothing that could reconstruct a feed. Say so on the pricing page.

**S** — Confirm all three beta traders for this week. Schedule three calls. **You are on every call,
watching their screen, saying nothing unless they are truly stuck.** Every word you say to help them
is a word you'll have to put in the docs later, so notice which words you needed.

*Float:* whoever is free does a final pass on the install notes.

---

#### W7D2 · Tue Oct 13 — beta trader 1

**S leads.** Call, screen shared, trader installs unaided. Write down **every moment of confusion.
Do not explain it away** — not in the moment beyond what's needed to unstick them, and especially
not afterwards to yourself. "They were just confused because they didn't read it" is the sentence
that turns a fixable UX bug into a permanent one.

**P** — On call, muted, watching. Do not jump in. Every time you want to say "you just have to
click—", that is a UX bug and you should write it down instead.

**V** — Not on the call. Signal quality tuning, and standing by for anything that breaks.

---

#### W7D3 · Wed Oct 14 — beta trader 2

Same shape. **S leads, P watches muted, V standing by.**

**V** — Fix whatever broke on trader 1's machine. It will be something you didn't anticipate: a
different vendor account tier, a different Windows locale, a symbol format you've never seen, a
timezone that isn't yours. **A machine that isn't yours is a different machine in ways you cannot
enumerate in advance** — which is the entire reason this week exists.

---

#### W7D4 · Thu Oct 15 — beta trader 3

Same shape.

**P** — Crash reporting to Sentry, live, with source maps, before this call. Trader 3 is your last
chance to catch a crash on a machine you don't own before Week 9's paying subscribers.

---

#### W7D5 · Fri Oct 16

**S** — Consolidate three confusion logs into one ranked list. Rank by **how many of the three hit
it**, not by how bad it felt. Something all three tripped on is a design flaw; something one person
tripped on may be that person.

**P + V** — Read the list together, without defending anything. The rule for today: you may ask
clarifying questions, you may not explain why the user was wrong.

**ABC · 16:00 — Week 7 gate.**

### Gate — Week 7
- [ ] Three outside traders installed **unaided** and used it for a full session
- [ ] Zero installs required a call to complete
- [ ] Sentry shows three distinct machines, real sessions
- [ ] Three confusion logs written by Shreyas, consolidated and ranked
- [ ] Telemetry confirmed to carry no market data

---

# Week 8 · Oct 19 – Oct 23 — Fix the five things

**Beta feedback, ranked, top five only. Everything else goes on a list and stays on it.**

The list is not a backlog you'll get to. It is a record of things you decided not to do, and
Shreyas's job this week is to defend it. A team that fixes fifteen things in Week 8 ships nothing
in Week 9.

---

#### W8D1 · Mon Oct 19

**S** — Rank the feedback ruthlessly. Five items. **Then write the "not now" list and defend it** —
by name, with a reason each, so that in Week 10 when someone says "we should just quickly—", the
answer already exists in writing.

**P** — Start the top UX fix from the confusion log.

**V** — Signal quality fixes **from real usage, not from your own backtest**. The distinction is the
whole point of Week 7: your backtest says what the rule does on data you chose; the telemetry says
what it does on trades a stranger took. When they disagree, the stranger is right.

---

#### W8D2 · Tue Oct 20

**P** — UX fixes two and three.

**V** — Performance: **the overlay must not stutter a live chart.** Profile the compositing path
against Prathamesh's Week 2 frame-timing numbers. A trader forgives a wrong signal before a laggy
chart, because the second one is their fault to fix and they'll fix it by uninstalling.

**S** — Ask each beta trader the only question that matters, **unprompted and separately**:
*would you pay $39 for this today?* Do not preface it. Do not explain the value first. Do not ask
it in a group. Record the exact words of the answer — including the hedges, especially the hedges.

---

#### W8D3 · Wed Oct 21

**P** — cTrader compatibility pass. Window handle capture, overlay positioning, click-through. It is
the second-most-common platform among the audience and it is a day's work now versus a week later.

**V** — Signal fixes continued. Re-run the harness after every change; the Week 4 reproduction test
is your regression net.

**S** — Consolidate the $39 answers into `docs/qa/beta-verdict.md`, verbatim. **Verbatim means
verbatim** — "yeah I'd probably pay for it if it also did X" is not a yes, and writing it down as
one is how a team convinces itself it has a business.

---

#### W8D4 · Thu Oct 22

**P** — Fixes four and five. Then a full regression pass against Shreyas's Week 2 test protocol.

**V** — The Week 9 prep that is genuinely yours: the journal add-on's entitlement check on the
backend. Prathamesh takes the in-app gating next week; you provide the tier in the key-validate
response, which `contracts.md` S3 already specifies. **No contract change needed** — that is what
freezing it in Week 1 bought you.

**S** — Week 9 distribution prep: where will the demo recording go, which communities, what does the
post say. Draft it now; Week 9 is a heavy week and this is the part that gets dropped.

---

#### W8D5 · Fri Oct 23 — **the decision gate**

**ABC · all three.** Read `beta-verdict.md` out loud. Count the unprompted yeses.

**If it is two or three:** Week 9 is "open the doors" and the plan proceeds unchanged.

**If it is one or zero:** Week 9 is **not** "open the doors". It is finding out what would make it a
yes, and the honest read is that the answer is in the hedges Shreyas wrote down verbatim on
Wednesday. This is a real branch, not a formality, and taking it costs you two weeks against a
twelve-week target — which is survivable. Launching into three polite maybes is not.

### Gate — Week 8
- [ ] **At least two of three beta traders said yes to $39, unprompted**
- [ ] Their exact words are in `docs/qa/beta-verdict.md`
- [ ] Five fixes shipped; the "not now" list exists and is defended by name
- [ ] Overlay does not stutter a live chart — measured, against Week 2's baseline
- [ ] cTrader works
