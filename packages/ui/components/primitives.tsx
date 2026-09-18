'use client'

/**
 * The primitives, shared by the customer site and the admin portal.
 *
 * Same shapes as the desktop app: gradient fill, 12px radius, indigo glow on
 * the one primary action, translucent-white ghosts for everything else.
 */

import Link from 'next/link'
import { useState, type ReactNode } from 'react'

import { CheckIcon, CopyIcon } from './icons'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-200 disabled:opacity-55 disabled:cursor-not-allowed disabled:shadow-none whitespace-nowrap'

const SIZE = {
  md: 'px-5 py-2.5 text-[14px]',
  sm: 'px-3.5 py-1.5 text-[13px] rounded-lg',
  lg: 'px-6 py-3.5 text-[15px]',
}

export const buttonKind = {
  primary: 'grad glow text-white hover:brightness-110',
  secondary: 'surface text-ink hover:border-white/20 hover:bg-white/[0.06]',
  ghost: 'text-dim hover:text-ink hover:bg-white/[0.05]',
  danger: 'border border-ask/30 bg-ask/10 text-ask hover:bg-ask/15',
  success: 'border border-bid/30 bg-bid/10 text-bid hover:bg-bid/15',
}

export type ButtonKind = keyof typeof buttonKind
export type ButtonSize = keyof typeof SIZE

export function buttonClass(kind: ButtonKind = 'primary', size: ButtonSize = 'md', extra = '') {
  return `${BASE} ${SIZE[size]} ${buttonKind[kind]} ${extra}`
}

export function Button({
  kind = 'primary',
  size = 'md',
  className = '',
  loading = false,
  children,
  ...rest
}: {
  kind?: ButtonKind
  size?: ButtonSize
  className?: string
  loading?: boolean
  children: ReactNode
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={buttonClass(kind, size, className)} disabled={loading || rest.disabled} {...rest}>
      {loading ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" /> : null}
      {children}
    </button>
  )
}

export function ButtonLink({
  href,
  kind = 'primary',
  size = 'md',
  className = '',
  children,
  external = false,
}: {
  href: string
  kind?: ButtonKind
  size?: ButtonSize
  className?: string
  children: ReactNode
  external?: boolean
}) {
  if (external) {
    return (
      <a href={href} className={buttonClass(kind, size, className)} target="_blank" rel="noreferrer">
        {children}
      </a>
    )
  }
  return (
    <Link href={href} className={buttonClass(kind, size, className)}>
      {children}
    </Link>
  )
}

/** The Vision Hub mark: a V cut from a lens, on the brand gradient. */
export function Mark({ size = 30 }: { size?: number }) {
  return (
    <span
      className="grad grid shrink-0 place-items-center rounded-[9px] text-white shadow-[0_4px_14px_rgba(139,92,246,0.45)]"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
        <path d="M4 6l8 12 8-12" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="12" cy="7.2" r="2.1" fill="currentColor" />
      </svg>
    </span>
  )
}

export function Banner({
  kind = 'info',
  children,
  className = '',
}: {
  kind?: 'info' | 'error' | 'success' | 'warn'
  children: ReactNode
  className?: string
}) {
  const styles = {
    info: 'border-violet/35 bg-violet/10 text-violet-lift',
    success: 'border-bid/30 bg-bid/10 text-bid',
    warn: 'border-warn/30 bg-warn/10 text-warn',
    error: 'border-ask/30 bg-ask/10 text-ask',
  }[kind]

  return (
    <div
      role={kind === 'error' ? 'alert' : 'status'}
      className={`my-3 rounded-xl border px-4 py-3 text-[14px] leading-relaxed ${styles} ${className}`}
    >
      {children}
    </div>
  )
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-semibold tracking-[0.06em] text-faint uppercase">{label}</span>
      {children}
      {error ? <span className="text-[13px] text-ask">{error}</span> : null}
      {hint && !error ? <span className="text-[13px] text-faint">{hint}</span> : null}
    </label>
  )
}

export function Eyebrow({ children, muted = false }: { children: ReactNode; muted?: boolean }) {
  return (
    <span
      className={`inline-flex w-fit shrink-0 items-center gap-2 self-start rounded-full border px-3 py-1 text-[11px] font-bold tracking-[0.14em] uppercase ${
        muted ? 'border-white/10 bg-white/[0.03] text-faint' : 'border-violet/30 bg-violet/10 text-violet-lift'
      }`}
    >
      {muted ? null : <span className="h-1.5 w-1.5 rounded-full bg-violet" />}
      {children}
    </span>
  )
}

