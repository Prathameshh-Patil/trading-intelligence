'use client'

/**
 * Pricing.
 *
 * One currency at a time, toggled — never side by side. A visitor who can see
 * both will do the division and ask why it does not match a bank rate, and that
 * is a support email about foreign exchange instead of a sale.
 *
 * The founding-price promise is a full section in body weight, not fine print:
 * `plans/team/phase-3-month-two.md` requires it said plainly on the page, in the
 * checkout and in the confirmation email, because plainness is what buys honest
 * feedback rather than polite feedback.
 */

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { Button, Eyebrow, PageHeader } from '@/components/ui'
import {
  FOUNDING,
  HOW_PAYING_WORKS,
  PRICING,
  formatPrice,
  type Currency,
  type PlanId,
} from '@/content/site'
import { useSession } from '@/lib/session'

export default function PricingPage() {
  const [currency, setCurrency] = useState<Currency>('usd')
  const { me } = useSession()
  const router = useRouter()

  function choose(plan: PlanId) {
    router.push(me ? `/checkout?plan=${plan}&currency=${currency}` : '/signup')
  }

  return (
    <main className="mx-auto max-w-[1000px] px-6 py-16">
      <PageHeader
        eyebrow="PRICING"
        title="One price, one add-on, no tiers"
        lede="There is no enterprise plan and there is no free tier with the useful half removed."
      />

      <div
        role="group"
        aria-label="Currency"
        className="mb-8 inline-flex gap-1 surface rounded-xl p-1"
      >
        {(
          [
            { id: 'usd', label: 'USD · pay in USDT' },
            { id: 'inr', label: 'INR · pay by UPI' },
          ] as const
        ).map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setCurrency(option.id)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              currency === option.id ? 'grad text-white' : 'text-dim'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {PRICING.plans.map((plan, i) => (
          <div
            key={plan.id}
            className={`flex flex-col gap-3 rounded-2xl border p-7 ${
              i === 0 ? 'border-violet/45 surface' : 'surface'
            }`}
          >
            {i === 0 ? <Eyebrow>Most people start here</Eyebrow> : null}
            <h2 className="text-xl font-semibold">{plan.name}</h2>

            <div className="flex items-baseline gap-2">
              <span className="num text-[2.6rem] leading-none font-semibold">
                {formatPrice(currency === 'usd' ? plan.usd : plan.inr, currency)}
              </span>
              <span className="text-faint">/month</span>
            </div>

            <p className="text-dim">{plan.blurb}</p>

            {'addOnUsd' in plan ? (
              <p className="text-sm text-faint">
                That is Core plus{' '}
                <span className="num">
                  {formatPrice(currency === 'usd' ? plan.addOnUsd : plan.addOnInr, currency)}
                </span>{' '}
                for the journal. You can add it later without repaying anything.
              </p>
            ) : null}

            <ul className="mt-2 mb-auto flex flex-col gap-2.5 text-[15px] text-dim">
              {plan.includes.map((line) => (
                <li key={line} className="flex gap-2.5">
                  <span className="text-bid">✓</span>
                  {line}
                </li>
              ))}
            </ul>

            <Button onClick={() => choose(plan.id)}>
              {me ? 'Continue to payment' : 'Create an account'} →
            </Button>
          </div>
        ))}
      </div>

      <section className="mt-12 surface rounded-2xl p-7">
        <h2 className="mb-3 text-[19px] font-semibold">{FOUNDING.title}</h2>
        <p className="text-dim">{FOUNDING.body}</p>
      </section>

      <section className="mt-5 surface rounded-2xl p-7">
        <h2 className="mb-3 text-[19px] font-semibold">How paying works</h2>
        <p className="text-dim">{HOW_PAYING_WORKS}</p>
        <p className="mt-3 text-sm text-faint">
          Fourteen-day refund, no reason needed —{' '}
          <Link href="/policy#refunds" className="text-violet-lift">
            the whole policy
          </Link>{' '}
          is three paragraphs.
        </p>
      </section>
    </main>
  )
}
