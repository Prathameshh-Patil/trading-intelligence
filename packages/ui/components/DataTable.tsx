'use client'

/**
 * The data table: header row on top, sortable columns, a search box, optional
 * filter selects, pagination, and honest loading / empty states.
 *
 * Headless `@tanstack/react-table` underneath so sorting and filtering are
 * correct and this file only draws. Numbers and dates right-align through the
 * column's `meta.align`; the row-level `flashKey` lets a page highlight the
 * row an event just touched.
 */

import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type RowData,
  type SortingState,
} from '@tanstack/react-table'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

// Re-exported so pages type their columns without depending on the table
// library themselves.
export type { ColumnDef } from '@tanstack/react-table'

import { ChevronDown, ChevronUp, SearchIcon } from './icons'
import { EmptyState, Spinner } from './primitives'

declare module '@tanstack/react-table' {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    align?: 'left' | 'right' | 'center'
    width?: string
    /** Keep this column visible on narrow screens. */
    primary?: boolean
  }
}

export type Filter<T> = {
  id: string
  label: string
  options: { value: string; label: string }[]
  predicate: (row: T, value: string) => boolean
}

export function DataTable<T>({
  data,
  columns,
  loading = false,
  emptyTitle = 'Nothing here yet',
  emptyBody,
  searchPlaceholder = 'Search…',
  searchKeys,
  filters = [],
  initialSort = [],
  pageSize = 25,
  onRowClick,
  rowKey,
  flashKey,
  toolbar,
  dense = false,
}: {
  data: T[]
  columns: ColumnDef<T, any>[]
  loading?: boolean
  emptyTitle?: string
  emptyBody?: ReactNode
  searchPlaceholder?: string
  /** Fields the search box matches against. Omit to hide the search box. */
  searchKeys?: (keyof T)[]
  filters?: Filter<T>[]
  initialSort?: SortingState
  pageSize?: number
  onRowClick?: (row: T) => void
  rowKey: (row: T) => string | number
  /** A row key to flash once, e.g. the row an event just changed. */
  flashKey?: string | number | null
  toolbar?: ReactNode
  dense?: boolean
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSort)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<Record<string, string>>({})

  const rows = useMemo(() => {
    let out = data
    const q = query.trim().toLowerCase()
    if (q && searchKeys?.length) {
      out = out.filter((row) => searchKeys.some((k) => String(row[k] ?? '').toLowerCase().includes(q)))
    }
    for (const f of filters) {
      const v = active[f.id]
      if (v) out = out.filter((row) => f.predicate(row, v))
    }
    return out
  }, [data, query, searchKeys, filters, active])

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  })

  // Reset to page 1 when the filtered set changes under us.
  useEffect(() => table.setPageIndex(0), [rows, table])

  const pageCount = table.getPageCount()
  const { pageIndex } = table.getState().pagination
  const cellPad = dense ? 'px-3 py-2' : 'px-4 py-3'

  return (
    <div className="surface overflow-hidden rounded-2xl">
      {(searchKeys?.length || filters.length || toolbar) && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5">
          {searchKeys?.length ? (
            <label className="relative min-w-[200px] flex-1">
              <SearchIcon size={15} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="!py-2 !pl-9 text-[14px]"
              />
            </label>
          ) : null}
          {filters.map((f) => (
            <select
              key={f.id}
              value={active[f.id] ?? ''}
              onChange={(e) => setActive((a) => ({ ...a, [f.id]: e.target.value }))}
              aria-label={f.label}
              className="!w-auto !py-2 text-[13px]"
            >
              <option value="">{f.label}: all</option>
              {f.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ))}
          {toolbar ? <div className="ml-auto flex items-center gap-2">{toolbar}</div> : null}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead className="sticky top-0 z-10 bg-panel">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const meta = h.column.columnDef.meta
                  const align = meta?.align ?? 'left'
                  const sortable = h.column.getCanSort()
                  const dir = h.column.getIsSorted()
                  return (
                    <th
                      key={h.id}
                      style={{ width: meta?.width }}
                      className={`${cellPad} border-b border-line text-[11px] font-semibold tracking-[0.08em] text-faint uppercase select-none ${
                        align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
                      } ${meta?.primary ? '' : 'hidden md:table-cell'}`}
                    >
                      {h.isPlaceholder ? null : sortable ? (
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className={`inline-flex items-center gap-1 hover:text-ink ${dir ? 'text-ink' : ''}`}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {dir === 'asc' ? <ChevronUp size={12} /> : dir === 'desc' ? <ChevronDown size={12} /> : null}
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading && data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center">
                  <Spinner label="Loading…" />
                </td>
              </tr>
            ) : table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>
                  <EmptyState title={rows.length === 0 && data.length > 0 ? 'No matches' : emptyTitle} body={emptyBody} />
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => {
                const key = rowKey(row.original)
                return (
                  <tr
                    key={key}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                    className={`border-b border-line last:border-b-0 ${onRowClick ? 'cursor-pointer hover:bg-white/[0.035]' : ''} ${
                      flashKey !== undefined && flashKey !== null && flashKey === key ? 'vh-flash' : ''
                    }`}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const meta = cell.column.columnDef.meta
                      const align = meta?.align ?? 'left'
                      return (
                        <td
                          key={cell.id}
                          className={`${cellPad} align-middle ${
                            align === 'right' ? 'num text-right' : align === 'center' ? 'text-center' : 'text-left'
                          } ${meta?.primary ? '' : 'hidden md:table-cell'}`}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      )
                    })}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {pageCount > 1 ? (
        <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2 text-[13px] text-faint">
          <span>
            {rows.length} row{rows.length === 1 ? '' : 's'} · page {pageIndex + 1} of {pageCount}
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              disabled={!table.getCanPreviousPage()}
              onClick={() => table.previousPage()}
              className="surface rounded-lg px-3 py-1 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={!table.getCanNextPage()}
              onClick={() => table.nextPage()}
              className="surface rounded-lg px-3 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
