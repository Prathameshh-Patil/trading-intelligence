'use client'

/**
 * The left rail both sites hang off.
 *
 * Desktop: a fixed 248px column with the brand at the top, the navigation
 * in the middle and an account block pinned to the bottom. The page content
 * sits to its right and the *window* scrolls, so anything that listens to
 * scroll position (the landing page's scenes) keeps working.
 *
 * Phone: the rail becomes a top bar with a menu button; the same navigation
 * slides in as a drawer.
 */

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState, type ReactNode } from 'react'

import { CloseIcon, MenuIcon } from './icons'

export type NavItem = {
  href: string
  label: string
  icon?: ReactNode
  badge?: ReactNode
  /** Match this route and everything under it. */
  prefix?: boolean
}

export type NavGroup = { title?: string; items: NavItem[] }

export function SidebarShell({
  brand,
  groups,
  footer,
  topbar,
  children,
  railFooter,
}: {
  brand: ReactNode
  groups: NavGroup[]
  /** Bottom of the rail -- the account block. */
  footer?: ReactNode
  /** Right side of the phone top bar / desktop content header. */
  topbar?: ReactNode
  /** Small print under the nav, above the footer. */
  railFooter?: ReactNode
  children: ReactNode
}) {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  // Route change closes the drawer.
  useEffect(() => setOpen(false), [pathname])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open])

  const isActive = (item: NavItem) =>
    item.prefix ? pathname === item.href || pathname.startsWith(item.href + '/') : pathname === item.href

  const nav = (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-2">
      {groups.map((group, i) => (
        <div key={group.title ?? i}>
          {group.title ? (
            <p className="px-3 pb-1.5 text-[10.5px] font-bold tracking-[0.14em] text-faint uppercase">{group.title}</p>
          ) : null}
          <ul className="flex flex-col gap-0.5">
            {group.items.map((item) => {
              const active = isActive(item)
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={`group flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] font-medium transition ${
                      active
                        ? 'bg-violet/15 text-ink shadow-[inset_2px_0_0_0_var(--color-violet)]'
                        : 'text-dim hover:bg-white/[0.05] hover:text-ink'
                    }`}
                  >
                    {item.icon ? (
                      <span className={`shrink-0 ${active ? 'text-violet-lift' : 'text-faint group-hover:text-dim'}`}>
                        {item.icon}
                      </span>
                    ) : null}
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.badge ? <span className="shrink-0">{item.badge}</span> : null}
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )

  return (
    <div className="min-h-screen">
      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-rail flex-col border-r border-line bg-raise/80 backdrop-blur-xl lg:flex">
        <div className="px-5 pt-5 pb-4">{brand}</div>
        {nav}
        {railFooter ? <div className="px-5 py-3 text-[12px] text-faint">{railFooter}</div> : null}
        {footer ? <div className="border-t border-line p-3">{footer}</div> : null}
      </aside>

      {/* Phone top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-line bg-bg/80 px-4 py-3 backdrop-blur-xl lg:hidden">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Open navigation"
            aria-expanded={open}
            onClick={() => setOpen(true)}
            className="surface rounded-lg p-2 text-dim hover:text-ink"
          >
            <MenuIcon />
          </button>
          {brand}
        </div>
        {topbar ? <div className="flex items-center gap-2">{topbar}</div> : null}
      </header>

      {/* Phone drawer */}
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="vh-fade absolute inset-0 bg-black/60"
            onClick={() => setOpen(false)}
          />
          <div className="vh-slide absolute inset-y-0 left-0 flex w-[min(300px,85vw)] flex-col border-r border-line bg-raise">
            <div className="flex items-center justify-between px-5 pt-5 pb-4">
              {brand}
              <button type="button" aria-label="Close" onClick={() => setOpen(false)} className="p-1 text-dim">
                <CloseIcon />
              </button>
            </div>
            {nav}
            {footer ? <div className="border-t border-line p-3">{footer}</div> : null}
          </div>
        </div>
      ) : null}

      <div className="lg:pl-rail">
        {topbar ? (
          <div className="sticky top-0 z-20 hidden items-center justify-end gap-3 border-b border-line bg-bg/70 px-6 py-2.5 backdrop-blur-xl lg:flex">
            {topbar}
          </div>
        ) : null}
        {children}
      </div>
    </div>
  )
}
