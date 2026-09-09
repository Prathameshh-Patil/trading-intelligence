'use client'

/**
 * What a stranger sees before release.
 *
 * Claims nothing, prices nothing, promises nothing. Every sentence is about what
 * the tool *shows* and who it is *for* — never what it will make you — because
 * the internal measurement of whether this data predicts price came back flat
 * and is recorded honestly. There is no product claim here to walk back on a
 * call later.
 */

import Link from 'next/link'
import { useState } from 'react'

import { api } from '@/lib/api'
import { Banner, buttonClass } from './ui'
import { BRAND, CONTACT, HOLDING } from '@/content/site'

export function Holding() {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setState('sending')
    try {
      await api.joinWaitlist(email)
      setState('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setState('error')
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-6 py-16">
      <div className="grid-bg pointer-events-none absolute inset-0 -z-10" aria-hidden />

      <div className="flex max-w-[660px] flex-col items-center gap-5 text-center">
        <div className="flex items-center gap-2.5 font-bold text-ink">
          <span className="grid h-7 w-7 place-items-center rounded-lg grad text-sm font-extrabold text-black">
            T
          </span>
          {BRAND.name}
        </div>

        <span className="inline-flex items-center gap-2 text-[11px] font-bold tracking-[0.18em] text-violet-lift uppercase">
          <span className="h-1.5 w-1.5 rounded-full grad" />
          {HOLDING.badge}
        </span>

        <h1 className="text-[clamp(2.1rem,6vw,3.6rem)] font-semibold">
          {HOLDING.title[0]}
          <br />
          <span className="text-violet-lift">{HOLDING.title[1]}</span>
        </h1>

        {HOLDING.body.map((paragraph) => (
          <p key={paragraph} className="text-[17px] leading-relaxed text-dim">
            {paragraph}
          </p>
        ))}

        {state === 'done' ? (
          <Banner kind="success">
            You are on the list. We will write to you once — when it is ready — and not before.
          </Banner>
        ) : (
          <form className="mt-2 flex w-full max-w-[460px] flex-wrap gap-2.5" onSubmit={submit}>
            <input
              type="email"
              required
              value={email}
              placeholder="you@example.com"
              aria-label="Email address"
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1"
            />
            <button className={buttonClass.primary} type="submit" disabled={state === 'sending'}>
              {state === 'sending' ? 'Adding…' : 'Tell me when it ships'}
            </button>
          </form>
        )}

        {state === 'error' ? <Banner kind="error">{error}</Banner> : null}

        <p className="text-sm text-faint">
          Questions before then —{' '}
          <a className="text-violet-lift" href={`mailto:${CONTACT.email}`}>
            {CONTACT.email}
          </a>
          , or <Link href="/contact" className="text-violet-lift">the other ways to reach us</Link>.
        </p>

        <p className="text-sm text-faint">
          Building this with us? <Link href="/login" className="text-violet-lift">Sign in</Link>.
        </p>
      </div>
    </main>
  )
}
