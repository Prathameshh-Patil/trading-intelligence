'use client'

/**
 * What comes with it beyond the software.
 *
 * All four are commitments from the plan rather than marketing — the onboarding
 * call for every subscriber, the feed set up together, the weekly note written
 * whether the week went well or badly, and support answered by the three people
 * who can change the code. If one stops being true it comes off this page
 * before it comes off the plan.
 */

import { Eyebrow } from '../ui'
import { SERVICES } from '@/content/site'
import { useReveal } from '@/lib/motion'

export function Services() {
  const ref = useReveal<HTMLElement>({ childSelector: '[data-service]', stepMs: 70 })

  return (
    <section id="services" ref={ref} className="relative overflow-hidden px-6 py-24">
      <div className="aura aura-indigo top-10 right-0 h-[26rem] w-[26rem] opacity-60" />

      <div className="mx-auto grid max-w-[1200px] gap-14 lg:grid-cols-[0.85fr_1.15fr]">
        <div>
          <Eyebrow>What you get</Eyebrow>
          <h2 className="mt-5 text-[clamp(2rem,3.8vw,2.7rem)]">
            The software is the smaller half.
          </h2>
          <p className="mt-5 max-w-[38ch] text-[17px] leading-relaxed text-dim">
            Ten subscribers is few enough that every one of them gets a person. That is not a
            growth strategy, it is the whole point — and it is why the list on the right is short
            and specific rather than long and hedged.
          </p>
        </div>

        <ol className="flex flex-col gap-3">
          {SERVICES.map((service, i) => (
            <li key={service.title} data-service className="surface lift flex gap-5 rounded-2xl p-6">
              <span className="num grad grid h-9 w-9 shrink-0 place-items-center rounded-xl text-[13px] font-bold text-white shadow-[0_4px_14px_rgba(139,92,246,0.35)]">
                {i + 1}
              </span>
              <div>
                <h3 className="mb-2 text-[17px] leading-snug font-semibold">{service.title}</h3>
                <p className="text-[15px] leading-relaxed text-dim">{service.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
