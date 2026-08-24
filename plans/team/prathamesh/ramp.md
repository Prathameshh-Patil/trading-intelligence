# The frontend → backend ramp

You are frontend-first and the schedule respects that. Weeks 1–4 are pure shell work. Then you take
backend in three deliberate steps, each chosen so you are never writing a server for a client you
don't understand.

By Week 12 you own two route modules outright.

---

## Step 1 · Week 5 — consume a contract you didn't write

**No backend code. You read an API spec and build against it.**

You build the entire key flow against `services/api/tests/fixtures/keys_fake.py` — a 30-line fake
Varad committed on 28 Aug, running on port 8001. It returns **all six branches** of the
key-validate contract, including the three failure branches a real backend would take days to let
you reproduce naturally.

What you learn here: how to read an HTTP contract as a spec rather than as documentation, and why
`valid: false` is a **200 and not a 401**. That distinction is the whole reason offline and lapsed
can look different in the UI — a 401 conflates "your key is bad" with "we couldn't reach the
server", and conflating those either locks out a paying subscriber on a bad WiFi day or silently
gives the product away.

On **Wednesday 30 Sep** you change one URL and point at the real backend. If anything else needs
changing, a contract leaked. That's the point of the scheduled swap-in.

---

## Step 2 · Week 6, Thursday 8 Oct — your first route

**`POST /api/v1/journal` and `GET /api/v1/journal?since=`**, per [`../contracts.md`](../contracts.md) S4.

This is the first route on purpose, and the reasoning matters:

- **You already own the journal UI.** You are writing a server for a client you built yourself, so
  you already know every way it will be called.
- **It is local-first.** The app works completely offline, forever. If your route is broken for a
  day, nobody notices except a "last synced" timestamp going stale. The blast radius of your first
  backend mistake is approximately zero — which is exactly what you want for a first backend
  mistake.
- **The conflict rule is a product decision, not a technical one.** Last-write-wins by
  `updated_at`, **and the loser is kept.** A trader's journal entry is never silently discarded
  because two devices disagreed. You are the right person to make that call because you know what
  the journal is for.

**Varad reviews it. He does not write it.** He comments on the migration, the idempotency, and the
index on `(user_id, updated_at)`, and you fix them. If he rewrites it, you don't become a backend
engineer and he owns two more route modules for the rest of the year. That is written into his file
too, so hold him to it.

What you'll touch for the first time: Alembic migrations, SQLAlchemy models, a FastAPI router, and
pytest against a real database. `services/api` already has all four working and 17 tests passing —
read `app/analysis.py` and `tests/test_api.py` before you start. The `503` shape used for upstream
failure is the house style; match it.

---

## Step 3 · Week 9, Tuesday 27 Oct — entitlement gating, front to back

**The journal add-on gated behind its own tier.**

Varad populates `tier` in the key-validate response — the field has existed in the frozen contract
since Week 1, so **no contract change is needed.** That's what freezing it bought.

You own everything downstream: read the tier, gate the UI, and handle **the tier changing
mid-session without a restart.** That last part is the interesting one and it is genuinely full
stack — someone clicks upgrade on the website, the webhook fires, the backend updates the
entitlement, and the desktop app has to notice within seconds without the user doing anything.

This is the first time you own a feature that crosses all three of website, backend and desktop.
It is week nine, and by then you will have touched all three.

---

## What stays Varad's

So the boundary is clear and nobody has to ask:

- The Rust engine, feed adapters, delta arithmetic, outlier rules, backtest harness
- Clerk auth wiring, key issue and revoke, usage metering
- Payment webhooks, signature verification, idempotency
- Postgres schema design and rate limiting

If you want any of it later, that's a conversation in Week 12 — not a thing that happens quietly
during a sprint.

---

## The one backend rule you cannot break

**No market data on our servers. Ever.**

Not a tick, not a price series, not a screenshot, not in a log line, not in a telemetry field. This
is not a preference or a performance choice — it is the licensing boundary the entire architecture
rests on. Data flowing through our servers to subscribers makes us a data distributor, and the
cheapest honest version of that is Databento Plus at **$1,750/month** plus a separate CME derived-data
licence running into five figures per instrument per year. Roughly twenty times the whole budget.

Deleting that one hop is what makes this business possible. If a route you're writing would accept
a tick, the answer is no, and there is no version of the requirement that changes it.
