'use client'

/**
 * The transition between routes.
 *
 * Keyed on the pathname, so React discards the old subtree and mounts a new one
 * — which is what lets a plain CSS animation run on every navigation without any
 * transition library.
 *
 * Kept short (320ms) and small (10px). A page transition is a courtesy that says
 * "something changed"; anything longer and the site feels slower than it is,
 * which on a page arguing for a low-latency tool is the wrong impression.
 */

import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'

export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  return (
    <div key={pathname} className="page-enter">
      {children}
    </div>
  )
}
