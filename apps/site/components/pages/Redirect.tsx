'use client'

/**
 * A route that used to exist, sending its visitors on.
 *
 * `output: 'export'` has no server to answer with a 301, so the redirect is
 * the page: a `<meta refresh>` for anything without JavaScript, and
 * `router.replace` for everything else so the old address never lands in
 * history.
 */

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export function Redirect({ to }: { to: string }) {
  const router = useRouter()
  useEffect(() => router.replace(to), [router, to])
  return (
    <>
      <meta httpEquiv="refresh" content={`0;url=${to}`} />
      <main className="mx-auto max-w-[760px] px-6 py-16 text-sm text-faint">
        Moved to <a href={to} className="text-violet-lift">{to}</a>.
      </main>
    </>
  )
}
