/**
 * Every price, address, contact detail and piece of marketing copy on the site.
 *
 * No component hardcodes a number or a sentence a human might want to change.
 * Change it here and it changes on the page, in the checkout and in the policy
 * at once — which matters most for the founding-price promise, because
 * `plans/team/phase-3-month-two.md` requires it stated identically in all three
 * places and three copies of a sentence drift.
 *
 * Values marked PLACEHOLDER are the ones only Prathamesh can supply. They are
 * deliberately not plausible, so a stub is never mistaken for a real UPI ID or
 * wallet address.
 */

export const BRAND = {
  name: 'Trading Intelligence',
  product: 'a desktop order-flow overlay for gold futures',
} as const

/** PLACEHOLDER — all four. */
export const CONTACT = {
  email: 'PLACEHOLDER_SUPPORT_EMAIL@example.com',
  phone: '+91 PLACEHOLDER_PHONE',
  hours: 'Mon–Fri, 09:00–18:00 IST',
  responseTarget: 'within one business day',
} as const

/**
 * The people. Ten subscribers buy from people, not from a brand — so this is on
 * the page, and it is real names or it is nothing.
 *
 * PLACEHOLDER — names and roles.
 */
export const TEAM = [
  { name: 'PLACEHOLDER_NAME_1', role: 'Desktop app, capture, packaging' },
  { name: 'PLACEHOLDER_NAME_2', role: 'Signal engine and backend' },
  { name: 'PLACEHOLDER_NAME_3', role: 'Product, QA, and every onboarding call' },
] as const

/**
 * Payment rails. There is no processor: a buyer pays here, uploads proof, and a
 * human approves it.
 *
 * The chain matters more than the address — USDT sent on the wrong network is
 * unrecoverable by anyone — which is why `network` is a separate field and the
 * checkout page is built so the address cannot render without it.
 *
 * PLACEHOLDER — the UPI id, the account name, the wallet address, the chain.
 */
export const PAYMENT = {
  upi: {
    id: 'PLACEHOLDER_UPI_ID@bank',
    accountName: 'PLACEHOLDER_ACCOUNT_NAME',
  },
  usdt: {
    chain: 'PLACEHOLDER_CHAIN',
    network: 'PLACEHOLDER_NETWORK (e.g. Tron TRC20)',
    address: 'PLACEHOLDER_USDT_WALLET_ADDRESS',
  },
} as const

/**
 * Prices.
 *
 * USD is from `plans/team/phase-3-month-two.md` W6D1 and is agreed: $39/mo core,
 * $4.99/mo journal add-on, founding price permanent for the first ten.
 *
 * ⚠️ PLACEHOLDER — the INR figures are unconfirmed. They are round equivalents
 * at roughly 90/USD, picked so the page never shows a converted-looking number
 * like ₹3,451. Nobody has agreed them.
 */
export const PRICING = {
  foundingSeats: 10,
  plans: [
    {
      id: 'core' as const,
      name: 'Core',
      usd: 39,
      inr: 3499,
      blurb: 'The overlay, the live feed, the rules engine.',
      includes: [
        'Floating overlay over any chart platform',
        'Signed delta and session-reset CVD',
        'Absorption, trapped participants, size clusters',
        'Outliers flagged against measured base rates',
        'Rules engine and session review',
      ],
    },
    {
      id: 'core_journal' as const,
      name: 'Core + Journal',
      usd: 43.99,
      inr: 3948,
      addOnUsd: 4.99,
      addOnInr: 449,
      blurb: 'Everything in Core, plus the trade journal.',
      includes: [
        'Everything in Core',
        'Trade journal, local-first — it works with our server switched off',
        'Journal sync across your own machines',
        'Session review against your own logged trades',
      ],
    },
  ],
} as const

export type PlanId = (typeof PRICING.plans)[number]['id']
export type Currency = 'usd' | 'inr'

/** The rail decides the currency, not the buyer. UPI is rupees; USDT is dollars. */
export const CURRENCY_OF_METHOD = { upi: 'inr', usdt: 'usd' } as const

