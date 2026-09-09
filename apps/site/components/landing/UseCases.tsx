'use client'

/**
 * Four situations, not four promises.
 *
 * Each card ends at what the tool *shows* — the `shows` line is the read-out it
 * puts on screen, and the card stops there. "You will know whether size showed
 * up" is a fact about the data; "you will catch the move" would be a claim, and
 * is not on this page anywhere.
 */

import { Eyebrow } from '../ui'
import { USE_CASES } from '@/content/site'
import { useReveal } from '@/lib/motion'

export function UseCases() {
  const ref = useReveal<HTMLElement>({ childSelector: '[data-case]', stepMs: 80 })

  return (
    <section id="use-cases" ref={ref} className="relative overflow-hidden px-6 py-24">
      <div className="aura aura-violet top-1/4 -left-40 h-[30rem] w-[30rem] opacity-60" />

      <div className="mx-auto max-w-[1200px]">
        <Eyebrow>Use cases</Eyebrow>
        <h2 className="mt-5 max-w-[24ch] text-[clamp(2rem,4.2vw,3rem)]">
          Four places a bar is <span className="grad-text">hiding something</span> from you.
        </h2>

        <div className="mt-14 grid gap-4 lg:grid-cols-2">
          {USE_CASES.map((useCase) => (
            <article key={useCase.title} data-case className="surface lift group rounded-2xl p-7">
              <span className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-bold tracking-[0.12em] text-faint uppercase">
                {useCase.tag}
              </span>

              <h3 className="mt-4 mb-3 text-[20px] leading-snug font-semibold">{useCase.title}</h3>
              <p className="text-[15px] leading-relaxed text-dim">{useCase.body}</p>

              <div className="mt-6 flex items-center gap-2.5 border-t border-white/[0.06] pt-4">
                <span className="grad h-1.5 w-1.5 shrink-0 rounded-full" />
                <span className="num text-[12px] text-violet-lift">{useCase.shows}</span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
