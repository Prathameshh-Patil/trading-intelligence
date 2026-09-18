'use client'

import { useCallback, useEffect, useState } from 'react'
import type { User } from '@vision-hub/contracts'
import { type ColumnDef, DataTable, PageHeader, Pill, timeAgo, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { UserDrawer } from '@/components/UserDrawer'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

export default function UsersPage() {
  return (
    <RequireAdmin>
      <Users />
    </RequireAdmin>
  )
}

const columns: ColumnDef<User, any>[] = [
  {
    accessorKey: 'email',
    header: 'Account',
    meta: { primary: true },
    cell: ({ row }) => (
      <div className="min-w-0">
        <p className="num truncate font-medium">{row.original.email}</p>
        <p className="text-[12px] text-faint md:hidden">
          <Pill status={row.original.status} />
        </p>
      </div>
    ),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ getValue }) => <Pill status={getValue<string>()} />,
  },
  {
    accessorKey: 'role',
    header: 'Role',
    cell: ({ getValue }) => <span className={getValue<string>() === 'admin' ? 'text-violet-lift' : 'text-dim'}>{getValue<string>()}</span>,
  },
  {
    id: 'key',
    header: 'Key',
    accessorFn: (u) => u.key?.prefix ?? '',
    cell: ({ row }) =>
      row.original.key ? (
        <span className="num text-dim">
          {row.original.key.prefix}… <Pill status={row.original.key.status} className="ml-1" />
        </span>
      ) : (
        <span className="text-faint">—</span>
      ),
  },
  {
    id: 'validated',
    header: 'Last check-in',
    accessorFn: (u) => u.key?.last_validated_at ?? '',
    meta: { align: 'right' },
    cell: ({ row }) => <span className="text-dim">{timeAgo(row.original.key?.last_validated_at)}</span>,
  },
  {
    accessorKey: 'created_at',
    header: 'Signed up',
    meta: { align: 'right' },
    cell: ({ getValue }) => <span className="text-dim">{timeAgo(getValue<string>())}</span>,
  },
  {
    accessorKey: 'open_tickets',
    header: 'Open tickets',
    meta: { align: 'right' },
    cell: ({ getValue }) => (getValue<number>() ? <span className="text-warn">{getValue<number>()}</span> : <span className="text-faint">0</span>),
  },
]

function Users() {
  const toast = useToast()
  const [rows, setRows] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState<number | null>(null)
  const [flash, setFlash] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      setRows(await api.admin.users())
    } catch (e) {
      toast({ kind: 'error', title: 'Could not load users', body: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => void load(), [load])
  useLive([], (e) => {
    if ('user_id' in e.data && typeof e.data.user_id === 'number') setFlash(e.data.user_id)
    void load()
  })

  return (
    <>
      <PageHeader compact title="Users" lede="Every account, whatever its state. Click a row for the full picture." />
      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        rowKey={(u) => u.id}
        flashKey={flash}
        onRowClick={(u) => setOpen(u.id)}
        searchKeys={['email']}
        searchPlaceholder="Search by email…"
        filters={[
          {
            id: 'status',
            label: 'Status',
            options: ['pending', 'approved', 'rejected', 'suspended'].map((s) => ({ value: s, label: s })),
            predicate: (u, v) => u.status === v,
          },
          {
            id: 'role',
            label: 'Role',
            options: [
              { value: 'admin', label: 'admin' },
              { value: 'user', label: 'user' },
            ],
            predicate: (u, v) => u.role === v,
          },
        ]}
        initialSort={[{ id: 'created_at', desc: true }]}
        emptyTitle="No accounts yet"
      />
      {open !== null ? <UserDrawer userId={open} onClose={() => setOpen(null)} onChanged={load} /> : null}
    </>
  )
}
