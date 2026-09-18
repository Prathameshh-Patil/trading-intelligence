import type { Metadata } from 'next'

import { HowItRuns } from '@/components/landing/HowItRuns'
import { Services } from '@/components/landing/Services'
import { WhoWeAre } from '@/components/landing/WhoWeAre'
import { SectionPage } from '@/components/pages/SectionPage'
import { PAGES } from '@/content/site'

export const metadata: Metadata = { title: 'Services' }

export default function ServicesPage() {
  return (
    <SectionPage {...PAGES.services}>
      <Services />
      <HowItRuns />
      <WhoWeAre />
    </SectionPage>
  )
}
