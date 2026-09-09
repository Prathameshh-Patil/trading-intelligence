'use client'

/**
 * Six capabilities, staggered on entry.
 *
 * Each card carries a small drawn mark rather than a number — a delta ledger, a
 * CVD curve, an absorption bar. On a page arguing that the picture matters more
 * than the summary, six cards labelled 01–06 were making the opposite case.
 */

import type { ReactNode } from 'react'

import { Eyebrow } from '../ui'
import { SHOWS } from '@/content/site'
import { useReveal } from '@/lib/motion'

const S = { fill: 'none', strokeWidth: 1.6, strokeLinecap: 'round' as const }

/** One mark per capability, drawn rather than iconified — each is the thing it names. */
const MARKS: ReactNode[] = [
  // signed delta — paired bars either side of a centre line
  <>
    <line x1="12" y1="3" x2="12" y2="21" stroke="#6b7285" {...S} />
    <rect x="13" y="5" width="7" height="3.2" rx="1.2" fill="#34d399" />
    <rect x="5" y="10" width="7" height="3.2" rx="1.2" fill="#f87171" />
    <rect x="13" y="15" width="5" height="3.2" rx="1.2" fill="#34d399" />
  </>,
  // session-reset CVD — a curve that starts at a baseline
  <>
    <line x1="3" y1="19" x2="21" y2="19" stroke="#6b7285" {...S} />
    <path d="M3 19c4 0 5-7 9-8s5 2 9-3" stroke="#34d399" {...S} />
  </>,
  // absorption — size stacking under a flat line
  <>
    <line x1="3" y1="10" x2="21" y2="10" stroke="#a78bfa" {...S} />
    <rect x="5" y="12" width="2.6" height="7" rx="1" fill="#f87171" />
    <rect x="9" y="12" width="2.6" height="5" rx="1" fill="#f87171" />
    <rect x="13" y="12" width="2.6" height="8" rx="1" fill="#f87171" />
    <rect x="17" y="12" width="2.6" height="4" rx="1" fill="#f87171" />
  </>,
  // size clusters — dots grouped at one level
  <>
    <circle cx="7" cy="8" r="1.5" fill="#6b7285" />
    <circle cx="11" cy="14" r="2.6" fill="#8b5cf6" />
    <circle cx="15" cy="14" r="2.2" fill="#8b5cf6" />
    <circle cx="18" cy="7" r="1.4" fill="#6b7285" />
  </>,
  // outliers vs baseline — one bar breaking a threshold
  <>
    <line x1="3" y1="9" x2="21" y2="9" stroke="#6b7285" strokeDasharray="2 3" {...S} />
    <rect x="5" y="13" width="3" height="6" rx="1.2" fill="#6b7285" />
    <rect x="10.5" y="4" width="3" height="15" rx="1.2" fill="#fbbf24" />
    <rect x="16" y="14" width="3" height="5" rx="1.2" fill="#6b7285" />
  </>,
  // rules — a checklist
  <>
    <path d="M4 7.5l2 2 3.5-4" stroke="#34d399" {...S} />
    <line x1="12" y1="7" x2="20" y2="7" stroke="#6b7285" {...S} />
    <path d="M4 16.5l2 2 3.5-4" stroke="#34d399" {...S} />
    <line x1="12" y1="16" x2="20" y2="16" stroke="#6b7285" {...S} />
  </>,
]

export function WhatItShows() {
  const ref = useReveal<HTMLElement>({ childSelector: '[data-card]', stepMs: 55 })

  return (
    <section id="features" ref={ref} className="relative overflow-hidden px-6 py-24">
      <div className="aura aura-indigo top-0 -right-40 h-[28rem] w-[28rem] opacity-70" />

      <div className="mx-auto max-w-[1200px]">
        <Eyebrow>What it shows</Eyebrow>
        <h2 className="mt-5 max-w-[20ch] text-[clamp(2rem,4.2vw,3rem)]">
          Everything here is in the tape.{' '}
          <span className="grad-text">None of it survives being drawn.</span>
        </h2>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SHOWS.map((item, i) => (
            <article key={item.title} data-card className="surface lift rounded-2xl p-6">
              <div className="surface-hi mb-5 grid h-11 w-11 place-items-center rounded-xl">
                <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden>
                  {MARKS[i]}
                </svg>
              </div>
              <h3 className="mb-2.5 text-[17px] font-semibold">{item.title}</h3>
              <p className="text-[15px] leading-relaxed text-dim">{item.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
