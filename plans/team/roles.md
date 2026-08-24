# Roles — who owns what, and who decides

Ownership is **by system, not by task queue**. Owning a system means you get to say no to things
that damage it, and it means nobody else edits it without asking you. A task queue makes three
people into one person with three hands; system ownership makes three people into three people.

---

## Prathamesh · Engineer 1 · **Shell** (blue)

Everything the user touches.

**Owns:** the Tauri window and its overlay behaviour · the React UI ported from `apps/extension` ·
screen capture · packaging, code signing, auto-update · the four website pages · from Week 5, the
user-facing half of the backend.

**Your folder:** [`prathamesh/`](prathamesh/README.md) — the schedule, and [`ramp.md`](prathamesh/ramp.md)
for the backend path.

**Directories:** `apps/desktop/`, `apps/web/`, `apps/extension/`, and from Week 6
`services/api/app/routes/journal.py` and `entitlements.py`.

**The frontend → backend ramp.** You are frontend-first and the schedule respects that. Weeks 1–4
are pure shell work. Week 5 you build the desktop side of the key flow — still frontend, but you
are now reading an API contract you didn't write. Week 6 you take your first backend route:
**journal sync**, chosen deliberately because you already own the journal UI, so you are writing a
server for a client you understand. Week 9 you take entitlement gating. By Week 12 you own two
route modules outright.

**Decides:** anything about how the product looks, feels, installs and updates. If you say a UI
change makes the overlay worse, that is final.

**Failure mode:** polishing the UI while the engine is unproven. The UI is already good — it
survived a full port and a browser-extension rewrite. Resist redesigning it until a real trader
has used it. Concretely: in Weeks 1–3, if you catch yourself in a CSS file for more than an hour,
stop and go to the Float row.

---

## Varad · Engineer 2 · **Signal + backend** (teal)

Everything that turns ticks into a number, and everything that lives on a server.

**Owns:** feed adapters · the delta/CVD/footprint engine · the outlier rules from `strategy.md` ·
the backtest harness · the honest measurement of whether any of it predicts anything · FastAPI,
Postgres, auth, keys, metering, webhooks.

**Your folder:** [`varad/`](varad/README.md) — the schedule, and [`thresholds.md`](varad/thresholds.md),
which is due Thursday of Week 1.

**Directories:** `services/signal-data/`, the Rust engine crate (new, `services/engine/`),
`services/api/` (minus the two route modules that transfer to Prathamesh).

**Languages:** Rust for the engine, Python for research and the API. You already own
`services/api` and wrote the Databento puller, so this is continuous with what you have.

**Decides:** what counts as a signal, what the thresholds are, and whether a measurement is honest.
If you say the edge test was flat, it was flat.

**Failure mode:** falling in love with a signal and never running the null test. Guard against it
mechanically — **write the success threshold down on Thursday morning of Week 1, before you look at
any results, and commit it.** A threshold chosen after seeing the distribution is not a threshold.

---

## Shreyas · Engineer 0 · **Product, QA, ops** (ochre)

The most underrated seat here, and the easiest to under-use.

**Owns:** vendor and compliance calls · beta trader recruitment · the test protocol · design
polish and landing copy · support · release QA · AI-assisted code review · and the one that
matters most, **domain validation** — sitting with the live overlay and judging whether what it
flags matches what an order-flow trader would actually call an outlier.

**Files:** [`shreyas/`](shreyas/README.md) is your folder — the schedule, [`grading.md`](shreyas/grading.md)
and [`review-rubric.md`](shreyas/review-rubric.md). `docs/qa/` is yours. You open issues;
you do not open PRs against `services/` or `apps/src`.

**You are not technical, and that is not a gap here.** Two of the three highest-risk items in this
plan are phone calls, not code: the bring-your-own-feed licensing answer and the SEBI Research
Analyst question. Both are yours. If either comes back wrong, no amount of Rust helps.

**On code review:** you review through Claude, with a fixed rubric, and the rubric is built around
what that method genuinely catches — contract drift, missing tests, secrets in a diff, scope creep,
undocumented behaviour changes. It does not catch subtle concurrency bugs in the Rust engine, and
[`review-rubric.md`](shreyas/review-rubric.md) says so plainly rather than pretending otherwise. Catching the first four on every PR
is worth more than you think: a leaked key in `.env.example` was staged once already on 25 Aug and
only caught by chance.

**Decides:** whether a signal is right. **If Shreyas says the signal looks wrong, that stops the
sprint.** Not "gets logged". Stops it.

**Failure mode:** being treated as a helper rather than an owner. The two engineers cause this, not
Shreyas. Watch for it in standup — if two days pass where Shreyas only reports on things the
engineers asked for, the seat is being misused.

---

## Decision rights, when you disagree

| Question | Decides | Everyone else |
| :--- | :--- | :--- |
| Is this a real signal? | Shreyas | Can argue, cannot override |
| Is this measurement honest? | Varad | Can argue, cannot override |
| Does this ship to users? | Prathamesh | Can argue, cannot override |
| Do we slide a gate? | All three, unanimous | No unanimity = gate does not slide |
| Do we spend money? | Varad, against the budget in the artifact | Ceiling is $280–300; run rate is $84–126 |

---

## A note on the reassignment

`plans/current.md` currently has Prathamesh on the Databento pull (#6) and the delta/CVD work (A1),
with Varad on the spot-XAUUSD correlation (A2). **This plan swaps that**, per the split above:
signal work is Varad's, shell work is Prathamesh's. Two consequences worth naming:

- Item **A2** (spot XAUUSD correlation) is **cut**, not reassigned. The artifact's Fact Two rules
  out spot gold as a launch instrument — it has no centralised volume, which is exactly why
  `real_volume` comes back empty on MT5. The correlation study was scoping a product we are no
  longer building first. It moves to the Week 12 quarter-two discussion.
- Item **#6** (run the Databento pull for real) moves to Varad and happens in Week 0, not Week 1,
  because Week 1 Day 1 assumes the data is already on disk.

`plans/current.md` has been updated to say this.
