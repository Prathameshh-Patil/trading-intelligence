/**
 * The landing page: the sequence, in order.
 *
 * The order is the argument, and it runs claim → proof → application → terms:
 *
 *   1–2  the wedge, performed rather than asserted (both scroll-scrubbed)
 *   3–5  what it shows, where you would use it, one worked example
 *   6–7  how it runs, and what comes with it beyond the software
 *   8–9  the difference stated flatly, then what we refuse to claim
 *   10+  price, the questions, the people, the ask
 *
 * Reordering breaks the argument before it breaks the layout — the caption of
 * each scrubbed section assumes you have watched the one before it.
 */

import { Absorption } from '@/components/landing/Absorption'
import { AtAGlance } from '@/components/landing/AtAGlance'
import { Compare } from '@/components/landing/Compare'
import { Faq } from '@/components/landing/Faq'
import { FinalCta } from '@/components/landing/FinalCta'
import { Hero } from '@/components/landing/Hero'
import { HowItRuns } from '@/components/landing/HowItRuns'
import { LossyCompression } from '@/components/landing/LossyCompression'
import { NotClaiming } from '@/components/landing/NotClaiming'
import { PricingPreview } from '@/components/landing/PricingPreview'
import { Services } from '@/components/landing/Services'
import { TwoCandles } from '@/components/landing/TwoCandles'
import { UseCases } from '@/components/landing/UseCases'
import { WhatItShows } from '@/components/landing/WhatItShows'
import { WhoWeAre } from '@/components/landing/WhoWeAre'

export default function LandingPage() {
  return (
    <main>
      <Hero />
      <AtAGlance />
      <LossyCompression />
      <TwoCandles />
      <WhatItShows />
      <UseCases />
      <Absorption />
      <HowItRuns />
      <Services />
      <Compare />
      <NotClaiming />
      <PricingPreview />
      <Faq />
      <WhoWeAre />
      <FinalCta />
    </main>
  )
}
