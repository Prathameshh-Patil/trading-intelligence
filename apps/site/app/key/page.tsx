'use client'

/**
 * The post-purchase page — S5's exit door and nothing else.
 *
 * `contracts.md` S5 specifies: poll `GET /api/v1/keys/mine` every 2s for 30s,
 * then show a support link. That cadence was written for a card processor
 * settling asynchronously, where thirty seconds is usually enough. Approval here
 * is a human reading a screenshot, so thirty seconds usually is NOT enough — the
 * polling stays, because the key really can arrive while someone sits here, but
 * what follows it says the true thing rather than the reassuring one.
 *
 * The behaviour worth keeping exactly: **a 404 is "not yet", never an error.** A
 * page that assumes the key exists on first load shows a failure to a buyer who
 * has just paid.
 */

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Banner, CopyField, PageHeader, Pill, Spinner } from '@/components/ui'
import { CONTACT } from '@/content/site'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import { ApiError, type LicenceKey, type Payment } from '@/lib/types'

const POLL_MS = 2000
const POLL_FOR_MS = 30_000

export default function KeyPage() {
  const { me } = useSession()
  const [key, setKey] = useState<LicenceKey | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [polling, setPolling] = useState(true)
  const startedAt = useRef(Date.now())

  const poll = useCallback(async () => {
    try {
      setKey(await api.keysMine())
      setPolling(false)
    } catch (err) {
      // 404 is the documented "not yet" and is not shown to anyone.
      if (!(err instanceof ApiError && err.status === 404)) setPolling(false)
    }
  }, [])

  useEffect(() => {
    if (!me) return
    void poll()
    void api.myPayments().then(setPayments).catch(() => setPayments([]))

    const timer = window.setInterval(() => {
      if (Date.now() - startedAt.current > POLL_FOR_MS) {
        setPolling(false)
        window.clearInterval(timer)
        return
      }
      void poll()
    }, POLL_MS)

    return () => window.clearInterval(timer)
  }, [me, poll])

  if (!me) {
    return (
      <main className="mx-auto max-w-[760px] px-6 py-16">
        <PageHeader title="Sign in to see your key" />
        <Link href="/login" className="text-violet-lift">Sign in →</Link>
      </main>
    )
  }

  const rejected = payments.find((p) => p.status === 'rejected')

  return (
    <main className="mx-auto max-w-[760px] px-6 py-16">
      <PageHeader
        eyebrow="YOUR LICENCE"
        title={key ? 'Your key is ready' : 'Payment received — it is with a person'}
      />

      {key ? (
        <>
          <Banner kind="success">
            Approved. Paste this into the desktop app under <strong>Settings → Licence</strong>.
          </Banner>
          <CopyField label="Licence key" value={key.key} />
          <p className="text-sm text-faint">
            Tier <Pill status={key.tier} /> · issued{' '}
            <span className="num">{new Date(key.created_at).toLocaleString()}</span>
          </p>
          <p className="mt-6 text-dim">
            Next: install the app, connect your own feed, and book the onboarding call. We do one
            with every subscriber, and it is where install problems go to die.
          </p>
          <Link href="/contact" className="text-violet-lift">Book the onboarding call →</Link>
        </>
      ) : (
        <>
          {polling ? (
            <Spinner label="Checking for your key…" />
          ) : (
            <Banner kind="info">
              <strong>It is with one of us now.</strong> We check payments by hand — usually
              within a few hours, always {CONTACT.responseTarget}. You do not need to keep this
              page open: your key arrives by email, and it will be here when you come back.
            </Banner>
          )}

          {rejected ? (
            <Banner kind="error">
              <strong>We could not match one of your payments.</strong>{' '}
              {rejected.rejectionReason ?? 'No reason was recorded.'} Nothing has been taken from
              you — <Link href="/support" className="underline">raise a ticket</Link> and we will
              sort it out.
            </Banner>
          ) : null}
        </>
      )}

      {payments.length ? (
        <section className="mt-12">
          <h2 className="mb-4 text-[19px] font-semibold">Your payments</h2>
          <div className="overflow-x-auto">
            <table className="num w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-[11px] tracking-wider text-faint uppercase">
                  <th className="border-b border-white/[0.08] px-3 py-2.5">Submitted</th>
                  <th className="border-b border-white/[0.08] px-3 py-2.5">Plan</th>
                  <th className="border-b border-white/[0.08] px-3 py-2.5">Rail</th>
                  <th className="border-b border-white/[0.08] px-3 py-2.5">Amount</th>
                  <th className="border-b border-white/[0.08] px-3 py-2.5">Reference</th>
                  <th className="border-b border-white/[0.08] px-3 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td className="border-b border-white/[0.08] px-3 py-2.5 whitespace-nowrap">
                      {new Date(p.createdAt).toLocaleDateString()}
                    </td>
                    <td className="border-b border-white/[0.08] px-3 py-2.5 whitespace-nowrap">
                      {p.plan === 'core_journal' ? 'Core + Journal' : 'Core'}
                    </td>
                    <td className="border-b border-white/[0.08] px-3 py-2.5">{p.method.toUpperCase()}</td>
                    <td className="border-b border-white/[0.08] px-3 py-2.5 whitespace-nowrap">
                      {p.currency === 'usd' ? '$' : '₹'}
                      {p.amount}
                    </td>
                    <td className="border-b border-white/[0.08] px-3 py-2.5">{p.reference}</td>
                    <td className="border-b border-white/[0.08] px-3 py-2.5">
                      <Pill status={p.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-faint">
            Quote the reference above if you write to us.
          </p>
        </section>
      ) : null}
    </main>
  )
}
