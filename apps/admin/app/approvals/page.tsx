'use client'

/**
 * The queue. New sign-ups appear without a reload; approve and reject are
 * modals, not prompts; the minted key is shown once, here.
 */

import { useCallback, useEffect, useState } from 'react'
import type { ApproveResponse, Payment, User } from '@vision-hub/contracts'
import { type ColumnDef, Button, ConfirmModal, DataTable, PageHeader, Pill, timeAgo, useToast } from '@vision-hub/ui'

import { KeyReveal } from '@/components/KeyReveal'
import { ProofModal } from '@/components/Proof'
import { RequireAdmin } from '@/components/RequireAdmin'
import { UserDrawer } from '@/components/UserDrawer'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

export default function ApprovalsPage() {
  return (
    <RequireAdmin>
      <Approvals />
    </RequireAdmin>
  )
}

function Approvals() {
  const toast = useToast()
  const [rows, setRows] = useState<User[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(true)
  const [flash, setFlash] = useState<number | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [confirm, setConfirm] = useState<{ kind: 'approve' | 'reject'; user: User } | null>(null)
  const [reveal, setReveal] = useState<ApproveResponse | null>(null)
  const [proof, setProof] = useState<Payment | null>(null)

  const load = useCallback(async () => {
    try {
      const [u, p] = await Promise.all([api.admin.users({ status: 'pending' }), api.admin.payments()])
      setRows(u)
      setPayments(p)
    } catch (e) {
      toast({ kind: 'error', title: 'Could not load the queue', body: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => void load(), [load])
  useLive(['user.signed_up', 'user.approved', 'user.rejected', 'user.suspended', 'user.reinstated', 'payment.submitted'], (e) => {
    void load()
    if (e.type === 'user.signed_up') {
      setFlash(e.data.user_id)
      toast({ kind: 'info', title: 'New sign-up', body: e.data.email })
    }
  })

  const proofsFor = (userId: number) => payments.filter((p) => p.user_id === userId)

  const columns: ColumnDef<User, any>[] = [
    {
      accessorKey: 'email',
      header: 'Account',
      meta: { primary: true },
      cell: ({ row }) => (
        <div className="min-w-0">
          <p className="num truncate font-medium">{row.original.email}</p>
          <p className="text-[12px] text-faint md:hidden">signed up {timeAgo(row.original.created_at)}</p>
        </div>
      ),
    },
    {
      accessorKey: 'created_at',
      header: 'Signed up',
      cell: ({ getValue }) => <span className="num text-dim">{timeAgo(getValue<string>())}</span>,
    },
    {
      id: 'proof',
      header: 'Payment proof',
      enableSorting: false,
      cell: ({ row }) => {
        const ps = proofsFor(row.original.id)
        if (ps.length === 0) return <span className="text-faint">none</span>
        return (
          <div className="flex flex-wrap gap-1.5">
            {ps.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={(ev) => {
                  ev.stopPropagation()
                  setProof(p)
                }}
                className="surface num rounded-md px-2 py-0.5 text-[12px] hover:border-violet/40"
              >
                {p.method.toUpperCase()} {p.currency === 'usd' ? '$' : '₹'}
                {p.amount}
              </button>
            ))}
          </div>
        )
      },
    },
    {
      accessorKey: 'admin_note',
      header: 'Note',
      enableSorting: false,
      cell: ({ getValue }) => <span className="line-clamp-1 max-w-[28ch] text-dim">{getValue<string | null>() ?? ''}</span>,
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      meta: { primary: true, align: 'right' },
      cell: ({ row }) => (
        <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <Button kind="success" size="sm" onClick={() => setConfirm({ kind: 'approve', user: row.original })}>
            Approve
          </Button>
          <Button kind="danger" size="sm" onClick={() => setConfirm({ kind: 'reject', user: row.original })}>
            Reject
          </Button>
        </div>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        compact
        title="Approvals"
        lede={`${rows.length} account${rows.length === 1 ? '' : 's'} waiting. Approving mints the licence key and shows it on their account page immediately.`}
      />
      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        rowKey={(u) => u.id}
        flashKey={flash}
        onRowClick={(u) => setOpen(u.id)}
        searchKeys={['email']}
        searchPlaceholder="Search by email…"
        initialSort={[{ id: 'created_at', desc: false }]}
        emptyTitle="The queue is empty"
        emptyBody="New sign-ups appear here the moment they happen."
      />

      {open !== null ? <UserDrawer userId={open} onClose={() => setOpen(null)} onChanged={load} /> : null}
      {confirm?.kind === 'approve' ? (
        <ConfirmModal
          title="Approve this account?"
          body={
            <>
              A licence key is minted for <strong>{confirm.user.email}</strong> and appears on their account page immediately.
            </>
          }
          confirmLabel="Approve and issue key"
          kind="success"
          onClose={() => setConfirm(null)}
          onConfirm={async () => {
            const r = await api.admin.approve(confirm.user.id)
            setReveal(r)
            void load()
          }}
        />
      ) : null}
      {confirm?.kind === 'reject' ? (
        <ConfirmModal
          title="Reject this account?"
          body={<>The reason is shown to <strong>{confirm.user.email}</strong> verbatim, so write it for them.</>}
          confirmLabel="Reject"
          kind="danger"
          requireText="Why this account is not being approved…"
          onClose={() => setConfirm(null)}
          onConfirm={async (reason) => {
            await api.admin.reject(confirm.user.id, reason)
            toast({ kind: 'success', title: `Rejected ${confirm.user.email}` })
            void load()
          }}
        />
      ) : null}
      {reveal ? <KeyReveal result={reveal} onClose={() => setReveal(null)} /> : null}
      {proof ? <ProofModal payment={proof} onClose={() => setProof(null)} /> : null}
      <p className="mt-3 hidden text-[12px] text-faint"><Pill status="pending" /></p>
    </>
  )
}
