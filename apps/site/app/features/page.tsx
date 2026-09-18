import type { Metadata } from 'next'

import { Compare } from '@/components/landing/Compare'
import { NotClaiming } from '@/components/landing/NotClaiming'
import { WhatItShows } from '@/components/landing/WhatItShows'
import { SectionPage } from '@/components/pages/SectionPage'
import { PAGES } from '@/content/site'

export const metadata: Metadata = { title: 'Features' }

export default function FeaturesPage() {
  return (
    <SectionPage {...PAGES.features}>
      <WhatItShows />
      <Compare />
      <NotClaiming />
    </SectionPage>
  )
}