export function planById(id: PlanId) {
  const plan = PRICING.plans.find((p) => p.id === id)
  if (!plan) throw new Error(`unknown plan: ${id}`)
  return plan
}

export function priceOf(id: PlanId, currency: Currency): number {
  const plan = planById(id)
  return currency === 'usd' ? plan.usd : plan.inr
}

export function formatPrice(amount: number, currency: Currency): string {
  return currency === 'usd'
    ? `$${amount.toFixed(2).replace(/\.00$/, '')}`
    : `₹${amount.toLocaleString('en-IN')}`
}

/* ── copy ────────────────────────────────────────────────────────────────── */

export const HERO = {
  eyebrow: 'Gold futures · GC · desktop overlay',
  title: ['Two identical sessions.', 'Opposite order flow.'],
  body: 'A candle keeps the open, high, low and close. It does not keep the aggressor side of a single trade — the chart threw that away when it drew the bar. Trading Intelligence reads the raw tape on your own machine and shows what the chart underneath structurally cannot.',
  facts: ['Runs on your machine', 'Your own feed entitlement', 'Sits over any chart platform'],
} as const

export const LOSSY = {
  eyebrow: 'WHAT A BAR COSTS',
  title: 'A candle is lossy compression.',
  // Worded to be true whether the reader watched it animate or is looking at
  // the reduced-motion still. "Everything you just watched" was neither.
  caption:
    'Every one of those trades carried a side. The bar kept four numbers and dropped the rest.',
} as const

export const TWO_CANDLES = {
  eyebrow: 'THE PART THAT CANNOT BE ARGUED WITH',
  title: 'Same four numbers. Opposite tape.',
  caption:
    'Same open. Same high. Same low. Same close. Opposite cumulative delta. Your chart draws these two sessions the same way.',
} as const

export const SHOWS = [
  {
    title: 'Signed delta',
    body: 'Every trade, split by who crossed the spread to get filled. The number a candle cannot carry, because drawing it threw the aggressor away.',
  },
  {
    title: 'Session-reset CVD',
    body: 'Cumulative delta that starts each session at zero, so what you are reading is today rather than an accumulated artefact of last week.',
  },
  {
    title: 'Absorption',
    body: 'Size hitting a level while price refuses to move. Visible in the tape, invisible in the bar drawn over it.',
  },
  {
    title: 'Size clusters',
    body: 'Where unusually large trades landed, and at what price. Clustered participation looks nothing like the same volume spread thin.',
  },
  {
    title: 'Outliers against a baseline',
    body: 'Flagged against base rates measured from a 19-month archive of the real tape — not against a number somebody picked.',
  },
  {
    title: 'Your rules, in front of you',
    body: 'The rules you wrote when the market was quiet, on screen when it is not. Plus a journal and a session review, so the tool earns its place between trades.',
  },
] as const

export const ABSORPTION = {
  eyebrow: 'ONE EXAMPLE, IN FULL',
  title: 'The tape said something. The bar did not.',
  caption:
    '1,940 contracts sold into this level over ninety seconds. Price moved three tenths of a point. Here is the candle your chart drew.',
} as const

export const HOW_IT_RUNS = {
  eyebrow: 'HOW IT RUNS',
  title: 'On your machine, over your chart, on your own feed.',
  steps: [
    {
      title: 'Install and connect your feed',
      body: 'Your own account, your own entitlement. Ten minutes, and we do it with you on a call.',
    },
    {
      title: 'Put it beside your chart',
      body: 'A 460×820 window that stays on top. Your platform does not know it exists.',
    },
    {
      title: 'Read what the bar dropped',
      body: 'Delta, CVD, absorption and outliers, live, against measured base rates.',
    },
  ],
} as const

/**
 * The section that does not move.
 *
 * After five scroll-driven sections, stillness is the argument: it reads as
 * someone dropping the sales voice. Do not add a reveal to this.
 */
