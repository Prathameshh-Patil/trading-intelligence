# Gates — every Friday, 16:00, all three in a room

A gate is a **binary question with evidence attached**. "The engine works" is not a gate. "Live
delta matched a reference footprint chart for a full session, and here is the side-by-side" is.

**If a gate is not met, next week is the same gate.** Not the same gate plus next week's work. The
correct response to a missed gate is to lose a week, deliberately, with everyone knowing. Sliding
gates is how twelve-week plans become nine-month plans, and it happens one reasonable-sounding
Friday at a time.

A gate slides only on **unanimous** agreement from all three. No unanimity means it does not slide.

---

| Wk | Ends | Gate | Evidence that counts |
| :--- | :--- | :--- | :--- |
| **0** | Aug 30 | Days 1–3 debt is cleared; every open checkbox in `current.md` is closed or explicitly killed | A real Tauri window screenshotted on-device **— met, 3 Sep** · ~~real Databento row counts~~ **met by `8aece67`** · extension reloaded in a real Chrome (and Firefox) profile **— reported met ~28 Aug, not contemporaneously logged, see `current.md` #2/#8** · one live Claude analysis returned — **parked, own-model decision** · the S1 fixture committed **— met** · a reference-chart path chosen **— met, `c504e50`** · **the Anthropic key rotated** — **still open** |
| **1** | Sep 04 | **Does this project deserve to exist** | A forward-return distribution over one month, measured against a threshold **written down Thursday morning before results were seen** · a live feed held 30 min with no desync · a Tauri window floating over MT5 · licensing answered in writing by ≥1 vendor |
| **2** | Sep 11 | Engine has tests; overlay behaves like an overlay | `cargo test` green against the committed fixture session · click-through into MT5 demonstrated · position memory survives a restart · global hotkey works with MT5 focused |
| **3** | Sep 18 | **Live delta on screen, matching a reference footprint chart, for a full session** | Side-by-side screen recording, our overlay and ATAS/Sierra, same session, CVD agreeing at every 15-min mark |
| **4** | Sep 25 | All three ran it live for five consecutive sessions and would miss it if it vanished | Five dogfood logs per person · installers built for Mac and Windows · rule-violation warning fired on a real live trade |
| **5** | Oct 02 | A key issued by the backend unlocks the desktop app end to end | Screen recording: key issued from a `curl`, pasted into the app, feature unlocks · offline degradation demonstrated by pulling the network cable |
| **6** | Oct 09 | **One of you buys it with a real card and installs from the email. No manual steps.** | Bank statement line · the email as received · install completed from the link in it · then a real refund processed |
| **7** | Oct 16 | Three outside traders installed unaided and used it for a full session | Three confusion logs, written by Shreyas while watching their screens · Sentry shows three distinct machines · zero installs that needed a call to complete |
| **8** | Oct 23 | **At least two of three beta traders say yes to $39, unprompted** | Their words, quoted verbatim, in `docs/qa/beta-verdict.md`. Unprompted means they said it before being asked to say it |
| **9** | Oct 30 | Subscriber #1 exists and paid real money | A payment that is not from one of you |
| **10–11** | Nov 13 | Seven paying subscribers, and you know why each one bought | Seven payments · seven one-paragraph "why they bought" notes, one per subscriber, from Shreyas's onboarding calls |
| **12** | Nov 20 | **Ten paying subscribers, positive gross margin, ≥50% still active after a month** | Ten payments · run rate vs revenue on one line · usage telemetry per subscriber |

---

## The three gates that can end the project

**W1 — the edge test.** If the forward-return distribution is flat against the pre-written
threshold, the honest move is to spend Week 2 testing a second formulation from `strategy.md`,
not to start building. Two weeks of research beats six months of building the wrong thing. This is
the whole reason Week 1 is called kill week and the whole reason its code is throwaway.

**W3 — live delta matching a reference.** If our CVD doesn't agree with a real footprint chart, we
do not have a product, we have a plausible-looking number.

**This gate is already open and already documented.** `DELTA_CVD_FINDINGS.md` §3 marks it *NOT DONE
— hard gate open*, and is right to: everything confirmed so far is internal consistency, which
cannot catch a wrong contract, a timezone offset, a differing session boundary, or a systematic
magnitude error. The blocker is that ATAS and Sierra are Windows-only and the machine is an ARM Mac.
See [`week-00.md`](week-00.md) for the three ranked options. **A TradingView tick-rule
approximation does not clear this gate** — useful for direction and turning points, not for
tick-for-tick magnitude — but run it anyway in Week 0, because it costs nothing and would catch a
timezone or contract error three weeks early.

The usual advice is to check the `aggressor_side` mapping first. **Here, check it last** — it now
has three independent confirmations. Check timezone, then contract, then mapping.

**W8 — would you pay $39.** Two of three saying yes unprompted is the difference between a product
and a hobby. If the answer is "it's cool, but" from all three, Week 9 is not "open the doors", it
is finding out what would make it a yes.

## The gate that is easiest to fake and matters most

**W6 — buy it with a real card, no manual steps.** Everyone is tempted to count "well, I had to
paste the key manually but that's basically it." That is a manual step. Ten subscribers you
onboard personally is fine; a checkout that silently requires you to be awake is not, and you will
not find out until the first sale arrives at 3am from a different timezone.
