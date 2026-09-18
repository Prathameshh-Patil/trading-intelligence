'use client'

import { useCallback, useEffect, useState } from 'react'
import type { Ticket } from '@vision-hub/contracts'
import { type ColumnDef, Button, DataTable, Drawer, PageHeader, Pill, formatDateTime, timeAgo, useToast } from '@vision-hub/ui'

import { RequireAdmin } from '@/components/RequireAdmin'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'

export default function TicketsPage() {
  return (
    <RequireAdmin>
      <Tickets />
    </RequireAdmin>
  )
}

const columns: ColumnDef<Ticket, any>[] = [
  { accessorKey: 'ref', header: 'Ref', meta: { primary: true, width: '90px' }, cell: ({ getValue }) => <code className="num">{getValue<string>()}</code> },
  {
    accessorKey: 'subject',
    header: 'Subject',
    meta: { primary: true },
    cell: ({ row }) => (
      <div className="min-w-0">
        <p className="truncate font-medium">{row.original.subject}</p>
        <p className="num truncate text-[12px] text-faint">{row.original.email}</p>
      </div>
    ),
  },
  { accessorKey: 'category', header: 'Category', cell: ({ getValue }) => <span className="text-dim">{getValue<string>()}</span> },
  { accessorKey: 'status', header: 'Status', meta: { primary: true }, cell: ({ getValue }) => <Pill status={getValue<string>()} /> },
  {
    accessorKey: 'created_at',
    header: 'Opened',
    meta: { align: 'right' },
    cell: ({ getValue }) => <span className="text-dim">{timeAgo(getValue<string>())}</span>,
  },
]

function Tickets() {
  const toast = useToast()
  const [rows, setRows] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState<number | null>(null)
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      setRows(await api.admin.tickets())
    } catch (e) {
      toast({ kind: 'error', title: 'Could not load tickets', body: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => void load(), [load])
  useLive(['ticket.created', 'ticket.replied', 'ticket.closed'], (e) => {
    if (e.type === 'ticket.created') {
      setFlash(e.data.ticket_id)
      toast({ kind: 'info', title: `New ticket ${e.data.ref}`, body: e.data.email })
    }
    void load()
  })

  const ticket = rows.find((t) => t.id === openId) ?? null

  return (
    <>
      <PageHeader compact title="Tickets" lede="Support requests from the site. Reply here; the customer sees it on their account page." />
      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        rowKey={(t) => t.id}
        flashKey={flash}
        onRowClick={(t) => setOpenId(t.id)}
        searchKeys={['ref', 'email', 'subject']}
        searchPlaceholder="Search ref, email or subject…"
        filters={[
          {
            id: 'status',
            label: 'Status',
            options: ['open', 'answered', 'closed'].map((s) => ({ value: s, label: s })),
            predicate: (t, v) => t.status === v,
          },
        ]}
        initialSort={[{ id: 'created_at', desc: true }]}
        emptyTitle="No tickets"
      />

      {ticket ? (
        <Drawer
          title={
            <>
              <code className="num mr-2 text-faint">{ticket.ref}</code>
              {ticket.subject}
            </>
          }
          subtitle={`${ticket.email} · ${ticket.category} · opened ${formatDateTime(ticket.created_at)}`}
          onClose={() => setOpenId(null)}
        >
          <div className="mb-3 flex items-center gap-2">
            <Pill status={ticket.status} />
            {ticket.status !== 'closed' ? (
              <Button
                kind="ghost"
                size="sm"
                onClick={async () => {
                  await api.admin.closeTicket(ticket.id)
                  toast({ kind: 'success', title: `Closed ${ticket.ref}` })
                  void load()
                }}
              >
                Close ticket
              </Button>
            ) : null}
          </div>

          <div className="flex flex-col gap-3">
            <div className="surface rounded-xl px-4 py-3 text-[14px]">
              <p className="num mb-1 text-[12px] text-faint">{ticket.email} · {formatDateTime(ticket.created_at)}</p>
              <p className="whitespace-pre-wrap">{ticket.body}</p>
            </div>
            {ticket.replies.map((r) => (
              <div
                key={r.id}
                className={`rounded-xl px-4 py-3 text-[14px] ${r.from_staff ? 'ml-6 border border-violet/25 bg-violet/10' : 'surface'}`}
              >
                <p className="num mb-1 text-[12px] text-faint">
                  {r.from_staff ? 'Support' : ticket.email} · {formatDateTime(r.created_at)}
                </p>
                <p className="whitespace-pre-wrap">{r.body}</p>
              </div>
            ))}
          </div>

          {ticket.status !== 'closed' ? (
            <form
              className="mt-4"
              onSubmit={async (e) => {
                e.preventDefault()
                if (!reply.trim()) return
                setBusy(true)
                try {
                  await api.admin.reply(ticket.id, reply.trim())
                  setReply('')
                  toast({ kind: 'success', title: 'Reply sent' })
                  void load()
                } catch (err) {
                  toast({ kind: 'error', title: 'Reply failed', body: (err as Error).message })
                } finally {
                  setBusy(false)
                }
              }}
            >
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder="Write the reply the customer will read…"
                className="min-h-[110px]"
              />
              <div className="mt-2 flex justify-end">
                <Button type="submit" size="sm" loading={busy} disabled={!reply.trim()}>
                  Send reply
                </Button>
              </div>
            </form>
          ) : null}
        </Drawer>
      ) : null}
    </>
  )
}
