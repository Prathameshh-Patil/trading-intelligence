'use client'

/** Overview: the numbers that matter this morning, and what just happened. */

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import type { AuditEntry, Release, ServerEvent, Stats } from '@vision-hub/contracts'
import { Button, Card, PageHeader, StatCard, timeAgo, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

const LABELS: Partial<Record<ServerEvent['type'], string>> = {
  'user.signed_up': 'signed up',
  'user.approved': 'was approved',
  'user.rejected': 'was rejected',
  'user.suspended': 'was suspended',
  'user.reinstated': 'was reinstated',
  'user.role_changed': 'changed role',
  'key.rotated': 'rotated a key',
  'key.revoked': 'had a key revoked',
  'payment.submitted': 'attached a payment proof',
  'ticket.created': 'opened a ticket',
  'ticket.replied': 'ticket replied',
  'ticket.closed': 'ticket closed',
  'release.changed': 'release switch changed',
  'waitlist.joined': 'joined the waitlist',
}

type Item = { id: string; at: number; text: string }

function describe(e: ServerEvent): string | null {
  const label = LABELS[e.type]
  if (!label) return null
  const who = 'email' in e.data && e.data.email ? e.data.email : 'ref' in e.data ? e.data.ref : ''
  return `${who} ${label}`.trim()
}

export default function OverviewPage() {
  return (
    <RequireAdmin>
      <Overview />
    </RequireAdmin>
  )
}

function Overview() {
  const toast = useToast()
  const [stats, setStats] = useState<Stats | null>(null)
  const [release, setRelease] = useState<Release | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [feed, setFeed] = useState<Item[]>([])

  const load = useCallback(() => {
    api.admin.stats().then(setStats).catch(() => {})
    api.release().then(setRelease).catch(() => {})
    api.admin.audit().then((a) => setAudit(a.slice(0, 8))).catch(() => {})
  }, [])

  useEffect(load, [load])
  useLive([], (e) => {
    load()
    const text = describe(e)
    if (text) setFeed((f) => [{ id: `${Date.now()}-${Math.random()}`, at: Date.now(), text }, ...f].slice(0, 12))
  })

  return (
    <>
      <PageHeader compact title="Overview" lede="What is waiting, what is live, and what just happened." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Awaiting approval" value={stats?.pending ?? '—'} tone={stats?.pending ? 'warn' : 'default'} />
        <StatCard label="Approved" value={stats?.approved ?? '—'} tone="good" />
        <StatCard label="Active keys" value={stats?.active_keys ?? '—'} />
        <StatCard label="Validations · 24h" value={stats?.validations_24h ?? '—'} hint="desktop apps that checked in" />
        <StatCard label="Open tickets" value={stats?.open_tickets ?? '—'} tone={stats?.open_tickets ? 'warn' : 'default'} />
        <StatCard label="Sign-ups · 7d" value={stats?.signups_7d ?? '—'} hint={`${stats?.waitlist ?? 0} on the waitlist`} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card title="Release" className="lg:col-span-1">
          <p className="text-[14px] text-dim">
            The site is{' '}
            <strong className={release?.is_public ? 'text-bid' : 'text-warn'}>
              {release ? (release.is_public ? 'public' : 'pre-release') : '…'}
            </strong>
            .{' '}
            {release?.is_public
              ? 'Everyone sees the landing page, the pricing and sign-up.'
              : 'Strangers see the holding page and the waitlist form; signed-in accounts see everything.'}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              kind={release?.is_public ? 'secondary' : 'primary'}
              size="sm"
              onClick={async () => {
                if (!release) return
                try {
                  setRelease(await api.setPublic(!release.is_public))
                  toast({ kind: 'success', title: release.is_public ? 'Back to pre-release' : 'The site is public' })
                } catch (e) {
                  toast({ kind: 'error', title: 'Could not change the switch', body: (e as Error).message })
                }
              }}
            >
              {release?.is_public ? 'Back to pre-release' : 'Make the site public'}
            </Button>
            <Link href="/approvals" className="inline-flex items-center text-[13px] text-violet-lift hover:underline">
              Open the queue →
            </Link>
          </div>
        </Card>

        <Card title="Live" className="lg:col-span-1" actions={<span className="text-[12px] text-faint">this session</span>}>
          {feed.length === 0 ? (
            <p className="text-[13px] text-faint">Nothing yet. Events appear here as they happen — no refresh needed.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-[13px]">
              {feed.map((f) => (
                <li key={f.id} className="vh-flash flex justify-between gap-3 rounded-md px-1">
                  <span className="truncate">{f.text}</span>
                  <span className="num shrink-0 text-faint">{timeAgo(new Date(f.at).toISOString())}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent admin actions" className="lg:col-span-1" actions={<Link href="/audit" className="text-[12px] text-violet-lift">All →</Link>}>
          {audit.length === 0 ? (
            <p className="text-[13px] text-faint">No actions recorded yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-[13px]">
              {audit.map((a) => (
                <li key={a.id} className="flex justify-between gap-3">
                  <span className="truncate">
                    <span className="num text-violet-lift">{a.action}</span>{' '}
                    <span className="text-dim">{(a.detail?.email as string) ?? `${a.target_type} ${a.target_id}`}</span>
                  </span>
                  <span className="num shrink-0 text-faint">{timeAgo(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}
