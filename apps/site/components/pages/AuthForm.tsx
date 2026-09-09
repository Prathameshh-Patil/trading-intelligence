'use client'

/** Login and signup: one form, two modes — they differ by a verb and a hint. */

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { Banner, Button, Field } from '../ui'
import { USING_MOCK } from '@/lib/api'
import { DEV_ADMIN, DEV_USER } from '@/lib/mockApi'
import { useSession } from '@/lib/session'

export function AuthForm({ mode }: { mode: 'login' | 'signup' }) {
  const { signIn, signUp } = useSession()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const isSignup = mode === 'signup'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const me = isSignup ? await signUp(email, password) : await signIn(email, password)
      // An admin is here to review the site or the queue; a buyer is here to get
      // back to their key. Send each where they were actually going.
      router.push(me.role === 'admin' ? '/admin' : '/key')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-[520px] px-6 py-16">
      <h1 className="mb-3 text-[2rem] font-semibold">
        {isSignup ? 'Create your account' : 'Sign in'}
      </h1>
      <p className="mb-8 text-dim">
        {isSignup
          ? 'You need an account before you pay, so the key we issue has somewhere to land.'
          : 'Your licence key, your payments and your tickets live behind this.'}
      </p>

      <form className="flex flex-col gap-5" onSubmit={submit}>
        <Field label="Email">
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>

        <Field
          label="Password"
          hint={isSignup ? 'At least 10 characters. Length beats symbols.' : undefined}
        >
          <input
            type="password"
            required
            minLength={isSignup ? 10 : undefined}
            autoComplete={isSignup ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>

        {error ? <Banner kind="error">{error}</Banner> : null}

        <Button type="submit" disabled={busy}>
          {busy ? 'Working…' : isSignup ? 'Create account' : 'Sign in'}
        </Button>
      </form>

      <p className="mt-6 text-[15px] text-dim">
        {isSignup ? (
          <>
            Already have an account?{' '}
            <Link href="/login" className="text-violet-lift">Sign in</Link>.
          </>
        ) : (
          <>
            No account yet? <Link href="/signup" className="text-violet-lift">Create one</Link>.
          </>
        )}
      </p>

      {USING_MOCK ? (
        <Banner kind="warn">
          <strong>Mock data layer.</strong> No server is running, so this signs you in against your
          own browser storage. Two preview accounts exist only in this mode and are not credentials
          for anything real: <code>{DEV_ADMIN.email}</code> / <code>{DEV_ADMIN.password}</code>{' '}
          (admin — also opens the payment queue) and <code>{DEV_USER.email}</code> /{' '}
          <code>{DEV_USER.password}</code> (a plain account — past the release gate, nothing more).
        </Banner>
      ) : null}
    </main>
  )
}
