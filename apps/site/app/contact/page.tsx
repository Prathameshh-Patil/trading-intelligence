/** Call or email. Two channels, honestly described, and where to go instead. */

import Link from 'next/link'

import { Card, PageHeader } from '@/components/ui'
import { CONTACT } from '@/content/site'

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-[900px] px-6 py-16">
      <PageHeader
        eyebrow="CONTACT"
        title="Talk to a person"
        lede={`There are three of us. You will not get a bot and you will not get a queue — you will get one of us, ${CONTACT.responseTarget}.`}
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-[19px] font-semibold">Email</h2>
          <p className="mb-4 text-dim">
            Best for anything with a screenshot, a log, or a question that needs thinking about.
          </p>
          <a
            className="num text-violet-lift break-all"
            href={`mailto:${CONTACT.email}`}
          >
            {CONTACT.email}
          </a>
          <p className="mt-3 text-sm text-faint">Replies {CONTACT.responseTarget}.</p>
        </Card>

        <Card>
          <h2 className="mb-2 text-[19px] font-semibold">Phone</h2>
          <p className="mb-4 text-dim">
            Best for install trouble, and anything where a back-and-forth by email would take a
            week.
          </p>
          <a className="num text-violet-lift" href={`tel:${CONTACT.phone.replace(/\s/g, '')}`}>
            {CONTACT.phone}
          </a>
          <p className="mt-3 text-sm text-faint">
            {CONTACT.hours}. Outside those hours, email is faster.
          </p>
        </Card>
      </div>

      <Card className="mt-5">
        <h2 className="mb-2 text-[19px] font-semibold">If it is about a payment or a key</h2>
        <p className="text-dim">
          Raise a ticket instead — <Link href="/support" className="text-violet-lift">the support
          form</Link>. It attaches your account and your payment history to the message, which
          saves the first two emails of every one of those conversations.
        </p>
      </Card>
    </main>
  )
}
