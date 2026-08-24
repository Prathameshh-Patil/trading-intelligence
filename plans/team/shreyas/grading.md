# Domain validation — learning to grade the signal

**This is your most important job in the project.** Neither engineer can grade their own homework.
When you say a flag is wrong, the sprint stops.

---

## Part 1 · Week 0 — learn to read a footprint chart

Three hours, and the highest-leverage thing you do all quarter.

### What a footprint chart shows

A normal candle shows **price over time**. A footprint chart splits each candle **by price level**
and shows, at every level, **how much volume traded at the bid and how much at the ask.** Two
numbers per level instead of one candle.

### The four terms you must explain without notes

**Delta** — ask volume minus bid volume. Positive means buyers were lifting offers (aggressive
buying); negative means sellers were hitting bids. It is a **signed** number and its sign is the
whole point.

**CVD** — cumulative delta. Delta added up across the session. The running story of who has been
aggressive.

**Absorption** — heavy aggressive buying that **fails to move price up**. Someone large is selling
into it passively and soaking it up. Often marks a top.

**Trapped buyers** — aggressive buyers get filled near a high, price immediately reverses, and now
they're underwater and must sell to get out — which pushes price down further.

### Why a screenshot can never contain delta

A beta trader will ask you this, so learn the answer now.

Delta needs to know, for **every individual trade**, which side was the aggressor. A rendered candle
threw that away when it was drawn. **Two completely different sessions can produce identical candles
and opposite CVD.**

This is not an OCR quality problem and not a better-model problem. The information is **not in the
image at any resolution.** It is information theory, not engineering.

That is why capture only tells us the symbol, the timeframe, and the levels the trader drew — never
a number. It is also the reason [`../contracts.md`](../contracts.md) S6 has no numeric field beyond
`levels` and `confidence`: the type is the guardrail, because this is exactly the mistake that
becomes tempting in Week 8 when a vision model returns something that *looks* like volume.

### Do

Watch two order-flow teardown videos. Open the ATAS demo. Then write `docs/qa/glossary.md`
**in your own words.**

**If you cannot explain absorption without copying a definition, you cannot grade the overlay** —
and grading it is your most important job here. Redo the reading rather than moving on.

---

## Part 2 · The reference session — Week 1, Tuesday

Varad validates our delta against a real footprint chart. **You grade it independently.**

He shows you our CVD and ATAS's CVD side by side. You say whether they agree. Then you write
`docs/qa/reference-session.md`:

- The session date and instrument
- The reference tool used
- **Our CVD and the reference CVD at every 15-minute mark**
- Your sign-off

**Every future "is the delta right" argument gets settled against that file**, rather than against
anyone's memory. It is worth writing carefully once.

### Why you sign it and not him

If the `aggressor_side` mapping is inverted, **every delta sign in the product is wrong and every
chart still looks completely plausible.** Nothing downstream catches it — not a type checker, not a
test, not a code review. The only defence is a second person comparing our number to somebody else's
number. That is you.

### The distinction you are being paid to hold

There is already a strong internal case that the mapping is right — a 48.32/47.79 aggressor split,
83% tick-rule agreement, and a delta↔return correlation of +0.50 that would read −0.50 if the sign
were flipped. All three are real evidence and none of them is what you are checking.

**Internal consistency is the data agreeing with itself. Validation is the data agreeing with
somebody else.** Internal checks structurally cannot catch a wrong contract, a timezone offset, a
session boundary that differs from the reference, or a systematic magnitude error — every one of
those produces numbers that are perfectly self-consistent and wrong.

When someone says "but we already confirmed the mapping three ways", the answer is: *yes, and the
mapping is the least likely problem now. That's why we're checking the other four.*

### A worked example already in the repo

The 2026-07-16 session: **price fell 89 points while CVD closed +1,842.** The 08:00 ET hour was
sharper still — delta **+1,083** against a 47.7-point drop.

That is exactly what a flipped sign looks like, and it was chased hard before being ruled out. It
is genuine **absorption** — buyers repeatedly aggressing into heavy resting supply, price falling
anyway. Learn to recognise that shape, because it is both the product's core signal and its most
convincing false alarm.

---

## Part 3 · The grading protocol — your core loop, Weeks 3–11

Every day of Week 3, and most days after, you sit a full live session with the overlay open and
grade what it flags.

### One row per flag, in `docs/qa/disagreements.md`

| Field | Notes |
| :--- | :--- |
| Timestamp | **Exchange time**, so an engineer can find the ticks |
| Instrument | GC — the only instrument we run |
| What it flagged | `absorption` / `trapped` / `cluster`, and the price |
| Your verdict | **agree · disagree · unsure** |
| Why | One sentence. **This is the field engineers actually use** |
| Severity | Would this have cost a trader money, or was it just noise |

### Use "unsure" freely

A forced binary from someone who genuinely cannot tell is **noise dressed up as data**, and it will
send an engineer chasing a threshold that was fine. "Unsure" is a real answer and it is the honest
one more often than people admit.

### What you're looking for, in order

1. **Flags where the sign is wrong** — it says buying, the chart says selling. That's an
   `aggressor_side` mapping bug and it is **the worst possible bug**, because everything still looks
   plausible.
2. **Flags at levels that mean nothing** — a big print in the middle of nowhere is not a signal.
3. **Outliers it missed** that you would have called. Harder to spot and more valuable than false
   positives, because nothing in the log reminds you they existed.
4. **Flags firing in clusters of five when one event happened.**

### The rule for engineers reading your log

Varad reads it **before** he touches a threshold. If you called five flagged prints wrong, the
question is not *"how do I filter those five"* — it's *"what did those five have in common"*, and
sometimes the honest answer is *"nothing, the rule is wrong."*

---

## Part 4 · The weekly verdict

End of each grading week, one paragraph: **does what it flags match what an order-flow trader would
actually call an outlier?**

**You have the authority to say no, and if you say no the gate is not met.** Not "gets logged for
triage" — the gate is not met, and the correct response is to spend the next week on the same gate.

This authority only works if you use it early. The first time you say no should not be Week 8.
