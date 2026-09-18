'use client'

import { useCallback, useEffect, useState } from 'react'
import type { AuditEntry } from '@vision-hub/contracts'
import { type ColumnDef, DataTable, PageHeader, formatDateTime, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

export default function AuditPage() {
  return (
    <RequireAdmin>
      <Audit />
    </RequireAdmin>
  )
}

const columns: ColumnDef<AuditEntry, any>[] = [
  {
    accessorKey: 'created_at',
    header: 'When',
    meta: { primary: true, width: '150px' },
    cell: ({ getValue }) => <span className="num text-dim">{formatDateTime(getValue<string>())}</span>,
  },
  { accessorKey: 'actor', header: 'Admin', cell: ({ getValue }) => <span className="num">{getValue<string | null>() ?? '—'}</span> },
  { accessorKey: 'action', header: 'Action', meta: { primary: true }, cell: ({ getValue }) => <code className="num text-violet-lift">{getValue<string>()}</code> },
  {
    id: 'target',
    header: 'Target',
    accessorFn: (a) => (a.detail?.email as string) ?? `${a.target_type} ${a.target_id}`,
    meta: { primary: true },
    cell: ({ getValue }) => <span className="num">{getValue<string>()}</span>,
  },
  {
    id: 'detail',
    header: 'Detail',
    enableSorting: false,
    accessorFn: (a) => JSON.stringify(a.detail ?? {}),
    cell: ({ row }) => {
      const d = { ...(row.original.detail ?? {}) }
      delete d.email
      const s = Object.entries(d)
        .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join(' · ')
      return <span className="line-clamp-1 max-w-[40ch] text-[13px] text-dim">{s}</span>
    },
  },
  { accessorKey: 'ip', header: 'IP', meta: { align: 'right' }, cell: ({ getValue }) => <span className="text-faint">{getValue<string | null>() ?? '—'}</span> },
]

function Audit() {
  const toast = useToast()
  const [rows, setRows] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setRows(await api.admin.audit())
    } catch (e) {
      toast({ kind: 'error', title: 'Could not load the audit log', body: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => void load(), [load])
  useLive([], () => void load())

  return (
    <>
      <PageHeader compact title="Audit log" lede="Every admin action, who took it, and from where. Append-only." />
      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        rowKey={(a) => a.id}
        searchKeys={['actor', 'action']}
        searchPlaceholder="Search admin or action…"
        initialSort={[{ id: 'created_at', desc: true }]}
        pageSize={50}
        dense
        emptyTitle="Nothing recorded yet"
      />
    </>
  )
}
