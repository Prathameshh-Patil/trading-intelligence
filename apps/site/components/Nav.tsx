'use client'

/**
 * The nav.
 *
 * Section links only appear on the landing page, and only once the site is
 * past the gate — a stranger looking at the holding page has no sections to
 * jump to, and a link to one would be a link to a 404 with extra steps.
 *
 * Anchors are handled by hand rather than by the browser: Lenis owns scrolling,
 * and a native `#hash` jump teleports past it, which looks broken next to
 * everything else on the page.
 */

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'

import { Mark } from './ui'
import { useSession } from '@/lib/session'
import { BRAND } from '@/content/site'

const SECTIONS = [
  { id: 'features', label: 'Features' },
  { id: 'use-cases', label: 'Use cases' },
  { id: 'services', label: 'Services' },
] as const

export function Nav() {
  const { me, signOut, canSeeSite } = useSession()
  const router = useRouter()
  const pathname = usePathname()
  const onLanding = pathname === '/'

  function jump(id: string) {
    if (!onLanding) {
      router.push(`/#${id}`)
      return
    }
    const el = document.getElementById(id)
    if (!el) return
    window.scrollTo({
      top: el.getBoundingClientRect().top + window.scrollY - 80,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })
  }

  return (
    <nav className="sticky top-0 z-30 border-b border-white/[0.06] bg-bg/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <Mark />
          {BRAND.name}
        </Link>

        <div className="order-3 flex w-full flex-wrap items-center gap-x-7 gap-y-2 text-[14px] text-dim sm:order-none sm:w-auto">
          {canSeeSite
            ? SECTIONS.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => jump(section.id)}
                  className="transition hover:text-ink"
                >
                  {section.label}
                </button>
              ))
            : null}
          {canSeeSite ? (
            <Link href="/pricing" className="transition hover:text-ink">Pricing</Link>
          ) : null}
          <Link href="/support" className="transition hover:text-ink">Support</Link>
          <Link href="/contact" className="transition hover:text-ink">Contact</Link>
          {me?.role === 'admin' ? (
            <Link href="/admin" className="text-violet-lift transition hover:brightness-125">
              Admin
            </Link>
          ) : null}
        </div>

        {me ? (
          <div className="flex items-center gap-3">
            <Link href="/key" className="num max-w-[18ch] truncate text-[13px] text-faint">
              {me.email}
            </Link>
            <button
              type="button"
              className="surface rounded-lg px-3.5 py-2 text-sm font-semibold transition hover:border-white/20"
              onClick={async () => {
                await signOut()
                router.push('/')
              }}
            >
              Sign out
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="grad glow rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110"
          >
            Sign in
          </Link>
        )}
      </div>
    </nav>
  )
}