export function PageHeader({
  eyebrow,
  title,
  lede,
  actions,
  compact = false,
}: {
  eyebrow?: string
  title: string
  lede?: ReactNode
  actions?: ReactNode
  compact?: boolean
}) {
  return (
    <header className={`flex flex-wrap items-end justify-between gap-4 ${compact ? 'mb-6' : 'mb-10'}`}>
      <div>
        {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
        <h1 className={`${eyebrow ? 'mt-4' : ''} ${compact ? 'text-[26px]' : 'text-[clamp(2rem,4.5vw,2.8rem)]'}`}>
          {title}
        </h1>
        {lede ? <p className="mt-2 max-w-[62ch] text-[15px] text-dim">{lede}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}

export function Card({
  children,
  className = '',
  title,
  actions,
  padded = true,
}: {
  children: ReactNode
  className?: string
  title?: ReactNode
  actions?: ReactNode
  padded?: boolean
}) {
  return (
    <section className={`surface rounded-2xl ${padded ? 'p-5' : ''} ${className}`}>
      {title ? (
        <div className={`flex items-center justify-between gap-3 ${padded ? 'mb-4' : 'px-5 pt-5 pb-3'}`}>
          <h2 className="text-[15px] font-semibold">{title}</h2>
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  )
}

const TONES: Record<string, string> = {
  approved: 'border-bid/30 bg-bid/10 text-bid',
  active: 'border-bid/30 bg-bid/10 text-bid',
  answered: 'border-bid/30 bg-bid/10 text-bid',
  core: 'border-violet/30 bg-violet/10 text-violet-lift',
  core_journal: 'border-violet/30 bg-violet/10 text-violet-lift',
  admin: 'border-violet/30 bg-violet/10 text-violet-lift',
  rejected: 'border-ask/35 bg-ask/10 text-ask',
  revoked: 'border-ask/35 bg-ask/10 text-ask',
  suspended: 'border-ask/35 bg-ask/10 text-ask',
  pending: 'border-warn/30 bg-warn/10 text-warn',
  open: 'border-warn/30 bg-warn/10 text-warn',
  closed: 'border-white/10 bg-white/[0.04] text-faint',
  user: 'border-white/10 bg-white/[0.04] text-dim',
}

export function Pill({ status, className = '' }: { status: string; className?: string }) {
  const tone = TONES[status] ?? 'border-white/10 bg-white/[0.04] text-dim'
  return (
    <span
      className={`num inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold tracking-wide uppercase ${tone} ${className}`}
    >
      {status.replace('_', ' + ')}
    </span>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <div role="status" className="inline-flex items-center gap-2.5 text-sm text-dim">
      <span className="grad h-2 w-2 animate-pulse rounded-full motion-reduce:animate-none" />
      {label}
    </div>
  )
}

/**
 * A copy button that confirms itself. Used for the licence key and the
 * payment addresses -- every string where one mistyped character is a key
 * that never validates.
 */
export function CopyField({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false)

  return (
    <div className="surface my-2 flex flex-wrap items-center gap-3 rounded-xl px-4 py-3">
      <span className="text-[11px] font-bold tracking-[0.1em] text-faint uppercase">{label}</span>
      <code className={`min-w-[200px] flex-1 break-all text-[14px] text-ink ${mono ? 'num' : ''}`}>{value}</code>
      <button
        type="button"
        className="surface-hi inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-semibold transition hover:border-violet/40"
        onClick={() => {
          void navigator.clipboard.writeText(value)
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1400)
        }}
      >
        {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

export function EmptyState({ title, body, action }: { title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="text-[15px] font-semibold">{title}</p>
      {body ? <p className="max-w-[46ch] text-sm text-faint">{body}</p> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  )
}

export function StatCard({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'default' | 'warn' | 'good' | 'bad'
}) {
  const color = { default: 'text-ink', warn: 'text-warn', good: 'text-bid', bad: 'text-ask' }[tone]
  return (
    <div className="surface rounded-2xl px-5 py-4">
      <p className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">{label}</p>
      <p className={`num mt-1 text-[28px] leading-none font-semibold ${color}`}>{value}</p>
      {hint ? <p className="mt-2 text-[12px] text-faint">{hint}</p> : null}
    </div>
  )
}

export function LiveDot({ status, label }: { status: 'open' | 'connecting' | 'closed'; label?: string }) {
  const color = status === 'open' ? 'bg-bid live-dot' : status === 'connecting' ? 'bg-warn' : 'bg-faint'
  const text = label ?? (status === 'open' ? 'Live' : status === 'connecting' ? 'Connecting' : 'Offline')
  return (
    <span className="inline-flex items-center gap-2 text-[12px] text-dim" title={`Event stream: ${status}`}>
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {text}
    </span>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="surface rounded-md px-1.5 py-0.5 text-[11px] text-dim">{children}</kbd>
  )
}

/** Local, short, human. "2 min ago", "yesterday", "12 Sep". */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  const s = Math.round((Date.now() - t) / 1000)
  if (s < 45) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  if (s < 172800) return 'yesterday'
  if (s < 30 * 86400) return `${Math.round(s / 86400)} d ago`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
