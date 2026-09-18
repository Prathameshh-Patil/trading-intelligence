/**
 * The landing page: the short version.
 *
 * The argument runs claim → proof → price → the ask, and stops. The chapters
 * that used to follow -- what it shows, where you would use it, what comes
 * with it -- each have a page of their own in the rail now, so the landing
 * page is the wedge performed and nothing else:
 *
 *   1–2  the wedge, performed rather than asserted (both scroll-scrubbed)
 *   3    the price, stated once, and the founding promise beside it
 *   4    the questions a sceptic asks, then the ask
 *
 * Reordering breaks the argument before it breaks the layout -- the caption of
 * each scrubbed section assumes you have watched the one before it.
 */

import { AtAGlance } from '@/components/landing/AtAGlance'
import { Faq } from '@/components/landing/Faq'
import { FinalCta } from '@/components/landing/FinalCta'
import { Hero } from '@/components/landing/Hero'
import { LossyCompression } from '@/components/landing/LossyCompression'
import { PricingPreview } from '@/components/landing/PricingPreview'
import { TwoCandles } from '@/components/landing/TwoCandles'

export default function LandingPage() {
  return (
    <main>
      <Hero />
      <AtAGlance />
      <LossyCompression />
      <TwoCandles />
      <PricingPreview />
      <Faq />
      <FinalCta />
    </main>
  )
}
