'use client'

/**
 * Pinned, three steps.
 *
 * This is the section that answers "what do I actually install", which is the
 * real pre-purchase question and the one a stranger will not email to ask. The
 * pin holds the overlay mock still while the steps advance beside it, so the
 * thing being described stays on screen while it is described.
 */

import { useState } from 'react'

import { Eyebrow } from '../ui'
import { HOW_IT_RUNS } from '@/content/site'
import { useScrubber } from '@/lib/motion'

export function HowItRuns() {
  const [active, setActive] = useState(0)

  const ref = useScrubber<HTMLDivElement>({
    // Three steps over the pinned distance; the last one holds to the end rather
    // than flicking past as the pin releases.
    onProgress: (p) => setActive(Math.min(2, Math.floor(p * 3.02))),
    // `top top` because this one pins — see useScrubber's note on `start`.
    start: 'top top',
    end: '+=150%',
    pin: true,
  })

  return (
    <section ref={ref} className="relative mx-auto max-w-[1200px] px-6 py-24">
      <div className="grid items-center gap-14 lg:grid-cols-2">
        <div>
          <Eyebrow>{HOW_IT_RUNS.eyebrow}</Eyebrow>
          <h2 className="mt-4 mb-8 text-[clamp(2rem,3.8vw,2.7rem)] font-semibold">
            {HOW_IT_RUNS.title}
          </h2>

          <ol className="flex flex-col gap-4">
            {HOW_IT_RUNS.steps.map((step, i) => (
              <li
                key={step.title}
                className={`rounded-xl border p-5 transition-colors duration-300 ${
                  i === active ? 'border-violet/45 bg-violet/10' : 'surface'
                }`}
              >
                <div className="flex gap-4">
                  <span
                    className={`num text-sm font-bold ${i === active ? 'text-violet-lift' : 'text-faint'}`}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <h3 className="mb-1 text-[16px] font-semibold">{step.title}</h3>
                    <p className="text-[15px] text-dim">{step.body}</p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>

        {/* The overlay, at its real proportions — 460×820. */}
        <div className="relative mx-auto hidden aspect-[460/820] w-full max-w-[300px] overflow-hidden surface rounded-2xl lg:block">
          <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3">
            <span className="num text-[11px] text-faint">GCZ6</span>
            <span className="num text-[11px] text-bid">live</span>
          </div>
          <div className="p-4">
            <span className="num text-[10px] tracking-widest text-faint">SESSION DELTA</span>
            <div className="num mt-1 text-3xl font-semibold text-bid">+4,218</div>
            <div className="num mt-6 text-[10px] tracking-widest text-faint">LAST 1M</div>
            <div className="num text-xl text-ask">−612</div>
            <div className="mt-6 rounded-lg border border-white/[0.08] p-3">
              <div className="num text-[10px] tracking-widest text-faint">FLAGGED</div>
              <div className="mt-1 text-[13px] text-ink">Absorption at 2418.40</div>
            </div>
          </div>
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-surface to-transparent"
          />
        </div>
      </div>
    </section>
  )
}
