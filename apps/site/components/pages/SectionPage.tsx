/**
 * The frame for a content page in the rail: one header, then the landing
 * sections that belong to it, then the same close every page ends on.
 *
 * The sections themselves are the landing components unchanged -- they were
 * written to stand alone (each owns its reveal and its scrubbing), and a page
 * made of them is the same argument split into chapters rather than a second
 * copy of it.
 */

import type { ReactNode } from 'react'
import { PageHeader } from '@vision-hub/ui'

import { FinalCta } from '@/components/landing/FinalCta'

export function SectionPage({
  eyebrow,
  title,
  lede,
  children,
}: {
  eyebrow: string
  title: string
  lede: string
  children: ReactNode
}) {
  return (
    <main>
      <div className="relative mx-auto max-w-[1200px] px-6 pt-16 pb-4">
        <div className="aura aura-violet -top-40 -left-20 h-[28rem] w-[36rem] opacity-60" />
        <PageHeader eyebrow={eyebrow} title={title} lede={lede} />
      </div>
      {children}
      <FinalCta />
    </main>
  )
}
