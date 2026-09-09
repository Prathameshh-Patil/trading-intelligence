'use client'

/**
 * Chart versus tape, row by row.
 *
 * Not a competitor comparison — there is no rival product in this table, and
 * there deliberately never will be. Every row is a fact about what the two data
 * structures can physically carry, which is an argument nobody can dispute and
 * which does not depend on our software being any good.
 */

import { Eyebrow } from '../ui'
import { COMPARE } from '@/content/site'
import { useReveal } from '@/lib/motion'

function Yes() {
  return (
    <span className="inline-grid h-6 w-6 place-items-center rounded-full bg-bid/12 text-bid">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M4 12.5l5 5L20 6.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    </span>
  )
}

function No() {
  return (
    <span className="inline-grid h-6 w-6 place-items-center rounded-full bg-white/[0.04] text-faint">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      </svg>
    </span>
  )
}

export function Compare() {
  const ref = useReveal<HTMLElement>({ childSelector: '[data-row]', stepMs: 45 })

  return (
    <section ref={ref} className="relative px-6 py-24">
      <div className="mx-auto max-w-[1000px]">
        <Eyebrow>The difference, exactly</Eyebrow>
        <h2 className="mt-5 max-w-[22ch] text-[clamp(2rem,4.2vw,3rem)]">
          What survives being drawn, and{' '}
          <span className="grad-text">what does not</span>.
        </h2>

        <div className="surface mt-12 overflow-hidden rounded-2xl">
          <div className="grid grid-cols-[1fr_84px_84px] items-center gap-3 border-b border-white/[0.08] px-6 py-4 sm:grid-cols-[1fr_120px_120px]">
            <span className="text-[11px] font-bold tracking-[0.12em] text-faint uppercase">
              Information
            </span>
            <span className="text-center text-[11px] font-bold tracking-[0.1em] text-faint uppercase">
              Your chart
            </span>
            <span className="text-center text-[11px] font-bold tracking-[0.1em] text-violet-lift uppercase">
              The tape
            </span>
          </div>

          {COMPARE.rows.map((row) => (
            <div
              key={row.field}
              data-row
              className="grid grid-cols-[1fr_84px_84px] items-center gap-3 border-b border-white/[0.05] px-6 py-4 transition last:border-b-0 hover:bg-white/[0.02] sm:grid-cols-[1fr_120px_120px]"
            >
              <span className="text-[15px] text-ink">{row.field}</span>
              <span className="flex justify-center">{row.chart ? <Yes /> : <No />}</span>
              <span className="flex justify-center">{row.tape ? <Yes /> : <No />}</span>
            </div>
          ))}
        </div>

        <p className="mt-5 text-[14px] text-faint">
          Nothing in the right column is exotic. It was all in the trade data before the bar was
          drawn over it.
        </p>
      </div>
    </section>
  )
}
