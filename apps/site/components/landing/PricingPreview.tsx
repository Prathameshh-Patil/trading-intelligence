'use client'

/**
 * The price, stated once, plainly.
 *
 * It fades in on entry and does nothing else. **It never counts up.** A number
 * that animates reads as a number being sold to you, which is the opposite of
 * what the founding-price paragraph beneath it is trying to establish.
 */

import { ButtonLink, Eyebrow } from '../ui'
import { FOUNDING, PRICING, formatPrice } from '@/content/site'
import { useReveal } from '@/lib/motion'

export function PricingPreview() {
  const ref = useReveal<HTMLElement>()
  const core = PRICING.plans[0]

  return (
    <section ref={ref} className="relative mx-auto max-w-[1200px] px-6 py-24">
      <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <Eyebrow>FOUNDING PRICE</Eyebrow>
          <div className="mt-5 flex items-baseline gap-2">
            <span className="num text-[clamp(3rem,7vw,4.5rem)] leading-none font-semibold text-ink">
              {formatPrice(core.usd, 'usd')}
            </span>
            <span className="text-faint">/month</span>
          </div>
          <p className="mt-4 max-w-[36ch] text-dim">{core.blurb}</p>
          <div className="mt-8">
            <ButtonLink href="/pricing">See what is included →</ButtonLink>
          </div>
        </div>

        <div className="surface rounded-2xl p-8">
          <h3 className="mb-4 text-[20px] font-semibold">{FOUNDING.title}</h3>
          <p className="text-[16px] leading-relaxed text-dim">{FOUNDING.body}</p>
        </div>
      </div>
    </section>
  )
}
