'use client'

/**
 * The strip under the hero.
 *
 * Deliberately not "10,000 traders" or "99.9% uptime" — there are no customers
 * and no uptime record, and inventing either is the fastest way to lose the ten
 * real people this page is for. These four are facts about the build.
 */

import { AT_A_GLANCE } from '@/content/site'
import { useReveal } from '@/lib/motion'

export function AtAGlance() {
  const ref = useReveal<HTMLElement>({ childSelector: '[data-stat]', stepMs: 70 })

  return (
    <section ref={ref} className="relative px-6 pb-24">
      <div className="mx-auto grid max-w-[1200px] gap-px overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.06] sm:grid-cols-2 lg:grid-cols-4">
        {AT_A_GLANCE.map((stat) => (
          <div key={stat.label} data-stat className="bg-bg px-6 py-8 transition hover:bg-white/[0.02]">
            <div className="num grad-text text-[2.2rem] leading-none font-bold">{stat.value}</div>
            <div className="mt-3 text-[14px] leading-snug text-dim">{stat.label}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
