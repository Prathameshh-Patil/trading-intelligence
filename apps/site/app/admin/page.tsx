'use client'

/**
 * The page that makes manual payment possible.
 *
 * A screenshot upload with nowhere to be reviewed is a dead end, so this is the
 * other half of checkout: the pending queue, the proof at full size, and the two
 * buttons that issue or refuse a key.
 *
 * The idempotency that matters lives on the server, not here. S5's rule was
 * "webhooks arrive twice — the handler is idempotent or it issues two keys and
 * bills once", and two admins with this queue open is the same bug wearing a
 * different hat. Approving twice returns the key that already exists; this page
 * only has to not fight that.
 */

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'

import { Banner, Button, Card, PageHeader, Pill } from '@/components/ui'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import type { Payment, Ticket, WaitlistEntry } from '@/lib/types'

type Tab = 'payments' | 'tickets' | 'waitlist'

export default function AdminPage() {
  const { me, release, refresh } = useSession()
  const [tab, setTab] = useState<Tab>('payments')
  const [payments, setPayments] = useState<Payment[]>([])
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [waitlist, setWaitlist] = useState<WaitlistEntry[]>([])
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [zoom, setZoom] = useState<Payment | null>(null)

  const isAdmin = me?.role === 'admin'

  const load = useCallback(async () => {
    if (!isAdmin) return
    const [p, t, w] = await Promise.all([
      api.adminPayments().catch(() => []),
      api.adminTickets().catch(() => []),
      api.waitlist().catch(() => []),
    ])
    setPayments(p)
    setTickets(t)
    setWaitlist(w)
  }, [isAdmin])

  useEffect(() => {
    void load()
  }, [load])

  if (!isAdmin) {
    return (
      <main className="mx-auto max-w-[760px] px-6 py-16">
        <PageHeader title="Admins only" lede="Nothing here is available to a normal account." />
        <Link href="/login" className="text-violet-lift">Sign in →</Link>
      </main>
    )
  }

  async function approve(p: Payment) {
    setError('')
    try {
      const key = await api.approvePayment(p.id)
      setNote(`Approved ${p.email} — key ${key.key}`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approve failed.')
    }
  }

  async function reject(p: Payment) {
    // Shown verbatim to the buyer, so the prompt says so.
    const reason = window.prompt(`Why is ${p.email}'s payment being refused?\n\nThey will read this.`)
    if (!reason) return
    setError('')
    try {
      await api.rejectPayment(p.id, reason)
      setNote(`Refused ${p.email}.`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reject failed.')
    }
  }

  const pending = payments.filter((p) => p.status === 'pending').length
  const open = tickets.filter((t) => t.status === 'open').length

  return (
    <main className="mx-auto max-w-[1000px] px-6 py-16">
      <PageHeader
        eyebrow="ADMIN"
        title="Queue"
        lede={`${pending} payment${pending === 1 ? '' : 's'} waiting · ${open} open ticket${open === 1 ? '' : 's'}`}
      />

      <Card className="mb-6 flex flex-wrap items-center justify-between gap-5">
        <div>
          <h2 className="text-[18px] font-semibold">
            The site is {release.isPublic ? 'public' : 'pre-release'}
          </h2>
          <p className="max-w-[62ch] text-sm text-faint">
            {release.isPublic
              ? 'Everyone sees the landing page, the pricing and the checkout.'
              : 'Strangers see the holding page and the waitlist form. You see everything because you are signed in as an admin.'}
          </p>
        </div>
        <Button
          kind="secondary"
          onClick={async () => {
            await api.setPublic(!release.isPublic)
            await refresh()
          }}
        >
          {release.isPublic ? 'Back to pre-release' : 'Make the site public'}
        </Button>
      </Card>

      {note ? <Banner kind="success">{note}</Banner> : null}
      {error ? <Banner kind="error">{error}</Banner> : null}

      <div role="tablist" className="mb-6 inline-flex gap-1 surface rounded-xl p-1">
        {(['payments', 'tickets', 'waitlist'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold capitalize ${
              tab === t ? 'grad text-white' : 'text-dim'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'payments' ? (
        payments.length === 0 ? (
          <p className="text-sm text-faint">Nothing submitted yet.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {payments.map((p) => (
              <Card key={p.id} className="flex flex-col gap-5 sm:flex-row">
                <button
                  type="button"
                  onClick={() => setZoom(p)}
                  className="shrink-0 overflow-hidden rounded-xl border border-white/[0.08]"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={p.proofUrl}
                    alt={`Payment proof from ${p.email}`}
                    className="h-32 w-32 object-cover"
                  />
                </button>

                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-3">
                    <strong className="num">{p.email}</strong>
                    <Pill status={p.status} />
                  </div>
                  <p className="num text-sm text-faint">
                    {p.plan === 'core_journal' ? 'Core + Journal' : 'Core'} ·{' '}
                    {p.method.toUpperCase()} · {p.currency === 'usd' ? '$' : '₹'}
                    {p.amount} · {new Date(p.createdAt).toLocaleString()}
                  </p>
                  <p className="mt-2 text-sm">
                    Reference <code className="num">{p.reference}</code>
                  </p>
                  {p.rejectionReason ? (
                    <p className="mt-2 text-sm text-faint">Refused: {p.rejectionReason}</p>
                  ) : null}

                  {p.status === 'pending' ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                      <Button onClick={() => approve(p)}>Approve and issue key</Button>
                      <Button kind="danger" onClick={() => reject(p)}>Refuse</Button>
                    </div>
                  ) : null}
                </div>
              </Card>
            ))}
          </div>
        )
      ) : null}

      {tab === 'tickets' ? (
        tickets.length === 0 ? (
          <p className="text-sm text-faint">No tickets.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {tickets.map((t) => (
              <Card key={t.id}>
                <div className="flex flex-wrap items-center gap-3">
                  <code className="num">{t.ref}</code>
                  <strong>{t.subject}</strong>
                  <Pill status={t.status} />
                </div>
                <p className="num mt-1 text-sm text-faint">
                  {t.email} · {t.category} · {new Date(t.createdAt).toLocaleString()}
                </p>
                <p className="mt-2 text-dim">{t.body}</p>
                {t.replies.map((r) => (
                  <div key={r.id} className="mt-3 border-l-2 border-violet pl-4">
                    <span className="num text-xs text-faint">
                      Support · {new Date(r.createdAt).toLocaleString()}
                    </span>
                    <p className="text-ink">{r.body}</p>
                  </div>
                ))}
                <div className="mt-4 flex flex-wrap gap-3">
                  <Button
                    onClick={async () => {
                      const body = window.prompt(`Reply to ${t.ref} — ${t.subject}`)
                      if (!body) return
                      await api.replyToTicket(t.id, body).catch(() => setError('Reply failed.'))
                      await load()
                    }}
                  >
                    Reply
                  </Button>
                  {t.status !== 'closed' ? (
                    <Button
                      kind="secondary"
                      onClick={async () => {
                        await api.closeTicket(t.id)
                        await load()
                      }}
                    >
                      Close
                    </Button>
                  ) : null}
                </div>
              </Card>
            ))}
          </div>
        )
      ) : null}

      {tab === 'waitlist' ? (
        waitlist.length === 0 ? (
          <p className="text-sm text-faint">Nobody on the list yet.</p>
        ) : (
          <table className="num w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-[11px] tracking-wider text-faint uppercase">
                <th className="border-b border-white/[0.08] px-3 py-2.5">Email</th>
                <th className="border-b border-white/[0.08] px-3 py-2.5">Joined</th>
              </tr>
            </thead>
            <tbody>
              {waitlist.map((w) => (
                <tr key={w.email}>
                  <td className="border-b border-white/[0.08] px-3 py-2.5">{w.email}</td>
                  <td className="border-b border-white/[0.08] px-3 py-2.5">
                    {new Date(w.createdAt).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : null}

      {zoom ? (
        <div
          role="dialog"
          aria-label="Payment proof"
          onClick={() => setZoom(null)}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-black/90 p-8"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={zoom.proofUrl}
            alt={`Payment proof from ${zoom.email}`}
            className="max-h-[82vh] max-w-[min(1000px,92vw)] rounded-xl"
          />
          <p className="num text-sm text-dim">
            {zoom.email} · {zoom.reference} — click anywhere to close
          </p>
        </div>
      ) : null}
    </main>
  )
}
