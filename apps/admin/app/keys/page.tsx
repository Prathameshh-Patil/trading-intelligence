'use client'

import { useCallback, useEffect, useState } from 'react'
import type { KeySummary } from '@vision-hub/contracts'
import { type ColumnDef, Button, ConfirmModal, DataTable, PageHeader, Pill, formatDateTime, timeAgo, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { UserDrawer } from '@/components/UserDrawer'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

export default function KeysPage() {
  return (
    <RequireAdmin>
      <Keys />
    </RequireAdmin>
  )
}

function Keys() {
  const toast = useToast()
  const [rows, setRows] = useState<KeySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [revoke, setRevoke] = useState<KeySummary | null>(null)
  const [open, setOpen] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      setRows(await api.admin.keys())
    } catch (e) {
      toast({ kind: 'error', title: 'Could not load keys', body: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => void load(), [load])
  useLive(['user.approved', 'key.rotated', 'key.revoked', 'user.rejected', 'user.suspended'], () => void load())

  const columns: ColumnDef<KeySummary, any>[] = [
    {
      accessorKey: 'prefix',
      header: 'Key',
      meta: { primary: true },
      cell: ({ row }) => (
        <span className="num">
          {row.original.prefix}
          <span className="text-faint">····························</span>
        </span>
      ),
    },
    { accessorKey: 'email', header: 'Account', cell: ({ getValue }) => <span className="num">{getValue<string>()}</span> },
    { accessorKey: 'tier', header: 'Tier', cell: ({ getValue }) => <Pill status={getValue<string>()} /> },
    { accessorKey: 'status', header: 'Status', meta: { primary: true }, cell: ({ getValue }) => <Pill status={getValue<string>()} /> },
    {
      accessorKey: 'created_at',
      header: 'Issued',
      meta: { align: 'right' },
      cell: ({ getValue }) => <span className="text-dim">{formatDateTime(getValue<string>())}</span>,
    },
    {
      accessorKey: 'last_validated_at',
      header: 'Last check-in',
      meta: { align: 'right' },
      cell: ({ getValue }) => <span className="text-dim">{timeAgo(getValue<string | null>())}</span>,
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      meta: { align: 'right', primary: true },
      cell: ({ row }) => (
        <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          {row.original.status === 'active' ? (
            <Button kind="danger" size="sm" onClick={() => setRevoke(row.original)}>
              Revoke
            </Button>
          ) : null}
        </div>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        compact
        title="Licence keys"
        lede="Every key ever issued. Only the prefix is stored in plain view here; the account page shows the owner theirs."
      />
      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        rowKey={(k) => k.id}
        onRowClick={(k) => setOpen(k.user_id)}
        searchKeys={['email', 'prefix']}
        searchPlaceholder="Search by email or prefix…"
        filters={[
          {
            id: 'status',
            label: 'Status',
            options: [
              { value: 'active', label: 'active' },
              { value: 'revoked', label: 'revoked' },
            ],
            predicate: (k, v) => k.status === v,
          },
        ]}
        initialSort={[{ id: 'created_at', desc: true }]}
        emptyTitle="No keys issued yet"
        emptyBody="Approving an account mints its key."
      />
      {revoke ? (
        <ConfirmModal
          title="Revoke this key?"
          body={
            <>
              <strong>{revoke.email}</strong>&apos;s desktop app stops working on its next check. The account stays approved;
              rotate from the account drawer to issue a replacement.
            </>
          }
          confirmLabel="Revoke"
          kind="danger"
          onClose={() => setRevoke(null)}
          onConfirm={async () => {
            await api.admin.revokeKey(revoke.id)
            toast({ kind: 'success', title: `Revoked ${revoke.prefix}…` })
            void load()
          }}
        />
      ) : null}
      {open !== null ? <UserDrawer userId={open} onClose={() => setOpen(null)} onChanged={load} /> : null}
    </>
  )
}
