'use client'

import { useCallback, useEffect, useState } from 'react'
import type { WaitlistEntry } from '@vision-hub/contracts'
import { type ColumnDef, Button, DataTable, PageHeader, formatDateTime, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

export default function WaitlistPage() {
  return (
    <RequireAdmin>
      <Waitlist />
    </RequireAdmin>
  )
}

const columns: ColumnDef<WaitlistEntry, any>[] = [
  { accessorKey: 'email', header: 'Email', meta: { primary: true }, cell: ({ getValue }) => <span className="num">{getValue<string>()}</span> },
  {
    accessorKey: 'created_at',
    header: 'Joined',
    meta: { align: 'right', primary: true },
    cell: ({ getValue }) => <span className="text-dim">{formatDateTime(getValue<string>())}</span>,
  },
]

function Waitlist() {
  const toast = useToast()
  const [rows, setRows] = useState<WaitlistEntry[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setRows(await api.admin.waitlist())
    } catch (e) {
      toast({ kind: 'error', title: 'Could not load the waitlist', body: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => void load(), [load])
  useLive(['waitlist.joined'], () => void load())

  function exportCsv() {
    const csv = ['email,joined', ...rows.map((r) => `${r.email},${r.created_at}`)].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `waitlist-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <>
      <PageHeader
        compact
        title="Waitlist"
        lede="Emails left on the holding page while the site is pre-release."
        actions={
          <Button kind="secondary" size="sm" onClick={exportCsv} disabled={rows.length === 0}>
            Export CSV
          </Button>
        }
      />
      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        rowKey={(w) => w.email}
        searchKeys={['email']}
        initialSort={[{ id: 'created_at', desc: true }]}
        emptyTitle="Nobody on the list yet"
      />
    </>
  )
}
