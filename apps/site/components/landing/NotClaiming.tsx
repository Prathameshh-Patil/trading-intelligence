/**
 * The section that does not move. Deliberately.
 *
 * No reveal, no parallax, no stagger, not even a fade — and this is a server
 * component with no client hooks precisely so nobody can add one without
 * noticing they are changing what the section is.
 *
 * The reason: after five scroll-driven sections, a section that stops moving
 * reads as someone dropping the sales voice. The stillness is the argument, and
 * it is the most persuasive thing on the page because it refuses to perform.
 * Larger type, more whitespace, highest contrast. Do not "fix" this.
 */

import { Eyebrow } from '../ui'
import { NOT_CLAIMING } from '@/content/site'

export function NotClaiming() {
  return (
    <section className="relative mx-auto max-w-[1200px] px-6 py-32">
      {/* Muted, not violet. This section is where the sales voice drops. */}
      <Eyebrow muted>{NOT_CLAIMING.eyebrow}</Eyebrow>
      <h2 className="mt-5 max-w-[20ch] text-[clamp(2.2rem,4.6vw,3.4rem)] font-semibold text-ink">
        {NOT_CLAIMING.title}
      </h2>

      <div className="mt-14 grid gap-12 md:grid-cols-3">
        {NOT_CLAIMING.blocks.map((block) => (
          <div key={block.title}>
            <h3 className="mb-3 text-[18px] font-semibold text-ink">{block.title}</h3>
            <p className="text-[16px] leading-relaxed text-dim">{block.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
