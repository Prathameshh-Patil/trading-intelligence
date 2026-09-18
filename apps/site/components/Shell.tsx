'use client'

/**
 * The site's frame: the left rail, and the account block at the bottom of it.
 *
 * Six destinations in the rail, in the order `content/site.ts` fixes them.
 * The landing page keeps window scroll -- `SidebarShell` is a fixed column
 * beside the document, not a scroll container -- so the scrubbed scenes on
 * `/` keep working untouched.
 *
 * Before release the rail only shows what the visitor may open: the four
 * pages in `ALWAYS_OPEN` for a stranger, everything for a signed-in account.
 * A link to a page that will render the holding screen is a link to a 404
 * with extra steps.
 */

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import type { ReactNode } from 'react'
import {
  Button,
  LayersIcon,
  LifeBuoyIcon,
  LiveDot,
  MailIcon,
  Mark,
  Pill,
  SidebarShell,
  SparkIcon,
  TagIcon,
  UserIcon,
  UsersIcon,
} from '@vision-hub/ui'

import { BRAND, NAV } from '@/content/site'
import { useLiveStatus } from '@/lib/live'
import { useSession } from '@/lib/session'

const ICONS: Record<(typeof NAV)[number]['href'], ReactNode> = {
  '/features': <SparkIcon size={17} />,
  '/use-cases': <LayersIcon size={17} />,
  '/services': <UsersIcon size={17} />,
  '/pricing': <TagIcon size={17} />,
  '/support': <LifeBuoyIcon size={17} />,
  '/contact': <MailIcon size={17} />,
}

/** Open before release: the ways in, and the ways to reach a human. */
export const ALWAYS_OPEN = new Set(['/login', '/signup', '/support', '/contact'])

const ADMIN_URL = process.env.NEXT_PUBLIC_ADMIN_URL

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
      <Mark size={28} />
      {BRAND.name}
    </Link>
  )
}

function AccountBlock() {
  const { user, signOut } = useSession()
  const status = useLiveStatus()
  const router = useRouter()
  const pathname = usePathname()

  if (!user) {
    return (
      <div className="flex flex-col gap-2 p-1">
        <Link href="/login" className="grad glow rounded-xl px-4 py-2.5 text-center text-[14px] font-semibold text-white transition hover:brightness-110">
          Sign in
        </Link>
        <Link href="/signup" className="text-center text-[13px] text-dim transition hover:text-ink">
          Create an account
        </Link>
      </div>
    )
  }

  const onAccount = pathname === '/account'
  return (
    <div className="flex flex-col gap-2 p-1">
      <Link
        href="/account"
        aria-current={onAccount ? 'page' : undefined}
        className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition ${
          onAccount ? 'bg-violet/15' : 'hover:bg-white/[0.05]'
        }`}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/[0.06] text-dim">
          <UserIcon size={16} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="num block truncate text-[13px] text-ink">{user.email}</span>
          <span className="mt-0.5 flex items-center gap-1.5">
            <Pill status={user.status} />
            {user.role === 'admin' ? <Pill status="admin" /> : null}
          </span>
        </span>
      </Link>
      <div className="flex items-center justify-between gap-2 px-1">
        {user.role === 'admin' && ADMIN_URL ? (
          <a href={ADMIN_URL} className="text-[12px] text-violet-lift transition hover:brightness-125">
            Admin portal →
          </a>
        ) : (
          <LiveDot status={status} />
        )}
        <Button
          kind="ghost"
          size="sm"
          onClick={async () => {
            await signOut()
            router.push('/')
          }}
        >
          Sign out
        </Button>
      </div>
    </div>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  const { canSeeSite } = useSession()

  const items = NAV.filter((item) => canSeeSite || ALWAYS_OPEN.has(item.href)).map((item) => ({
    href: item.href,
    label: item.label,
    icon: ICONS[item.href],
  }))

  return (
    <SidebarShell
      brand={<Brand />}
      groups={[{ items }]}
      railFooter={
        <Link href="/policy" className="transition hover:text-dim">
          Terms, refunds &amp; privacy
        </Link>
      }
      footer={<AccountBlock />}
    >
      {children}
    </SidebarShell>
  )
}
