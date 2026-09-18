'use client'

/** Login and signup: one form, two modes — they differ by a verb and a hint. */

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { Banner, Button, Field } from '@vision-hub/ui'

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
      if (isSignup) await signUp(email, password)
      else await signIn(email, password)
      // Everyone lands on the account page: it is where the key arrives, and
      // an admin gets the portal link from the rail once they are there.
      router.push('/account')
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
          ? 'One of us approves every account by hand. Your licence key lands here the moment that happens.'
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

        <Button type="submit" size="lg" loading={busy}>
          {isSignup ? 'Create account' : 'Sign in'}
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

    </main>
  )
}
