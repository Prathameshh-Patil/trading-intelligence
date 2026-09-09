/**
 * Terms, refunds and privacy, on one page.
 *
 * `plans/team/phase-3-month-two.md`: the refund policy is written BEFORE the
 * first sale, not after the first refund request, and kept generous — at ten
 * subscribers, one unhappy person telling ten others costs more than every
 * refund you will ever issue.
 *
 * ⚠️ NOT REVIEWED. A working draft written by an engineer, and the SEBI
 * research-analyst question in `plans/current.md` is still open pending the CA
 * call — that call decides whether this site may describe anything as a signal
 * or a recommendation at all. Do not publish this page or take a payment against
 * it until it has happened.
 */

import Link from 'next/link'

import { Banner, PageHeader } from '@/components/ui'
import { CONTACT, PRICING } from '@/content/site'

export default function PolicyPage() {
  return (
    <main className="mx-auto max-w-[720px] px-6 py-16">
      <PageHeader
        eyebrow="POLICIES"
        title="Terms, refunds and privacy"
        lede="Short, because a policy nobody reads protects nobody."
      />

      <Banner kind="warn">
        <strong>Draft — not legally reviewed.</strong> This page has not yet been checked by a
        professional. It must be reviewed before the first payment is taken.
      </Banner>

      <div className="mt-8 flex flex-col gap-3 text-[16px] text-dim [&_h2]:mt-8 [&_h2]:mb-1 [&_h2]:text-[20px] [&_h2]:font-semibold [&_h2]:text-ink [&_li]:mb-2 [&_ul]:list-disc [&_ul]:pl-5">
        <h2 id="what-this-is">1. What this is, and what it is not</h2>
        <p>
          Trading Intelligence is a <strong className="text-ink">data tool</strong>. It reads the
          raw trade tape and shows you what it contains — signed delta, session-reset CVD,
          absorption, size clusters, and outliers against a measured baseline.
        </p>
        <p>
          It is not investment advice, it is not a recommendation to buy or sell anything, and it
          does not manage money or place orders. Every decision you make with it is yours.
          Position sizing is deliberately not a feature: the software has no field for it and
          never will.
        </p>
        <p>
          Trading futures involves risk of loss, including loss beyond your deposit. Past
          behaviour of any market statistic does not predict its future behaviour.
        </p>

        <h2 id="refunds">2. Refunds</h2>
        <p>
          <strong className="text-ink">Fourteen days, no reason needed, no questions asked.</strong>{' '}
          Write to <a className="text-violet-lift" href={`mailto:${CONTACT.email}`}>{CONTACT.email}</a>{' '}
          or <Link href="/support" className="text-violet-lift">raise a ticket</Link> within fourteen
          days of a payment and we refund it in full, on the rail you paid from.
        </p>
        <ul>
          <li>
            <strong className="text-ink">UPI</strong> — back to the account you paid from, within
            five business days.
          </li>
          <li>
            <strong className="text-ink">USDT</strong> — back to the wallet you paid from, on the
            same chain. You cover the network fee; we cover everything else. Send us the receiving
            address in writing, because we will not infer it.
          </li>
        </ul>
        <p>
          After fourteen days you can stop at any time, and the subscription ends when the period
          you have paid for ends. We do not pro-rate part months, and{' '}
          <strong className="text-ink">nothing auto-renews</strong> — because every payment here is
          one you send by hand, a subscription cannot quietly continue after you stop paying
          attention to it.
        </p>
        <p>
          If the software does not work on your machine and we cannot fix it, that is a refund
          regardless of how long it has been.
        </p>

        <h2 id="founding">3. The founding price</h2>
        <p>
          The first {PRICING.foundingSeats} subscribers keep their price permanently, for as long
          as the subscription runs without a break. If the price goes up later, it does not go up
          for them. If they cancel and come back, it is at whatever the price is then.
        </p>

        <h2 id="payments">4. Payments and keys</h2>
        <p>
          There is no card processor. You pay by UPI or in USDT, upload proof, and a human checks
          it and issues your licence key — usually within a few hours, and always{' '}
          {CONTACT.responseTarget}. Until a key is issued, no payment has been accepted and
          nothing has started.
        </p>
        <p>
          One key is one person. Sharing a key is what gets it revoked; installing it on your own
          laptop and your own desktop is not, and we will never treat it as such.
        </p>

        <h2 id="privacy">5. What we store</h2>
        <p>We hold as little as we can run on:</p>
        <ul>
          <li>Your email address and a hash of your password.</li>
          <li>
            Your payment screenshots and reference numbers, as the record of a payment we
            accepted. Deleted on request once the payment is past any refund window.
          </li>
          <li>Your licence key, and which machines have validated it.</li>
          <li>Support tickets, and whatever you put in them.</li>
        </ul>
        <p>
          <strong className="text-ink">Your journal stays on your machine.</strong> It is
          local-first by design and works with our server switched off. If you turn sync on, we
          store the entries so your own machines can share them — nothing else reads them.
        </p>
        <p>
          <strong className="text-ink">We never receive your market data feed.</strong> The tick
          feed runs on your machine under your own broker entitlement and goes nowhere near us.
          What we do collect about signal quality is counts, timestamps and outcomes — never
          anything from which a feed could be reconstructed.
        </p>
        <p>
          We do not sell anything to anyone. Ask us to delete your account and we delete it, minus
          what we must keep as the record of a payment.
        </p>

        <h2 id="ending">6. Ending it</h2>
        <p>
          You can stop at any time by not sending the next payment. We can end a subscription for
          a shared or resold key, or for a chargeback opened without ever writing to us — and if
          we do, we say why.
        </p>
        <p>
          If we shut the product down, active subscribers get the remainder of what they paid for
          refunded, and a build that keeps working offline for as long as it keeps working.
        </p>

        <p className="mt-6 text-sm text-faint">
          Questions about any of this: <Link href="/contact" className="text-violet-lift">talk to us</Link>.
        </p>
      </div>
    </main>
  )
}
