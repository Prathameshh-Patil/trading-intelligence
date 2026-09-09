'use client'

/**
 * The six questions a sceptical trader asks before paying.
 *
 * Answered the way we would answer them on a call — including the two that are
 * bad for conversion. "Where is the track record" says there is not one, and
 * "is this a signal service" says no; both match NOT_CLAIMING and the policy
 * page word for word, because a person who gets three different answers in
 * three places stops believing all of them.
 *
 * Native <details>, so it opens with JavaScript disabled and is keyboard- and
 * screen-reader-correct without a line of ARIA.
 */

import { Eyebrow } from '../ui'
import { FAQ } from '@/content/site'
import { useReveal } from '@/lib/motion'

export function Faq() {
  const ref = useReveal<HTMLElement>({ childSelector: '[data-q]', stepMs: 55 })

  return (
    <section ref={ref} className="relative overflow-hidden px-6 py-24">
      <div className="aura aura-violet bottom-0 left-1/3 h-[24rem] w-[24rem] opacity-50" />

      <div className="mx-auto grid max-w-[1100px] gap-12 lg:grid-cols-[0.7fr_1.3fr]">
        <div>
          <Eyebrow>Questions</Eyebrow>
          <h2 className="mt-5 text-[clamp(2rem,3.8vw,2.7rem)]">
            The ones you would ask on the call.
          </h2>
        </div>

        <div className="flex flex-col gap-3">
          {FAQ.map((item) => (
            <details key={item.q} data-q className="surface group rounded-2xl px-6 py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[17px] font-semibold [&::-webkit-details-marker]:hidden">
                {item.q}
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-white/10 text-faint transition-transform duration-300 group-open:rotate-45">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <path
                      d="M12 5v14M5 12h14"
                      stroke="currentColor"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
              </summary>
              <p className="mt-4 max-w-[62ch] text-[15px] leading-relaxed text-dim">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
