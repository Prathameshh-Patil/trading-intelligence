'use client'

/**
 * The hero. Ambient only — nothing here depends on scroll.
 *
 * The page has to say something before it is scrolled, so it leads with the
 * product itself: the real 380px panel floating in violet light, with a live
 * tape ticking beside it. Both loop forever and neither is scroll-linked.
 *
 * The tape is `aria-hidden` — a screen reader being read a hundred invented
 * trades is nobody's idea of an accessible page.
 */

import { useMemo } from 'react'

import { AppPanel } from './AppPanel'
import { ButtonLink, Eyebrow } from '../ui'
import { HERO } from '@/content/site'
import { mulberry32 } from '@/lib/rng'

type Print = { price: string; size: number; side: 'bid' | 'ask' }

function useTape(count: number): Print[] {
  return useMemo(() => {
    const rand = mulberry32(20260909)
    let price = 2418.4
    return Array.from({ length: count }, () => {
      price += (rand() - 0.5) * 0.4
      return {
        price: price.toFixed(1),
        // Lognormal-ish: mostly small, occasionally not. Uniform random would
        // look like noise rather than like a tape.
        size: Math.max(1, Math.round(Math.exp(rand() * 3.6))),
        side: rand() > 0.5 ? 'bid' : 'ask',
      } satisfies Print
    })
  }, [count])
}

export function Hero() {
  const prints = useTape(30)

  return (
    <section className="relative overflow-hidden px-6 pt-20 pb-28">
      <div className="grid-bg" />
      <div className="aura aura-violet drift -top-40 -left-40 h-[36rem] w-[36rem]" />
      <div className="aura aura-indigo top-20 right-0 h-[30rem] w-[30rem]" />

      <div className="mx-auto grid max-w-[1200px] items-center gap-16 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <Eyebrow>{HERO.eyebrow}</Eyebrow>

          <h1 className="mt-6 mb-7 text-[clamp(2.8rem,6vw,4.8rem)]">
            {HERO.title[0]}
            <br />
            <span className="grad-text">{HERO.title[1]}</span>
          </h1>

          <p className="max-w-[54ch] text-[19px] leading-[1.65] text-dim">{HERO.body}</p>

          <div className="mt-10 flex flex-wrap gap-3.5">
            <ButtonLink href="/pricing">See pricing →</ButtonLink>
            <ButtonLink href="/contact" kind="secondary">Talk to us first</ButtonLink>
          </div>

          <ul className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-[13px] text-faint">
            {HERO.facts.map((fact) => (
              <li key={fact} className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-violet" />
                {fact}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex items-start justify-center gap-4">
          <AppPanel />

          {/* The tape, tucked behind the panel on wide screens. */}
          <div
            aria-hidden
            className="surface hidden w-[190px] shrink-0 self-stretch overflow-hidden rounded-2xl xl:block"
          >
            <div className="flex items-center justify-between border-b border-white/[0.08] px-3 py-2.5">
              <span className="num text-[11px] text-faint">TIME &amp; SALES</span>
              <span className="h-1.5 w-1.5 rounded-full bg-bid" />
            </div>
            <div className="tape-mask h-[420px] overflow-hidden">
              <div className="tape-scroll">
                {[0, 1].map((copy) => (
                  <div key={copy}>
                    {prints.map((print, i) => (
                      <div
                        key={`${copy}-${i}`}
                        className="num flex items-center justify-between border-b border-white/[0.04] px-3 py-1.5 text-[12px]"
                      >
                        <span className="text-dim">{print.price}</span>
                        <span className={print.side === 'bid' ? 'text-bid' : 'text-ask'}>
                          {print.side === 'bid' ? 'B' : 'A'}
                        </span>
                        <span className="text-ink">{print.size}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className="mx-auto mt-10 max-w-[1200px] text-[12px] text-faint">
        Illustrative — not a live session.
      </p>
    </section>
  )
}
