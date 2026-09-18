'use client'

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import type { Release, SessionInfo, User } from '@vision-hub/contracts'
import { Button, Card, Field, PageHeader, Pill, timeAgo, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'
import { useSession } from '@/lib/session'

export default function SettingsPage() {
  return (
    <RequireAdmin>
      <Settings />
    </RequireAdmin>
  )
}

function Settings() {
  const toast = useToast()
  const { user } = useSession()
  const [release, setRelease] = useState<Release | null>(null)
  const [admins, setAdmins] = useState<User[]>([])
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.release().then(setRelease).catch(() => {})
    api.admin.users().then((u) => setAdmins(u.filter((x) => x.role === 'admin'))).catch(() => {})
    api.sessions().then(setSessions).catch(() => {})
  }, [])
  useEffect(load, [load])
  useLive(['release.changed', 'user.role_changed'], load)

  async function promote(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const u = await api.admin.promote(email.trim())
      toast({ kind: 'success', title: `${u.email} is now an admin` })
      setEmail('')
      load()
    } catch (err) {
      toast({ kind: 'error', title: 'Could not promote', body: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader compact title="Settings" lede="The release switch, who else is an admin, and your own sessions." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Release">
          <p className="text-[14px] text-dim">
            The customer site is{' '}
            <strong className={release?.is_public ? 'text-bid' : 'text-warn'}>
              {release ? (release.is_public ? 'public' : 'pre-release') : '…'}
            </strong>
            .
          </p>
          <Button
            className="mt-4"
            kind={release?.is_public ? 'secondary' : 'primary'}
            size="sm"
            onClick={async () => {
              if (!release) return
              setRelease(await api.setPublic(!release.is_public))
            }}
          >
            {release?.is_public ? 'Back to pre-release' : 'Make the site public'}
          </Button>
        </Card>

        <Card title="Administrators">
          <ul className="mb-4 flex flex-col gap-1.5 text-[14px]">
            {admins.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3">
                <span className="num truncate">{a.email}</span>
                <span className="text-[12px] text-faint">{a.id === user?.id ? 'you' : `last seen ${timeAgo(a.last_login_at)}`}</span>
              </li>
            ))}
          </ul>
          <form onSubmit={promote} className="flex items-end gap-2">
            <div className="flex-1">
              <Field label="Promote by email" hint="They must have signed up first.">
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" />
              </Field>
            </div>
            <Button type="submit" size="md" kind="secondary" loading={busy} disabled={!email.trim()}>
              Make admin
            </Button>
          </form>
        </Card>

        <Card title="Your sessions" className="lg:col-span-2" actions={<Pill status={user?.role ?? 'user'} />}>
          <ul className="flex flex-col gap-2">
            {sessions.map((s) => (
              <li key={s.family_id} className="surface flex items-center justify-between gap-3 rounded-xl px-4 py-2.5 text-[13px]">
                <div className="min-w-0">
                  <p className="truncate">
                    {s.user_agent ?? 'Unknown device'} {s.current ? <span className="ml-1 text-bid">· this device</span> : null}
                  </p>
                  <p className="num text-faint">
                    {s.ip ?? '—'} · started {timeAgo(s.created_at)} · last used {timeAgo(s.last_used_at)}
                  </p>
                </div>
                {!s.current ? (
                  <Button
                    kind="ghost"
                    size="sm"
                    onClick={async () => {
                      await api.endSession(s.family_id)
                      load()
                    }}
                  >
                    End
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <Button kind="danger" size="sm" onClick={() => api.logoutAll()}>
              Sign out everywhere
            </Button>
          </div>
        </Card>
      </div>
    </>
  )
}
