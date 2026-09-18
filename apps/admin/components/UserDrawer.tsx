'use client'

/**
 * One account, in full: status, key, proof, tickets, sessions, and every
 * action an admin can take on it. Opened from the users table and the queue.
 */

import { useCallback, useEffect, useState } from 'react'
import type { ApproveResponse, Payment, UserDetail } from '@vision-hub/contracts'
import {
  Button,
  ConfirmModal,
  Drawer,
  Pill,
  Spinner,
  formatDateTime,
  timeAgo,
  useToast,
} from '@vision-hub/ui'

import { api } from '@/lib/api'
import { useLive } from '@/lib/live'
import { useSession } from '@/lib/session'

import { KeyReveal } from './KeyReveal'
import { ProofModal, ProofThumb } from './Proof'

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-[13px] last:border-b-0">
      <span className="text-faint">{k}</span>
      <span className="num text-right text-ink">{v}</span>
    </div>
  )
}

export function UserDrawer({ userId, onClose, onChanged }: { userId: number; onClose: () => void; onChanged?: () => void }) {
  const { user: me } = useSession()
  const toast = useToast()
  const [u, setU] = useState<UserDetail | null>(null)
  const [confirm, setConfirm] = useState<null | 'approve' | 'reject' | 'suspend' | 'reinstate' | 'rotate' | 'revoke' | 'logout' | 'admin'>(null)
  const [reveal, setReveal] = useState<ApproveResponse | null>(null)
  const [proof, setProof] = useState<Payment | null>(null)
  const [note, setNote] = useState('')
  const [noteBusy, setNoteBusy] = useState(false)

  const load = useCallback(() => {
    api.admin
      .user(userId)
      .then((d) => {
        setU(d)
        setNote(d.admin_note ?? '')
      })
      .catch((e) => toast({ kind: 'error', title: 'Could not load account', body: e.message }))
  }, [userId, toast])

  useEffect(load, [load])
  useLive([], (e) => {
    if ('user_id' in e.data && e.data.user_id === userId) load()
  })

  async function act(fn: () => Promise<unknown>, done: string) {
    await fn()
    toast({ kind: 'success', title: done })
    load()
    onChanged?.()
  }

  if (!u) {
    return (
      <Drawer title="Account" onClose={onClose}>
        <Spinner label="Loading…" />
      </Drawer>
    )
  }

  const isSelf = me?.id === u.id

  return (
    <Drawer title={u.email} subtitle={`Account #${u.id} · signed up ${timeAgo(u.created_at)}`} onClose={onClose}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Pill status={u.status} />
        <Pill status={u.role} />
        {u.key ? <Pill status={u.key.status} /> : null}
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {u.status === 'pending' || u.status === 'rejected' ? (
          <Button kind="success" size="sm" onClick={() => setConfirm('approve')}>
            Approve &amp; issue key
          </Button>
        ) : null}
        {u.status === 'pending' ? (
          <Button kind="danger" size="sm" onClick={() => setConfirm('reject')}>
            Reject
          </Button>
        ) : null}
        {u.status === 'approved' ? (
          <Button kind="secondary" size="sm" onClick={() => setConfirm('rotate')}>
            Rotate key
          </Button>
        ) : null}
        {u.key?.status === 'active' ? (
          <Button kind="danger" size="sm" onClick={() => setConfirm('revoke')}>
            Revoke key
          </Button>
        ) : null}
        {u.status !== 'suspended' && !isSelf ? (
          <Button kind="ghost" size="sm" onClick={() => setConfirm('suspend')}>
            Suspend
          </Button>
        ) : null}
        {u.status === 'suspended' ? (
          <Button kind="secondary" size="sm" onClick={() => setConfirm('reinstate')}>
            Reinstate
          </Button>
        ) : null}
        {!isSelf ? (
          <Button kind="ghost" size="sm" onClick={() => setConfirm('logout')}>
            Sign out everywhere
          </Button>
        ) : null}
        {u.role !== 'admin' ? (
          <Button kind="ghost" size="sm" onClick={() => setConfirm('admin')}>
            Make admin
          </Button>
        ) : null}
      </div>

      <section className="surface mb-4 rounded-xl px-4 py-1">
        <Row k="Status" v={u.status} />
        <Row k="Approved" v={u.approved_at ? `${formatDateTime(u.approved_at)} by ${u.approved_by ?? '—'}` : '—'} />
        {u.rejection_reason ? <Row k="Rejected because" v={u.rejection_reason} /> : null}
        <Row k="Last sign-in" v={timeAgo(u.last_login_at)} />
        <Row k="Key" v={u.key ? `${u.key.prefix}… · ${u.key.tier}` : 'none'} />
        <Row k="Key last validated" v={timeAgo(u.key?.last_validated_at)} />
      </section>

      <section className="mb-4">
        <h3 className="mb-2 text-[12px] font-semibold tracking-wider text-faint uppercase">Internal note</h3>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Never shown to the customer."
          className="min-h-[72px]"
        />
        <div className="mt-2 flex justify-end">
          <Button
            kind="secondary"
            size="sm"
            loading={noteBusy}
            disabled={note === (u.admin_note ?? '')}
            onClick={async () => {
              setNoteBusy(true)
              try {
                await api.admin.setNote(u.id, note)
                load()
              } finally {
                setNoteBusy(false)
              }
            }}
          >
            Save note
          </Button>
        </div>
      </section>

      <section className="mb-4">
        <h3 className="mb-2 text-[12px] font-semibold tracking-wider text-faint uppercase">
          Payment proofs ({u.payments.length})
        </h3>
        {u.payments.length === 0 ? (
          <p className="text-[13px] text-faint">None attached. Approval does not need one.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {u.payments.map((p) => (
              <li key={p.id} className="surface flex items-center gap-3 rounded-xl px-3 py-2 text-[13px]">
                <ProofThumb payment={p} onOpen={() => setProof(p)} />
                <div className="min-w-0 flex-1">
                  <p className="num truncate">
                    {p.plan} · {p.method.toUpperCase()} · {p.currency === 'usd' ? '$' : '₹'}
                    {p.amount}
                  </p>
                  <p className="num truncate text-faint">
                    ref {p.reference} · {timeAgo(p.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-4">
        <h3 className="mb-2 text-[12px] font-semibold tracking-wider text-faint uppercase">Tickets ({u.tickets.length})</h3>
        {u.tickets.length === 0 ? (
          <p className="text-[13px] text-faint">No tickets.</p>
        ) : (
          <ul className="flex flex-col gap-1.5 text-[13px]">
            {u.tickets.map((t) => (
              <li key={t.id} className="flex items-center gap-2">
                <code className="num text-faint">{t.ref}</code>
                <span className="flex-1 truncate">{t.subject}</span>
                <Pill status={t.status} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-[12px] font-semibold tracking-wider text-faint uppercase">Sessions ({u.sessions.length})</h3>
        {u.sessions.length === 0 ? (
          <p className="text-[13px] text-faint">Not signed in anywhere.</p>
        ) : (
          <ul className="flex flex-col gap-1.5 text-[13px]">
            {u.sessions.map((s) => (
              <li key={s.family_id} className="surface rounded-lg px-3 py-2">
                <p className="truncate">{s.user_agent ?? 'Unknown device'}</p>
                <p className="num text-faint">
                  {s.ip ?? '—'} · started {timeAgo(s.created_at)} · last used {timeAgo(s.last_used_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {confirm === 'approve' ? (
        <ConfirmModal
          title="Approve this account?"
          body={
            <>
              A licence key is minted for <strong>{u.email}</strong> and appears on their account page immediately.
            </>
          }
          confirmLabel="Approve and issue key"
          kind="success"
          onClose={() => setConfirm(null)}
          onConfirm={async () => {
            const r = await api.admin.approve(u.id)
            setReveal(r)
            load()
            onChanged?.()
          }}
        />
      ) : null}
      {confirm === 'reject' ? (
        <ConfirmModal
          title="Reject this account?"
          body={<>The reason is shown to <strong>{u.email}</strong> verbatim, so write it for them.</>}
          confirmLabel="Reject"
          kind="danger"
          requireText="Why this account is not being approved…"
          onClose={() => setConfirm(null)}
          onConfirm={(reason) => act(() => api.admin.reject(u.id, reason), `Rejected ${u.email}`)}
        />
      ) : null}
      {confirm === 'suspend' ? (
        <ConfirmModal
          title="Suspend this account?"
          body="They are signed out everywhere, their key stops validating, and they cannot sign in until reinstated."
          confirmLabel="Suspend"
          kind="danger"
          onClose={() => setConfirm(null)}
          onConfirm={() => act(() => api.admin.suspend(u.id), `Suspended ${u.email}`)}
        />
      ) : null}
      {confirm === 'reinstate' ? (
        <ConfirmModal
          title="Reinstate this account?"
          body="Back to approved if it had a key, otherwise back to the approval queue."
          confirmLabel="Reinstate"
          onClose={() => setConfirm(null)}
          onConfirm={() => act(() => api.admin.reinstate(u.id), `Reinstated ${u.email}`)}
        />
      ) : null}
      {confirm === 'rotate' ? (
        <ConfirmModal
          title="Rotate this key?"
          body="The current key stops validating and a new one is minted. The desktop app will ask for the new key on its next check."
          confirmLabel="Rotate"
          onClose={() => setConfirm(null)}
          onConfirm={async () => {
            const r = await api.admin.rotateKey(u.id)
            setReveal(r)
            load()
            onChanged?.()
          }}
        />
      ) : null}
      {confirm === 'revoke' && u.key ? (
        <ConfirmModal
          title="Revoke this key?"
          body="The desktop app stops working on its next check. The account stays approved; rotate to issue a replacement."
          confirmLabel="Revoke"
          kind="danger"
          onClose={() => setConfirm(null)}
          onConfirm={() => act(() => api.admin.revokeKey(u.key!.id), `Revoked ${u.key!.prefix}…`)}
        />
      ) : null}
      {confirm === 'logout' ? (
        <ConfirmModal
          title="Sign this account out everywhere?"
          body="Every session ends and every access token stops working on its next request."
          confirmLabel="Sign out everywhere"
          onClose={() => setConfirm(null)}
          onConfirm={() => act(() => api.admin.logoutAll(u.id), `Signed ${u.email} out everywhere`)}
        />
      ) : null}
      {confirm === 'admin' ? (
        <ConfirmModal
          title="Make this account an administrator?"
          body="They can open this portal, approve accounts and issue keys."
          confirmLabel="Make admin"
          onClose={() => setConfirm(null)}
          onConfirm={() => act(() => api.admin.setRole(u.id, 'admin'), `${u.email} is now an admin`)}
        />
      ) : null}
      {reveal ? <KeyReveal result={reveal} onClose={() => setReveal(null)} /> : null}
      {proof ? <ProofModal payment={proof} onClose={() => setProof(null)} /> : null}
    </Drawer>
  )
}
