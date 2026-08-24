# AI-assisted code review

You review every PR through Claude, with a fixed rubric.

**This method genuinely catches some classes of problem and genuinely misses others**, and knowing
which is which is what makes you useful here rather than decorative. Both lists are below and the
second one is not a disclaimer — it is instructions.

---

## The workflow

```sh
gh pr list                    # what's open
gh pr diff 12 > /tmp/pr.diff  # the diff
gh pr view 12                 # title, description, files touched
```

Paste the diff into Claude with the prompt below. Anything it flags, **you post as a PR comment in
your own words** and tag the author.

**You are not deciding whether the code is right — you are making sure a human answers each flag.**
An engineer replying *"no, that's fine because X"* is a **successful review**, not a failed one. The
value is that the question got asked at all.

---

## The prompt

```
Review this diff against the project's rules. For each finding give: the file and line,
what's wrong, and why it matters. Rank by severity. If the diff is clean, say so — do not
invent findings.

Rules:
1. CONTRACT DRIFT — these shapes are frozen in plans/team/contracts.md and must not change
   without all three of us agreeing. Flag any change to:
   - the /api/v1/analyze response keys, or confidence's 0-100 scale
   - DeltaBar, Outlier, FeedStatus, CaptureContext (S2, S6)
   - the key-validate response, especially valid:false being a 200 not a 401 (S3)
   - the tick record columns, especially aggressor_side (S1)
2. SECRETS — any real key, token, password or connection string. .env.example must contain
   placeholders only. A real key was staged in .env.example once already on 25 Aug.
3. CAPTURE PURITY — CaptureContext must carry no numeric field except levels and confidence.
   Screenshots can never yield delta, CVD, volume or an outlier. Flag any attempt.
4. NO MARKET DATA ON OUR SERVERS — flag any backend route, log line or telemetry field that
   accepts or stores a tick, a price series, or a screenshot. This is a licensing boundary,
   not a preference.
5. TESTS — does new behaviour have a test? Was an existing test deleted or weakened? Flag any
   assertion that got looser.
6. SCOPE — does the diff do things the PR description doesn't mention?
7. PYTHON 3.12 ONLY — flag anything raising requires-python, or lockfile edits made by hand
   rather than by uv/pnpm.
8. DIST FRESHNESS — if apps/extension/src changed, apps/extension/dist must change in the
   same commit.

Then: list what you could NOT assess from the diff alone.
```

**That last line matters.** It tells you where to ask a human instead of trusting the review.

---

## What this catches

- **Contract drift** — the eight frozen shapes in [`../contracts.md`](../contracts.md)
- **Secrets in a diff**
- **Missing or weakened tests** — including assertions that quietly got looser
- **Scope creep** — the diff doing things the description doesn't mention
- **A stale `dist`** — `apps/extension/src` changed without a rebuild
- **Capture-purity violations** — a numeric field sneaking into `CaptureContext`
- **Market-data-boundary violations** — a route, log line or telemetry field touching a tick

**Those seven are most of what actually goes wrong on a three-person team**, and catching them on
every PR is worth real money. Two of them have already bitten this repo:

- A real API key went into the tracked `.env.example` on 25 Aug **and was staged before it was
  caught.** `git commit -a` would have committed it. Nothing leaked, no rotation was needed — but it
  was caught by chance, and this rubric catches it every time.
- On 24 Aug the extension manifest silently regressed to `content_scripts` + `<all_urls>`, undoing
  a deliberate privacy decision made in `8cd4790`. That is exactly rule 6 — a change nobody asked
  for, in a diff about something else.

---

## What this does not catch — say so, don't pretend

- **Race conditions and memory bugs in the Rust engine**
- **Whether a threshold is correct** — only live grading tells you that
- **Whether the delta arithmetic is right** — only the reference session tells you that
- **Performance regressions**
- **Whether an architectural choice was wise**

**When the diff touches `services/engine/` and the review comes back clean, say:**

> *"Clean on the rubric. Not assessed for concurrency."*

**Not "looks good".** The second is a claim you cannot back, and the cost of making it once is that
everyone learns to discount everything you say — including the findings that were real. Your
credibility here is the whole asset; spend it carefully.

---

## Escalation

| What you found | What to do |
| :--- | :--- |
| A secret in a diff | **Stop. Tell both engineers immediately, not in a PR comment.** A PR comment is public in the repo history |
| Contract drift | Comment, tag both engineers. **It needs all three of us in standup**, not one engineer's approval |
| Market data on a server route | Comment, and flag it as a **licensing** issue, not a code issue. It is not a preference to be traded off |
| Missing tests | Comment, tag the author |
| Scope creep | Comment, ask what it's for. Sometimes there's a good reason and it just wasn't written down |
| Something you don't understand | **Ask.** Not understanding a diff is not a failure of the review — it is a finding about the code's readability, and worth saying out loud |