export const NOT_CLAIMING = {
  eyebrow: 'WHAT WE ARE NOT CLAIMING',
  title: 'This is a data tool, not a signal service.',
  blocks: [
    {
      title: 'No returns, no win rate, no track record',
      body: 'We do not publish a P&L curve and we are not going to. What we sell is visibility into data your chart discards. What you do with it is your decision and your risk.',
    },
    {
      title: 'No position sizing, ever',
      body: 'The software has no field for how much you should trade. That is a design decision, not a missing feature.',
    },
    {
      title: 'Ten subscribers, on purpose',
      body: 'We are looking for ten people, not ten thousand. Every one gets an onboarding call with a human who built it.',
    },
  ],
} as const

export const FOUNDING = {
  title: `The founding price is permanent for the first ${PRICING.foundingSeats}.`,
  body: `The first ${PRICING.foundingSeats} subscribers keep this price for as long as their subscription runs without a break. If we raise prices later, it does not go up for them. We are saying this on the page, in the checkout and in the email that carries your key — because we would rather have your honest opinion than your polite one.`,
} as const

export const HOW_PAYING_WORKS =
  'There is no card processor. You pay by UPI or in USDT, upload the receipt, and one of us checks it and issues your licence key — usually within a few hours. Nothing auto-renews, because there is nothing holding a card to renew against. When you want another month, you send another payment.'

export const HOLDING = {
  badge: 'Not released yet',
  title: ['The chart threw away', 'who initiated each trade.'],
  // Short on purpose — this is a holding page, not the pitch. Two lines: the
  // hook, then the honest caveat. The longer version of this argument lives on
  // the real landing page once you sign in.
  body: [
    'Same candle. Opposite order flow. Your chart can’t tell you which.',
    'We’re building the overlay that can — reading the real tape, on your own machine, for gold futures. Not finished. Not for sale. Yet.',
  ],
} as const

export const TICKET_CATEGORIES = [
  'Payment or key not received',
  'Install or update problem',
  'Feed or data question',
  'Billing, refund or cancellation',
  'Something else',
] as const

export const RISK_LINE = 'Futures trading involves risk of loss, including loss beyond your deposit.'

/* ── sections added for the fuller client-facing page ─────────────────────
   Every line below is checkable against the product or the plan. Nothing here
   is an outcome, a return, or a claim about what a trader will make — that
   restriction is the whole point of NOT_CLAIMING and it applies to the
   marketing sections just as hard. */

/**
 * The strip under the hero.
 *
 * Facts about the build, not about results. "19-month archive" is the Databento
 * GC archive on disk; "460×820" is the window geometry in `tauri.conf.json`;
 * "one instrument" is real — NQ was dropped on 25 Aug and a second instrument
 * is explicitly not on the table this quarter.
 */
export const AT_A_GLANCE = [
  { value: 'GC', label: 'One instrument, done properly' },
  { value: '19 mo', label: 'Of real tape behind the baselines' },
  { value: '460×820', label: 'A window, not another platform' },
  { value: '0', label: 'Bytes of your feed reaching us' },
] as const

/**
 * Use cases.
 *
 * Written as situations a gold trader will recognise, and each one ends at what
 * the tool *shows* rather than at what happens next. "You will know whether size
 * showed up" is a fact about the data; "you will catch the move" would be a
 * claim, and is not here.
 */
export const USE_CASES = [
  {
    tag: 'At a level',
    title: 'You keep getting stopped at the same price',
    body: 'A level that rejects you three times looks identical on the chart each time. The tape does not: absorption, a size cluster and a thin retest are three different events, and only one of them had participants behind it.',
    shows: 'Absorption · size clusters · delta at the level',
  },
  {
    tag: 'On a break',
    title: 'A breakout, and you cannot tell if anyone came',
    body: 'Price leaves the range on a bar that looks the same whether one participant lifted a thin book or a hundred crossed the spread. Signed delta separates those two, because it never threw the aggressor away.',
    shows: 'Signed delta · session CVD · outlier flagging',
  },
  {
    tag: 'Into the open',
    title: 'The 90 minutes around the New York open',
    body: 'The most-traded window of the gold session is also where a single bar hides the most. Session-reset CVD starts at zero each day, so what you are reading is today rather than an artefact carried over from last week.',
    shows: 'Session-reset CVD · phase · ATR in basis points',
  },
  {
    tag: 'After the close',
    title: 'You journal, but you never actually review',
    body: 'A journal nobody reads is a diary. The session review puts your logged entries next to what the tape was doing at the time, which is the only version of reviewing that changes anything.',
    shows: 'Journal · session review · your own rules',
  },
] as const

