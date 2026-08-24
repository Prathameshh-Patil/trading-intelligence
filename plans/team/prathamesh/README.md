# Prathamesh — your twelve weeks

**Engineer 1 · Shell · everything the user touches.**

You own: the Tauri window and its overlay behaviour · the React UI ported from `apps/extension` ·
screen capture · packaging, signing, auto-update · the four website pages · and from Week 5, the
user-facing half of the backend.

**Directories:** `apps/desktop/`, `apps/web/`, `apps/extension/`, and from Week 6
`services/api/app/routes/journal.py`, from Week 9 `entitlements.py`.

**Read before you write any code:** [`../contracts.md`](../contracts.md). Your independence from
Varad is entirely built on S2 (engine IPC) and S3 (API key) — types frozen Week 1, fakes you build
yourself, real implementations swapped in on two scheduled days.

**Your ramp into backend:** [`ramp.md`](ramp.md).

**Your failure mode:** polishing the UI while the engine is unproven. The UI is already good — it
survived a full port and a browser-extension rewrite. Concretely: in Weeks 1–3, if you are in a CSS
file for more than an hour, stop and take the Float item.

---

## Week 0 · Aug 26–28 — clear the debt

| Day | Work |
| :--- | :--- |
| **Wed 26** | Load the rebuilt extension in a **real Chrome profile** — `955b374` has never been checked in one. Confirm "Capture screen" reads a real selection through the `activeTab` + `chrome.scripting` path. Then the same in Firefox: it installs and CORS accepts it, but no Firefox profile has ever rendered a verdict. *(closes `current.md` #2, #8)* |
| **Thu 27** | `pnpm tauri dev`, on-device, and **look at a real window.** A headless-Chromium screenshot of the compiled bundle is not a native window. All six views render, window size right, zero console errors in the real webview. Screenshot it into `daily_updates/2026-08-27.md`. *(closes #7)* |
| **Fri 28** | Merge PR #3 if review is clean. Branch `feat/tauri-overlay` off `main`. Fresh-clone check: `git clean -xdf` in a scratch copy, `pnpm install`, `pnpm build`, `cargo build`. An hour now; a day in Week 6. |

**Float you can take:** the popup UI review (`current.md` #3) — written from scratch to unbreak a
build, nobody has looked at it as design.

---

## Week 1 · Aug 31 – Sep 4 — kill week

Every line of code you write this week is throwaway. Treat it that way — no abstractions, no file
you'd be sad to delete. The one exception is the type you freeze on Monday.

| Day | Work |
| :--- | :--- |
| **Mon 31** | Strip the Tauri window to the overlay skeleton. No overlay behaviour yet — today is the six ported views rendering at **380px wide**, which is a floating window, not a browser side panel. **Then freeze S2 with Varad**: write `apps/desktop/src/lib/engine/types.ts` from `contracts.md` and commit it. 30 minutes, both of you, one file — **the most valuable half hour of the week.** |
| **Tue 01** | Write `engine/mock.ts` — **S2's fake, and you write it, not Varad.** Replay the fixture session at 10x, emit `DeltaBar` and `Outlier`. The part that matters: make it **misbehave on demand** — go `stale`, drop the connection, emit a 7-digit CVD, emit a 40-char symbol. You need to find out *today* that your layout breaks on a 7-digit CVD, not in Week 3 with a live feed. Then: transparent, borderless, always-on-top, floating over MT5. Install the MT5 demo terminal. Confirm click-through. |
| **Wed 02** | Capture properly: wire `xcap` to capture **the MT5 window by handle**, not the whole screen. Confirm it works whether or not MT5 has focus — that is the whole difficulty, because a trader clicking our overlay takes focus away from MT5 at exactly the moment we need to read it. On Mac, walk the Screen Recording permission prompt and **write down every click** — you'll need it for onboarding docs in Week 5 and you will not remember it then. |
| **Thu 03** | **Live feed spike, in Rust.** Hold an open connection to a real live feed for a full 30 minutes and print trades with aggressor side without dropping or desyncing. Reconnection can wait; continuity cannot. *(Nominally Varad's lane — it's yours today because his whole day is the edge test, and this is the right week for your first Rust contact, on something small, before the Week 5 ramp.)* |
| **Fri 04** | Go/no-go, all three. **Stay quiet until the number is settled** — Varad presents the distribution, Shreyas asks the hard questions. Then help decide launch instrument and feed vendor: you have Thursday's data on whose adapter was least hostile. |

**Float:** Tuesday, if click-through works before lunch — take the **overlay compositing
measurement** early (nominally W2). Watch MT5's frame timing with the overlay on and off. Nobody
has published numbers on a transparent webview compositing over a fast-redrawing chart. Find out in
Week 1, not Week 8.

---

## Week 2 · Sep 7–11 — shell becomes real code

| Day | Work |
| :--- | :--- |
| **Mon 07** | **Click-through and position memory.** Click-through: transparent regions pass clicks to MT5, opaque regions don't — get the hit-test region right, because "sometimes swallows a click on a live chart" loses a subscriber in Week 10 and gets reported as "it feels laggy". Position memory: reopens where the trader left it, per monitor, surviving a monitor being unplugged. |
| **Tue 08** | **Global hotkey** to summon and dismiss, **working while MT5 has focus.** That clause is the entire difficulty — a hotkey that only works when our window is already focused is not a hotkey. Register at OS level on both platforms; pick a default that doesn't collide with MT5 or cTrader bindings. |
| **Wed 10** | Port all six views into Tauri against Shreyas's 380px design. **A port plus a density pass, not a redesign** — the UI survived a browser-extension rewrite; trust it. Everything still renders from `engine/mock.ts`. |
| **Thu 11** | Finish the view port. Then **90 minutes with Varad** defining the Rust↔JS command layer: `invoke` names, event channel names, serde shapes matching S2. The Rust side returns hardcoded data today — that's expected. |
| **Fri 11** | Overlay compositing measurement, if Week 1 didn't get to it. Frame timing with overlay on and off, **numbers written down.** A trader forgives a wrong signal before a laggy chart — the second is their fault to fix, and they'll fix it by uninstalling. |

**Float:** Tuesday, if the hotkey lands by lunch — start the view port. Wednesday is heavy.

---

## Week 3 · Sep 14–18 — live numbers on screen

The milestone that matters most in the quarter.

| Day | Work |
| :--- | :--- |
| **Mon 14** | Feed credential entry and connection status UI. Four states from S2 — and **`stale` is the one that matters**: connected but not receiving, which looks identical to a quiet market and is not. Make the four visually distinct **from three feet away**, because that's the actual viewing distance. Credentials to the OS keychain; never plaintext on disk, never to our servers. |
| **Tue 15** | Wire the **Analyze view to the local engine** instead of the stub API. Delete the `http://localhost:8000` call from the desktop signal path entirely — no signal number crosses a network any more. The one remaining API call from desktop is chart-context extraction, and it sends a screenshot, never a tick. |
| **Wed 16** | 🔴 **INTEGRATION DAY.** All day with Varad. `VITE_ENGINE=real`, pointed at the live feed, live delta streaming at sub-second latency. Then his outlier detector fires and you render it. **Expect the first three hours to be serde mismatches and timezone bugs** — that's why the day is reserved rather than squeezed. |
| **Thu 17** | Capture feeding `symbol` and `timeframe` into the engine's context (S6). Then the ugly cases: symbol not recognised, MT5 minimised, trader on a chart we have no feed for. Each needs a **visible, honest state — never a wrong number, and never a confident one.** |
| **Fri 18** | Polish the five live states: connecting, live, stale, reconnecting, gap-detected. Five clear appearances, tested by **unplugging the network cable** and watching. |

**Float:** Monday, if status UI lands early — wire capture into `setContext`, that's Wednesday's and
Wednesday is the integration.

---

## Week 4 · Sep 21–25 — rules, journal, dogfood

| Day | Work |
| :--- | :--- |
| **Mon 21** | Port the rule engine to local storage. **The same logic you already wrote** — a port, not a rewrite. The `storage.ts` shim from 24 Aug is the only thing that should change. If the two apps' rule behaviour diverges, one is now wrong and nobody notices for a month. |
| **Tue 22** | Port the journal to local storage. **Local-first per S4** — works completely offline, forever, with no backend in existence. Sync is a Week 6 addition that changes nothing about offline behaviour. Build it as if the backend will never exist and you won't have to rebuild it when the backend is late. |
| **Wed 23** | Rule-violation warning firing on **live** trades. The feature that most directly changes trader behaviour, and the most likely to be annoying: get timing and dismissal right, and make sure it cannot fire twice for the same violation. **Ask Shreyas to sit with it before you call it done.** |
| **Thu 24** | First installers. **Mac signed and notarized** — Gatekeeper *blocks* an unsigned build, it doesn't merely warn; $99/yr is already in the budget. **Windows unsigned, deliberately** — Azure's cheap signing service doesn't validate Indian organisations, and an OV cert is $215–260/yr plus a hardware token. Unsigned = "Windows protected your PC → More info → Run anyway". **Write that sentence today** into the install notes. Buy the cert at ~50 users. |
| **Fri 25** | Fix whatever Shreyas's clean-machine install found. There will be something. |

---

## Week 5 · Sep 28 – Oct 2 — backend (you consume it)

Your ramp starts here: you're reading an API contract you didn't write. See [`ramp.md`](ramp.md).

| Day | Work |
| :--- | :--- |
| **Mon 28** | Key entry, storage, validation — **pointed at `keys_fake.py` on port 8001**, the fake Varad committed on 28 Aug. You build the entire flow today against **all six branches**, including the three failure branches a real backend would take days to let you reproduce. Key goes to the OS keychain. |
| **Tue 29** | **Graceful degradation: offline vs lapsed. These are different and must look different.** Offline = we can't reach the server → keep working exactly as normal, retry quietly; a trader's session must never depend on our uptime. Lapsed = the server said the key is dead → degrade visibly, explain the fix. Conflating them either locks out a paying subscriber on bad WiFi or silently gives the product away. This is why S3 returns `valid:false` as a **200, not a 401**. |
| **Wed 30** | 🔴 **S3 SWAP-IN.** Repoint from `keys_fake.py` to the real backend. **Change one URL.** If anything else needs changing, a contract leaked — say so loudly, because other seams may have leaked too. Budget an hour. Then: auto-update channel wired up. |
| **Thu 01** | Auto-update finished and **tested by actually shipping an update** to your own installed build. Not a dry run — bump a version, push it through the real channel, watch your own machine take it. Update infrastructure that has never delivered an update is not update infrastructure. |
| **Fri 02** | Key flow edge cases: pasted with whitespace, wrong prefix, pasted twice, pasted while offline. All four happen in Week 7 with a trader watching. |

**Float:** Monday, if the key flow lands early — take the auto-update channel. You most want update
infrastructure working *before* you need to ship a fix.

---

## Week 6 · Oct 5–9 — the website is three days

**Four pages. Landing, pricing, post-purchase key page, login.** Resist everything else. "Website"
feels big because it gets conflated with docs plus dashboard plus billing portal. At ten
subscribers it's four pages and Clerk does most of the login.

**Cloudflare Pages, not Vercel.** Vercel Hobby prohibits commercial use, and "any method of
requesting or processing payment from visitors" counts — a landing page with a checkout button is
commercial. That's $20/mo avoided.

| Day | Work |
| :--- | :--- |
| **Mon 05** | Landing + pricing on Cloudflare Pages, from Shreyas's Week 4 copy. $39/mo core, $4.99/mo journal add-on, **founding price for the first ten, permanent, said plainly.** Plainly = on the page, in the checkout, in the confirmation email. That's what buys honest feedback instead of polite feedback. |
| **Tue 06** | Post-purchase key page + login. The key page polls `GET /api/v1/keys/mine` per S5: **every 2s for 30s, then a support link.** Payments settle asynchronously — a page that assumes the key exists on first load shows an error to roughly one buyer in five, and that buyer has just paid you. |
| **Wed 07** | Checkout integration with the processor Shreyas confirmed. **Website work ends today.** Anything not done by 18:00 goes on a list and stays there. A fifth page is not happening this quarter. |
| **Thu 08** | 🔵 **Your first backend route.** `POST /api/v1/journal` and `GET /api/v1/journal?since=` per S4. Last-write-wins by `updated_at`, **and the loser is kept** — a trader's journal entry is never silently discarded because two devices disagreed. Varad **reviews** it; he does not write it. |
| **Fri 09** | Gate day: one of you buys it with a real card and installs from the email. |

**Float:** Monday if both pages land early — start the key page. Thursday if the route lands early —
wire journal sync into the desktop app. Your own client, your own server, loop closed.

---

## Week 7 · Oct 12–16 — private beta

| Day | Work |
| :--- | :--- |
| **Mon 12** | Signed Mac build, verified by downloading on a **clean Mac** and watching Gatekeeper let it through silently. Windows build with the install note. Both on the download page. |
| **Tue 13** | Beta trader 1 call. **You are on it, muted, watching.** Do not jump in. **Every time you want to say "you just have to click—", that is a UX bug** — write it down instead. |
| **Wed 14** | Beta trader 2. Same shape. |
| **Thu 15** | Crash reporting to Sentry — live, with source maps — **before** the trader 3 call. Trader 3 is your last chance to catch a crash on a machine you don't own before Week 9's paying subscribers. Then the call. |
| **Fri 16** | Read Shreyas's ranked confusion log with Varad. **Today's rule: you may ask clarifying questions, you may not explain why the user was wrong.** |

---

## Week 8 · Oct 19–23 — fix the five things

| Day | Work |
| :--- | :--- |
| **Mon 19** | Top UX fix from the confusion log. |
| **Tue 20** | Fixes two and three. |
| **Wed 21** | **cTrader compatibility pass** — window handle capture, overlay positioning, click-through. Second-most-common platform in the audience; a day's work now versus a week later. |
| **Thu 22** | Fixes four and five. Full regression pass against Shreyas's Week 2 test protocol. |
| **Fri 23** | Decision gate: count the unprompted $39 yeses. |

---

## Week 9 · Oct 26–30 — open the doors

| Day | Work |
| :--- | :--- |
| **Mon 26** | Pricing page live with the founding-price offer, stated plainly in all three places. |
| **Tue 27** | 🔵 **In-app upgrade path, core → core-plus-journal.** Your entitlement gating, front to back: read the tier, gate the UI, handle the tier changing **mid-session without a restart.** Third route module you own. |
| **Wed 28** | Download and install friction pass from the Week 7 confusion logs. **Every step you delete between "decided to buy" and "seeing a signal" is worth more than a feature this month.** |
| **Thu 29** | Ship the first weekly visible improvement and **tell your subscribers** — however many there are. **Start this rhythm at one subscriber, not at ten.** A product that visibly improves every week retains; a silent one churns at month two regardless of quality. |
| **Fri 30** | Gate: subscriber #1 exists. |

---

## Weeks 10–11 · Nov 2–13 — distribution

Written as a repeating weekly shape, because these genuinely are the same week twice.

| Day | Work |
| :--- | :--- |
| **Mon** | Pick this week's visible improvement from the support log. Small, visible, shippable by Thursday. |
| **Tue–Wed** | Build it. |
| **Thu** | **Ship it, and tell every subscriber.** |
| **Fri** | Install-friction fix from the week's support tickets. |

---

## Week 12 · Nov 16–20 — count what's true

| Day | Work |
| :--- | :--- |
| **Mon 16** | Pay down the **worst** technical debt, not the most. Candidates: the `storage.ts` and `capture.ts` shims marked temporary on 24 Aug and never revisited · any divergence between the desktop and extension rule engines · whatever you've been working around by hand for six weeks. **One item done properly beats five started.** |
| **Tue 17** | Debt item two. |
| **Wed 18** | Debt item three, or stop and stabilise if three feels like reaching. |
| **Thu 19** | Quarter-two decision, all three, from evidence. |
| **Fri 20** | Final gate and the write-up. |

---

## Your gates

| Wk | You must have |
| :--- | :--- |
| 1 | A Tauri window floating over MT5, click-through into MT5 confirmed · `engine/mock.ts` misbehaving on demand |
| 2 | Click-through demonstrated · position memory survives a restart **including a monitor being unplugged** · global hotkey works **with MT5 focused** |
| 3 | Live delta rendering through the real engine, recorded side-by-side with ATAS |
| 4 | Installers for Mac (signed, notarized) and Windows (unsigned, documented) · clean-machine install passes both · rule warning fired on a real live trade |
| 5 | The S3 swap-in took **an hour, not a day** · auto-update delivered a real update · offline ≠ lapsed, demonstrated by pulling the cable |
| 6 | Four pages live · **zero manual steps** between payment and working software · journal route merged, reviewed not rewritten |
| 7 | Three traders installed **unaided** · Sentry live on three distinct machines |
| 8 | Five fixes shipped · overlay does not stutter a live chart, measured against your Week 2 baseline · cTrader works |
| 9 | Upgrade path works mid-session · weekly-improvement rhythm started |
| 12 | Worst debt paid down |

## The one thing you own that can end the project

**Overlay compositing performance.** Nobody has published numbers on a transparent webview
compositing over a fast-redrawing chart. It's probably fine. **Measure it in Week 1 or 2 rather
than discovering it in Week 8**, when the fix would mean rewriting the window layer with a beta
cohort already installed.
