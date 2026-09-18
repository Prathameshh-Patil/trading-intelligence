import type { Metadata } from 'next'

import { Absorption } from '@/components/landing/Absorption'
import { UseCases } from '@/components/landing/UseCases'
import { SectionPage } from '@/components/pages/SectionPage'
import { PAGES } from '@/content/site'

export const metadata: Metadata = { title: 'Use cases' }

export default function UseCasesPage() {
  return (
    <SectionPage {...PAGES.useCases}>
      <UseCases />
      <Absorption />
    </SectionPage>
  )
}