/**
 * What comes with it beyond the software.
 *
 * All four are commitments from `plans/team/phase-4-month-three.md` — the
 * onboarding call for every subscriber, the weekly shipped improvement, the
 * weekly accuracy note, and support answered by the three people who built it.
 * If any of those stops being true, it comes off this page first.
 */
export const SERVICES = [
  {
    title: 'An onboarding call. Every subscriber, no exceptions.',
    body: 'We install it with you, connect your feed with you, and stay on the call until you have seen it flag something live. This does not scale and it is not supposed to.',
  },
  {
    title: 'Your feed, set up with you',
    body: 'The tick feed runs on your own machine under your own entitlement. That is the part people get stuck on, so we do it together rather than sending you a page of instructions.',
  },
  {
    title: 'A weekly note on what the signal actually did',
    body: 'Written whether the week was good or bad. A tool that only reports its wins is not reporting.',
    },
  {
    title: 'Support from the three people who built it',
    body: 'No tier one. No ticket deflection. The person who answers you can change the code.',
  },
] as const

/**
 * Chart versus tape.
 *
 * The most direct statement of the wedge, and every row is a fact about how the
 * two data structures differ — not a comparison against a competitor's product.
 */
export const COMPARE = {
  rows: [
    { field: 'Open, high, low, close', chart: true, tape: true },
    { field: 'Total volume in the bar', chart: true, tape: true },
    { field: 'Which side crossed the spread', chart: false, tape: true },
    { field: 'Signed delta, and its running total', chart: false, tape: true },
    { field: 'Size absorbed at a level while price held', chart: false, tape: true },
    { field: 'Where the large trades actually landed', chart: false, tape: true },
    { field: 'Order of events inside the bar', chart: false, tape: true },
  ],
} as const

/**
 * FAQ.
 *
 * The six questions a sceptical trader asks before paying, answered the way we
 * would answer them on a call. The answers on returns and on advice are the
 * same ones in NOT_CLAIMING and in the policy — three places, one position.
 */
export const FAQ = [
  {
    q: 'Do I need my own market data?',
    a: 'Yes. The tick feed runs on your machine under your own broker or vendor entitlement, which is why your data never reaches us and why this costs what it costs rather than what redistributing a futures feed would cost. We set it up with you on the onboarding call.',
  },
  {
    q: 'Does it work with my charting platform?',
    a: 'It sits on top of whatever you already use — MT5, TradingView, anything. It is a separate always-on-top window; it does not plug into your platform, and your platform does not know it is there.',
  },
  {
    q: 'Is this a signal service? Will it tell me when to buy?',
    a: 'No. It shows you what is in the tape — delta, CVD, absorption, size clusters, outliers against measured baselines. It never tells you what to do, it has no field for position size, and it is not investment advice.',
  },
  {
    q: 'Where is the track record?',
    a: 'There is not one, and we are not going to invent one. We do not publish a P&L curve, a win rate or a backtest. What we sell is visibility into data your chart discards; what you do with it is your decision and your risk.',
  },
  {
    q: 'How does paying work, and can I stop?',
    a: 'You pay by UPI or in USDT, upload the receipt, and one of us checks it by hand and issues your key. Nothing auto-renews, because there is no card on file to renew against — when you want another month you send another payment. Fourteen-day refund, no reason needed.',
  },
  {
    q: 'Why only gold?',
    a: 'Because one instrument understood properly beats four guessed at. The baselines behind the outlier flagging are measured from 19 months of real GC tape; a second instrument means a new feed adapter, re-derived thresholds and a second reference session, and we would rather do that once it is earned.',
  },
] as const

export const FINAL_CTA = {
  title: 'Ten people. Every one of them talks to us first.',
  body: 'If you read this far you are probably one of the ten. Book the call before you pay anything — we would rather talk you out of it now than refund you in a fortnight.',
} as const
