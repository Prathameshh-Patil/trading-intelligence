'use client'

/**
 * The portal's frame: the left rail, the live indicator, and the gate.
 *
 * Anyone not signed in sees the login page. A signed-in account that is not
 * an admin sees one sentence and nothing else -- the API refuses it too, so
 * this is presentation, not the security boundary.
 */

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import type { Stats } from '@vision-hub/contracts'
import {
  Button,
  ClockIcon,
  HomeIcon,
  InboxIcon,
  KeyIcon,
  LifeBuoyIcon,
  ListIcon,
  LiveDot,
  Mark,
  SettingsIcon,
  SidebarShell,
  Spinner,
  UsersIcon,
} from '@vision-hub/ui'

import { api } from '@/lib/api'
import { useLive, useLiveStatus } from '@/lib/live'
import { useSession } from '@/lib/session'

function Badge({ n, tone = 'warn' }: { n: number; tone?: 'warn' | 'default' }) {
  if (!n) return null
  return (
    <span
      className={`num rounded-full px-1.5 py-0.5 text-[10.5px] font-bold ${
        tone === 'warn' ? 'bg-warn/15 text-warn' : 'bg-white/[0.08] text-dim'
      }`}
    >
      {n}
    </span>
  )
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
      <Mark size={28} />
      <span>
        Vision Hub <span className="ml-1 rounded-md bg-violet/15 px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-violet-lift uppercase">Admin</span>
      </span>
    </Link>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  const { user, ready } = useSession()
  const router = useRouter()
  const status = useLiveStatus()
  const [stats, setStats] = useState<Stats | null>(null)

  const isAdmin = user?.role === 'admin'

  const loadStats = useCallback(() => {
    if (!isAdmin) return
    api.admin.stats().then(setStats).catch(() => {})
  }, [isAdmin])

  useEffect(loadStats, [loadStats])
  useLive([], loadStats)

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Loading…" />
      </div>
    )
  }

  if (!user) {
    return <>{children}</>
  }

  if (!isAdmin) {
    return (
      <main className="mx-auto max-w-[520px] px-6 py-24 text-center">
        <Mark size={40} />
        <h1 className="mt-6 text-[24px]">This portal is for administrators</h1>
        <p className="mt-3 text-dim">
          You are signed in as <span className="num">{user.email}</span>, which is a customer account.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button kind="secondary" onClick={() => api.logout()}>
            Sign out
          </Button>
        </div>
      </main>
    )
  }

  return (
    <SidebarShell
      brand={<Brand />}
      groups={[
        {
          items: [
            { href: '/', label: 'Overview', icon: <HomeIcon size={17} /> },
            {
              href: '/approvals',
              label: 'Approvals',
              icon: <InboxIcon size={17} />,
              badge: <Badge n={stats?.pending ?? 0} />,
            },
            { href: '/users', label: 'Users', icon: <UsersIcon size={17} />, prefix: true },
            { href: '/keys', label: 'Licence keys', icon: <KeyIcon size={17} /> },
          ],
        },
        {
          title: 'Support',
          items: [
            {
              href: '/tickets',
              label: 'Tickets',
              icon: <LifeBuoyIcon size={17} />,
              badge: <Badge n={stats?.open_tickets ?? 0} />,
            },
            {
              href: '/waitlist',
              label: 'Waitlist',
              icon: <ListIcon size={17} />,
              badge: <Badge n={stats?.waitlist ?? 0} tone="default" />,
            },
          ],
        },
        {
          title: 'System',
          items: [
            { href: '/audit', label: 'Audit log', icon: <ClockIcon size={17} /> },
            { href: '/settings', label: 'Settings', icon: <SettingsIcon size={17} /> },
          ],
        },
      ]}
      topbar={
        <>
          <LiveDot status={status} />
          <span className="num hidden max-w-[22ch] truncate text-[12px] text-faint sm:inline">{user.email}</span>
          <Button
            kind="ghost"
            size="sm"
            onClick={async () => {
              await api.logout()
              router.push('/login')
            }}
          >
            Sign out
          </Button>
        </>
      }
      railFooter={<span>{stats ? `${stats.live_admins} admin${stats.live_admins === 1 ? '' : 's'} online` : ''}</span>}
    >
      <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
    </SidebarShell>
  )
}
