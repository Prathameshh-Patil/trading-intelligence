'use client'

/**
 * The account page -- where the key lands, and everything around it.
 *
 * Four stops: signed up → awaiting approval → approved → activated in the
 * app. The first two are the account's status, the third is the key, and the
 * fourth is the desktop app's own report (`/keys/mine/activation`), so the
 * last step only lights up once the app has really run.
 *
 * It is live. The user's event stream says when an approval, a rejection, a
 * rotation or a reply lands; this page then re-fetches, so what it shows is
 * the server's answer and not a reconstruction. If the stream is down it
 * polls instead -- slower, same truth.
 *
 * The behaviour worth keeping from S5 exactly: **a 404 on `/keys/mine` is
 * "not yet", never an error.** The `reason` in its body is the account's
 * status, and that is what drives the timeline.
 */

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { ApiError, type Activation, type LicenceKey, type Payment, type SessionInfo, type Ticket } from '@vision-hub/contracts'
import {
  Banner,
  Button,
  Card,
  CheckIcon,
  ConfirmModal,
  CopyField,
  PageHeader,
  Pill,
  Spinner,
  formatDateTime,
  timeAgo,
  useToast,
} from '@vision-hub/ui'

import { PaymentProof } from '@/components/pages/PaymentProof'
import { ACCOUNT_STEPS, CONTACT } from '@/content/site'
import { api } from '@/lib/api'
import { useLive, useLiveStatus } from '@/lib/live'
import { useSession } from '@/lib/session'

// The installers' home. Unset until the first release exists, and the paragraph
// below points only at the onboarding call.
const DOWNLOAD_URL = process.env.NEXT_PUBLIC_DOWNLOAD_URL

/** Polling cadence when the stream is not open. */
const POLL_MS = 15_000

type StepState = 'done' | 'current' | 'todo' | 'failed'

