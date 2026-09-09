'use client'

/**
 * The last thing on the page, and it asks for a conversation rather than a card.
 *
 * "We would rather talk you out of it now than refund you in a fortnight" is
 * meant literally — at ten subscribers a bad fit costs more in support and
 * reputation than the $39 is worth.
 */

import { ButtonLink } from '../ui'
import { FINAL_CTA } from '@/content/site'
import { useReveal } from '@/lib/motion'

export function FinalCta() {
  const ref = useReveal<HTMLElement>()

  return (
    <section ref={ref} className="relative px-6 py-24">
      <div className="relative mx-auto max-w-[1000px] overflow-hidden rounded-3xl border border-violet/25 px-8 py-16 text-center sm:px-16">
        <div className="aura aura-violet drift -top-32 left-1/2 h-[26rem] w-[34rem] -translate-x-1/2" />

        <h2 className="mx-auto max-w-[20ch] text-[clamp(2rem,4.4vw,3rem)]">{FINAL_CTA.title}</h2>
        <p className="mx-auto mt-6 max-w-[52ch] text-[17px] leading-relaxed text-dim">
          {FINAL_CTA.body}
        </p>

        <div className="mt-10 flex flex-wrap justify-center gap-3.5">
          <ButtonLink href="/contact">Book the call →</ButtonLink>
          <ButtonLink href="/pricing" kind="secondary">See pricing</ButtonLink>
        </div>
      </div>
    </section>
  )
}
