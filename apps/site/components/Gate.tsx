'use client'

/**
 * The pre-release gate, client half.
 *
 * Three layers protect the unreleased site, and only the first is a security
 * property:
 *
 *   1. `services/api` refuses pre-release data to a session with no account at
 *      all — signing in is the whole requirement, admin or not. That is the
 *      real gate, and it is not in this file.
 *   2. This component declines to *render* the site when the server says
 *      `can_preview` is false, so a stranger who guesses `/pricing` gets the
 *      holding page rather than a 404 confirming the route exists.
 *   3. Pages show nothing they were not given.
 *
 * A static bundle can only ever do 2 and 3. Anyone can read this file out of the
 * deployed JavaScript — which is exactly why it asks the server rather than
 * deciding, and why nothing secret lives on the client side of the line.
 */

import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'
import { Spinner } from '@vision-hub/ui'

import { Footer } from './Footer'
import { Holding } from './Holding'
import { PageTransition } from './PageTransition'
import { ALWAYS_OPEN, Shell } from './Shell'
import { useSession } from '@/lib/session'

export function Gate({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const { ready, canSeeSite, release } = useSession()

  if (!ready) {
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <Spinner label="Loading…" />
      </div>
    )
  }

  if (!canSeeSite && !ALWAYS_OPEN.has(pathname)) return <Holding />

  return (
    <div className="grain">
      <Shell>
        {/*
          Keyed on `canSeeSite`, not just `!release.is_public` — the pages in
          ALWAYS_OPEN render for anonymous visitors too (that is the point of
          being always open), and a banner claiming "you are signed in" to
          someone looking at the login page because they are NOT signed in is
          exactly the kind of self-contradicting chrome that makes a site feel
          untrustworthy on the page asking someone to trust it with a password.
        */}
        {!release.is_public && canSeeSite ? (
          <div className="border-b border-violet/25 bg-violet/10 px-4 py-2 text-center text-[13px] font-semibold text-violet-lift">
            Pre-release preview — visitors without an account see the holding page. You are seeing
            this because you are signed in.
          </div>
        ) : null}

        <PageTransition>{children}</PageTransition>
        <Footer />
      </Shell>
    </div>
  )
}
