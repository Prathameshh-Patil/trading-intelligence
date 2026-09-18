'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '@vision-hub/contracts'
import { Banner, Button, Field, Mark } from '@vision-hub/ui'

import { api } from '@/lib/api'
import { useSession } from '@/lib/session'

export default function LoginPage() {
  const { user, ready } = useSession()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (ready && user?.role === 'admin') router.replace('/')
  }, [ready, user, router])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const me = await api.login(email, password)
      router.replace(me.role === 'admin' ? '/' : '/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in.')
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <form onSubmit={submit} className="surface w-full max-w-[380px] rounded-2xl p-7">
        <div className="mb-6 flex items-center gap-3">
          <Mark size={34} />
          <div>
            <p className="text-[16px] font-semibold">Vision Hub</p>
            <p className="text-[12px] tracking-wider text-faint uppercase">Admin portal</p>
          </div>
        </div>
        {error ? <Banner kind="error">{error}</Banner> : null}
        <div className="flex flex-col gap-4">
          <Field label="Email">
            <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password">
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button type="submit" loading={busy} className="mt-2 w-full">
            Sign in
          </Button>
        </div>
        <p className="mt-5 text-[12px] text-faint">
          Administrator accounts only. Sessions last 30 days and can be ended from any device.
        </p>
      </form>
    </main>
  )
}