export default function AccountPage() {
  const { user, ready } = useSession()
  const stream = useLiveStatus()
  const toast = useToast()

  const [key, setKey] = useState<LicenceKey | null>(null)
  const [activation, setActivation] = useState<Activation | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [rotating, setRotating] = useState(false)
  const [confirmRotate, setConfirmRotate] = useState(false)

  const loadKey = useCallback(async () => {
    try {
      setKey(await api.keysMine())
    } catch (err) {
      // 404 is the documented "not yet" and is not shown to anyone.
      if (err instanceof ApiError && err.status === 404) setKey(null)
    }
    api.activation().then(setActivation).catch(() => {})
  }, [])

  const loadRest = useCallback(() => {
    api.myPayments().then(setPayments).catch(() => setPayments([]))
    api.myTickets().then(setTickets).catch(() => setTickets([]))
    api.sessions().then(setSessions).catch(() => setSessions([]))
  }, [])

  const loadAll = useCallback(async () => {
    await Promise.all([loadKey(), api.refreshUser().catch(() => null)])
    loadRest()
  }, [loadKey, loadRest])

  useEffect(() => {
    if (!user) return
    void loadAll()
  }, [user?.id, loadAll]) // eslint-disable-line react-hooks/exhaustive-deps

  // The stream tells us *when*; the REST resource is still the answer.
  useLive(['user.approved', 'user.rejected', 'user.suspended', 'user.reinstated', 'key.rotated', 'key.revoked', 'key.activated'], (e) => {
    void loadAll()
    if (e.type === 'key.activated') {
      toast({ kind: 'success', title: 'Activated', body: 'The desktop app has validated your key.' })
    }
    if (e.type === 'user.approved') {
      toast({ kind: 'success', title: 'Approved', body: 'Your licence key is ready below.' })
    }
    if (e.type === 'user.rejected') {
      toast({ kind: 'error', title: 'Not approved', body: 'See the note on this page.' })
    }
  })
  useLive(['ticket.replied', 'ticket.closed'], () => {
    loadRest()
    toast({ kind: 'info', title: 'Support replied', body: 'Your ticket has a new message.' })
  })

  // Polling fallback: only while the stream is not open, and only until the
  // key has arrived and been used -- after that there is nothing to wait for.
  useEffect(() => {
    if (!user || stream === 'open') return
    if (key && activation?.activated) return
    const t = window.setInterval(() => void loadAll(), POLL_MS)
    return () => window.clearInterval(t)
  }, [user, stream, key, activation?.activated, loadAll])

  if (!ready) {
    return (
      <main className="mx-auto max-w-[860px] px-6 py-16">
        <Spinner label="Loading…" />
      </main>
    )
  }

  if (!user) {
    return (
      <main className="mx-auto max-w-[860px] px-6 py-16">
        <PageHeader
          title="Sign in to see your account"
          lede="Your licence key, your payments, your tickets and your sessions live behind this."
        />
        <div className="flex gap-3">
          <Link href="/login" className="text-violet-lift">Sign in →</Link>
          <Link href="/signup" className="text-dim">Create an account</Link>
        </div>
      </main>
    )
  }

  const status = user.status
  const steps = stepStates(status, key !== null, activation?.activated ?? false)
  const rejected = status === 'rejected'
  const suspended = status === 'suspended'

  return (
    <main className="mx-auto max-w-[860px] px-6 py-16">
      <PageHeader
        eyebrow="YOUR ACCOUNT"
        title={
          suspended
            ? 'Your account is suspended'
            : rejected
              ? 'We could not approve this account'
              : key
                ? 'Your key is ready'
                : 'Your account is with a person'
        }
        lede={<span className="num">{user.email}</span>}
      />

      {/* -- the timeline -------------------------------------------------- */}
      <ol className="surface mb-8 grid gap-0 rounded-2xl p-2 sm:grid-cols-4">
        {ACCOUNT_STEPS.map((step, i) => {
          const state = steps[i]
          return (
            <li key={step.id} className="relative flex gap-3 rounded-xl p-4 sm:flex-col sm:gap-2">
              <StepDot state={state} n={i + 1} />
              <div>
                <p
                  className={`text-[14px] font-semibold ${
                    state === 'todo' ? 'text-faint' : state === 'failed' ? 'text-ask' : 'text-ink'
                  }`}
                >
                  {step.title}
                </p>
                <p className="mt-0.5 text-[12.5px] leading-snug text-faint">{stepBody(step.id, state, activation)}</p>
              </div>
            </li>
          )
        })}
      </ol>

      {/* -- status ---------------------------------------------------------- */}
      {suspended ? (
        <Banner kind="error">
          <strong>Suspended.</strong> The key no longer validates and the app will show its licence
          screen. If you think this is a mistake, <Link href="/support" className="underline">raise a ticket</Link>{' '}
          and one of us will look the same day.
        </Banner>
      ) : rejected ? (
        <Banner kind="error">
          <strong>Not approved.</strong> Nothing has been charged and nothing is held against you —{' '}
          <Link href="/support" className="underline">raise a ticket</Link> if you would like to talk it
          through, and quote this page.
        </Banner>
      ) : key ? (
        <>
          <Banner kind="success">
            Approved. Paste this into the desktop app on its <strong>Licence</strong> screen — the
            app validates it and unlocks.
          </Banner>
          <CopyField label="Licence key" value={key.key} />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-sm text-faint">
            <span>
              Tier <Pill status={key.tier} /> · issued{' '}
              <span className="num">{formatDateTime(key.created_at)}</span>
              {activation?.last_validated_at ? (
                <>
                  {' '}· last checked by the app{' '}
                  <span className="num">{timeAgo(activation.last_validated_at)}</span>
                </>
              ) : null}
            </span>
            <Button kind="secondary" size="sm" onClick={() => setConfirmRotate(true)} loading={rotating}>
              Rotate key
            </Button>
          </div>
          <p className="mt-6 text-dim">
            Next: install the app, connect your own feed, and book the onboarding call. We do one
            with every subscriber, and it is where install problems go to die.{' '}
            {DOWNLOAD_URL && (
              <>
                <a href={DOWNLOAD_URL} className="text-violet-lift" target="_blank" rel="noreferrer">
                  Download the app →
                </a>{' '}
              </>
            )}
            <Link href="/contact" className="text-violet-lift">Book the call →</Link>
          </p>
        </>
      ) : (
        <Banner kind="info">
          <strong>It is with one of us now.</strong> We read every signup by hand — usually within a
          few hours, always {CONTACT.responseTarget}. You do not need to keep this page open: the key
          appears here the moment it is issued, and it will be here when you come back.
        </Banner>
      )}

      {confirmRotate ? (
        <ConfirmModal
          title="Rotate your licence key?"
          body={
            <>
              A new key is issued and the current one stops validating immediately. The desktop
              app will show its licence screen until you paste the new one.
            </>
          }
          confirmLabel="Rotate"
          kind="danger"
          onClose={() => setConfirmRotate(false)}
          onConfirm={async () => {
            setRotating(true)
            try {
              setKey(await api.rotateMyKey())
              toast({ kind: 'success', title: 'Key rotated', body: 'Paste the new key into the app.' })
            } catch (err) {
              toast({ kind: 'error', title: 'Could not rotate', body: err instanceof Error ? err.message : undefined })
            } finally {
              setRotating(false)
              setConfirmRotate(false)
            }
          }}
        />
      ) : null}

      {/* -- payment proof --------------------------------------------------- */}
      {!rejected && !suspended ? (
        <section className="mt-12">
          <h2 className="mb-1 text-[19px] font-semibold">Optional: attach payment proof</h2>
          <p className="mb-5 max-w-[62ch] text-sm text-dim">
            Paying is not on the path to your key. When you do pay — by UPI or in USDT — attach the
            receipt here so the person approving you can see it beside your account.
          </p>
          <PaymentProof onSubmitted={loadRest} />
        </section>
      ) : null}

      {payments.length ? (
        <Card className="mt-6" title="Your payments" padded={false}>
          <div className="overflow-x-auto">
            <table className="num w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-[11px] tracking-wider text-faint uppercase">
                  {['Submitted', 'Plan', 'Rail', 'Amount', 'Reference', 'Status'].map((h) => (
                    <th key={h} className="border-b border-line px-4 py-2.5 font-semibold">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td className="border-b border-line px-4 py-2.5 whitespace-nowrap">{formatDateTime(p.created_at)}</td>
                    <td className="border-b border-line px-4 py-2.5 whitespace-nowrap">
                      {p.plan === 'core_journal' ? 'Core + Journal' : 'Core'}
                    </td>
                    <td className="border-b border-line px-4 py-2.5">{p.method.toUpperCase()}</td>
                    <td className="border-b border-line px-4 py-2.5 whitespace-nowrap">
                      {p.currency === 'usd' ? '$' : '₹'}
                      {p.amount}
                    </td>
                    <td className="border-b border-line px-4 py-2.5">{p.reference}</td>
                    <td className="border-b border-line px-4 py-2.5">
                      <Pill status={p.status} />
                      {p.status === 'rejected' && p.rejection_reason ? (
                        <span className="ml-2 font-sans text-[12px] text-faint">{p.rejection_reason}</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-4 py-3 text-[12px] text-faint">Quote the reference above if you write to us.</p>
        </Card>
      ) : null}

      {/* -- tickets --------------------------------------------------------- */}
      <section className="mt-12">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[19px] font-semibold">Your tickets</h2>
          <Link href="/support" className="text-sm text-violet-lift">Raise one →</Link>
        </div>
        {tickets.length === 0 ? (
          <p className="text-sm text-faint">Nothing yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {tickets.map((t) => (
              <li key={t.id} className="surface rounded-2xl p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <code className="num text-[13px]">{t.ref}</code>
                  <strong className="text-[15px]">{t.subject}</strong>
                  <Pill status={t.status} />
                </div>
                <p className="num mt-1 text-[12px] text-faint">
                  {t.category} · {formatDateTime(t.created_at)}
                </p>
                <p className="mt-2 text-[14px] text-dim">{t.body}</p>
                {t.replies.map((r) => (
                  <div key={r.id} className={`mt-3 border-l-2 pl-4 ${r.from_staff ? 'border-violet' : 'border-line-hi'}`}>
                    <span className="num text-[11px] text-faint">
                      {r.from_staff ? 'Support' : 'You'} · {formatDateTime(r.created_at)}
                    </span>
                    <p className="text-[14px] text-ink">{r.body}</p>
                  </div>
                ))}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* -- sessions -------------------------------------------------------- */}
      <section className="mt-12">
        <h2 className="mb-1 text-[19px] font-semibold">Your sessions</h2>
        <p className="mb-4 text-sm text-dim">
          Every browser that is signed in. End one and it is signed out on its next request.
        </p>
        <Card padded={false}>
          <ul className="divide-y divide-line">
            {sessions.map((s) => (
              <li key={s.family_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px]">
                    {describeAgent(s.user_agent)}
                    {s.current ? <span className="ml-2 text-[11px] font-bold tracking-wide text-bid uppercase">This browser</span> : null}
                  </p>
                  <p className="num text-[12px] text-faint">
                    Signed in {timeAgo(s.created_at)} · last used {timeAgo(s.last_used_at)}
                    {s.ip ? ` · ${s.ip}` : ''}
                  </p>
                </div>
                {!s.current ? (
                  <Button
                    kind="ghost"
                    size="sm"
                    onClick={async () => {
                      await api.endSession(s.family_id).catch(() => {})
                      api.sessions().then(setSessions).catch(() => {})
                    }}
                  >
                    End session
                  </Button>
                ) : null}
              </li>
            ))}
            {sessions.length === 0 ? <li className="px-4 py-3 text-sm text-faint">Loading…</li> : null}
          </ul>
          <div className="border-t border-line px-4 py-3">
            <Button kind="danger" size="sm" onClick={() => api.logoutAll()}>
              Sign out everywhere
            </Button>
          </div>
        </Card>
      </section>
    </main>
  )
}

/* ---------------------------------------------------------------- helpers */

function stepStates(status: string, hasKey: boolean, activated: boolean): StepState[] {
  if (status === 'rejected') return ['done', 'failed', 'todo', 'todo']
  if (status === 'suspended') return ['done', 'done', 'failed', 'todo']
  if (status === 'pending') return ['done', 'current', 'todo', 'todo']
  // approved
  if (!hasKey) return ['done', 'done', 'current', 'todo']
  if (!activated) return ['done', 'done', 'done', 'current']
  return ['done', 'done', 'done', 'done']
}

function stepBody(id: (typeof ACCOUNT_STEPS)[number]['id'], state: StepState, activation: Activation | null): string {
  const step = ACCOUNT_STEPS.find((s) => s.id === id)!
  if (id === 'pending' && state === 'failed') return 'Not approved. The note on this page says why.'
  if (id === 'approved' && state === 'failed') return 'Suspended. The key no longer validates.'
  if (id === 'activated' && state === 'done' && activation?.last_validated_at) {
    return `Last checked ${timeAgo(activation.last_validated_at)}.`
  }
  return step.body
}

function StepDot({ state, n }: { state: StepState; n: number }) {
  const cls =
    state === 'done'
      ? 'grad text-white'
      : state === 'current'
        ? 'border border-violet/60 bg-violet/15 text-violet-lift live-dot'
        : state === 'failed'
          ? 'border border-ask/50 bg-ask/10 text-ask'
          : 'border border-line text-faint'
  return (
    <span className={`num grid h-7 w-7 shrink-0 place-items-center rounded-full text-[12px] font-bold ${cls}`}>
      {state === 'done' ? <CheckIcon size={14} /> : state === 'failed' ? '×' : n}
    </span>
  )
}

function describeAgent(ua: string | null): string {
  if (!ua) return 'Unknown browser'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /OPR\//.test(ua)
      ? 'Opera'
      : /Chrome\//.test(ua)
        ? 'Chrome'
        : /Safari\//.test(ua)
          ? 'Safari'
          : /Firefox\//.test(ua)
            ? 'Firefox'
            : 'Browser'
  const os = /Mac OS X/.test(ua)
    ? 'macOS'
    : /Windows/.test(ua)
      ? 'Windows'
      : /Android/.test(ua)
        ? 'Android'
        : /iPhone|iPad/.test(ua)
          ? 'iOS'
          : /Linux/.test(ua)
            ? 'Linux'
            : ''
  return os ? `${browser} on ${os}` : browser
}
