'use client'

/**
 * Raise a ticket, and see the ones you have raised.
 *
 * Stored rather than mailed, for one reason: someone whose key has not arrived
 * needs to be able to point at something. A reference number they can quote and
 * a status they can check is the difference between "did anyone get my email"
 * and a support conversation.
 *
 * No account needed — the person most likely to need support is the one whose
 * signup or payment just failed.
 */

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { Banner, Button, Field, PageHeader, Pill } from '@/components/ui'
import { CONTACT, TICKET_CATEGORIES } from '@/content/site'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import type { Ticket } from '@/lib/types'

export default function SupportPage() {
  const { me } = useSession()
  const [email, setEmail] = useState('')
  const [category, setCategory] = useState<string>(TICKET_CATEGORIES[0])
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [raised, setRaised] = useState<Ticket | null>(null)
  const [mine, setMine] = useState<Ticket[]>([])

  useEffect(() => {
    if (!me) return
    setEmail(me.email)
    void api.myTickets().then(setMine).catch(() => setMine([]))
  }, [me, raised])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setRaised(await api.createTicket({ email, category, subject, body }))
      setSubject('')
      setBody('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-[760px] px-6 py-16">
      <PageHeader
        eyebrow="SUPPORT"
        title="Raise a ticket"
        lede={`One of the three of us reads every one of these, ${CONTACT.responseTarget}.`}
      />

      {raised ? (
        <Banner kind="success">
          Raised as <strong className="num">{raised.ref}</strong>. We have it, and we will reply to{' '}
          <span className="num">{raised.email}</span>. Quote that reference if you follow up by
          phone.
        </Banner>
      ) : null}

      <form className="flex max-w-[560px] flex-col gap-5" onSubmit={submit}>
        <Field label="Your email" hint="Where the reply goes.">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            readOnly={Boolean(me)}
          />
        </Field>

        <Field label="What is it about">
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {TICKET_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Subject">
          <input
            required
            maxLength={140}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Paid by UPI two days ago, no key yet"
          />
        </Field>

        <Field
          label="What happened"
          hint="Transaction reference, what you expected, what you saw. Detail here is what saves the round trip."
        >
          <textarea
            required
            rows={7}
            maxLength={4000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </Field>

        {error ? <Banner kind="error">{error}</Banner> : null}

        <Button type="submit" disabled={busy}>
          {busy ? 'Sending…' : 'Raise ticket'}
        </Button>
      </form>

      {me ? (
        <section className="mt-12">
          <h2 className="mb-4 text-[19px] font-semibold">Your tickets</h2>
          {mine.length === 0 ? (
            <p className="text-sm text-faint">Nothing yet.</p>
          ) : (
            <ul className="flex flex-col gap-4">
              {mine.map((t) => (
                <li key={t.id} className="surface rounded-2xl p-5">
                  <div className="flex flex-wrap items-center gap-3">
                    <code className="num">{t.ref}</code>
                    <strong>{t.subject}</strong>
                    <Pill status={t.status} />
                  </div>
                  <p className="num mt-1 text-sm text-faint">
                    {t.category} · {new Date(t.createdAt).toLocaleString()}
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
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <p className="mt-8 text-sm text-faint">
          <Link href="/login" className="text-violet-lift">Sign in</Link> to see your past tickets and
          their replies here.
        </p>
      )}

      <p className="mt-8 text-sm text-faint">
        Urgent, or easier said out loud? <Link href="/contact" className="text-violet-lift">Call us</Link>{' '}
        — {CONTACT.hours}.
      </p>
    </main>
  )
}
