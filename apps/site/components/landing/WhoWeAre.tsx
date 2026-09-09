/**
 * Three named people. Static.
 *
 * Ten subscribers buy from people, not from a brand — and every one of them gets
 * an onboarding call with one of these three, so putting the names on the page
 * is just telling the truth early.
 */

import { ButtonLink } from '../ui'
import { CONTACT, TEAM } from '@/content/site'

export function WhoWeAre() {
  return (
    <section className="relative mx-auto max-w-[1200px] px-6 py-24">
      <span className="text-[11px] font-bold tracking-[0.18em] text-violet-lift uppercase">
        WHO IS BEHIND IT
      </span>
      <h2 className="mt-4 max-w-[24ch] text-[clamp(2rem,3.8vw,2.6rem)] font-semibold">
        Three people. You will speak to one of them before you pay.
      </h2>

      <div className="mt-10 grid gap-5 sm:grid-cols-3">
        {TEAM.map((person) => (
          <div key={person.name} className="surface rounded-2xl p-6">
            <h3 className="text-[17px] font-semibold">{person.name}</h3>
            <p className="mt-1 text-[15px] text-dim">{person.role}</p>
          </div>
        ))}
      </div>

      <div className="mt-10 flex flex-wrap items-center gap-4">
        <ButtonLink href="/contact" kind="secondary">Book a call before you buy</ButtonLink>
        <span className="text-sm text-faint">
          Or write to{' '}
          <a className="text-violet-lift" href={`mailto:${CONTACT.email}`}>
            {CONTACT.email}
          </a>{' '}
          — replies {CONTACT.responseTarget}.
        </span>
      </div>
    </section>
  )
}
