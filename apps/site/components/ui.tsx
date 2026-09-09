'use client'

/**
 * The primitives, matched to `apps/desktop/src/ui/theme.css`.
 *
 * A buyer sees this site and then the app. If the button here is a flat amber
 * rectangle and the button there is a violet gradient with a glow under it, the
 * two look like different products — so these are the app's shapes: gradient
 * fill, 12px radius, indigo glow, translucent-white ghosts.
 */

import Link from 'next/link'
import { useState, type ReactNode } from 'react'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-300 disabled:opacity-55 disabled:cursor-not-allowed disabled:shadow-none px-6 py-3.5'

export const buttonClass = {
  primary: `${BASE} grad glow text-white hover:brightness-110 hover:shadow-[0_10px_34px_rgba(99,102,241,0.5)]`,
  secondary: `${BASE} surface text-ink hover:surface-hi hover:border-white/20`,
  danger: `${BASE} border border-ask/30 bg-ask/10 text-ask hover:bg-ask/15`,
}

export function Button({
  kind = 'primary',
  children,
  ...rest
}: { kind?: keyof typeof buttonClass; children: ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={buttonClass[kind]} {...rest}>
      {children}
    </button>
  )
}

export function ButtonLink({
  href,
  kind = 'primary',
  children,
}: {
  href: string
  kind?: keyof typeof buttonClass
  children: ReactNode
}) {
  return (
    <Link href={href} className={buttonClass[kind]}>
      {children}
    </Link>
  )
}

/** The app's `.brand-mark`: gradient tile, violet glow beneath it. */
export function Mark({ size = 30 }: { size?: number }) {
  return (
    <span
      className="grad grid shrink-0 place-items-center rounded-[9px] font-extrabold text-white shadow-[0_4px_14px_rgba(139,92,246,0.45)]"
      style={{ width: size, height: size, fontSize: size * 0.45 }}
    >
      T
    </span>
  )
}

export function Banner({
  kind = 'info',
  children,
}: {
  kind?: 'info' | 'error' | 'success' | 'warn'
  children: ReactNode
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
      className={`my-4 rounded-xl border px-4 py-3.5 text-[15px] leading-relaxed ${styles}`}
    >
      {children}
    </div>
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[11px] font-semibold tracking-[0.06em] text-faint uppercase">
        {label}
      </span>
      {children}
      {hint ? <span className="text-[13px] text-faint">{hint}</span> : null}
    </label>
  )
}

/** Small violet pill. The app puts one above every view heading. */
export function Eyebrow({ children, muted = false }: { children: ReactNode; muted?: boolean }) {
  return (
    <span
      className={`inline-flex w-fit shrink-0 self-start items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-bold tracking-[0.14em] uppercase ${
        muted
          ? 'border-white/10 bg-white/[0.03] text-faint'
          : 'border-violet/30 bg-violet/10 text-violet-lift'
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
}: {
  eyebrow?: string
  title: string
  lede?: ReactNode
}) {
  return (
    <header className="mb-10">
      {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
      <h1 className="mt-5 mb-4 text-[clamp(2.2rem,5vw,3.2rem)]">{title}</h1>
      {lede ? <p className="max-w-[62ch] text-lg text-dim">{lede}</p> : null}
    </header>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`surface rounded-2xl p-6 ${className}`}>{children}</div>
}

export function Pill({ status }: { status: string }) {
  const tone =
    status === 'approved' || status === 'answered' || status.startsWith('core')
      ? 'border-bid/30 bg-bid/10 text-bid'
      : status === 'rejected'
        ? 'border-ask/35 bg-ask/10 text-ask'
        : 'border-warn/30 bg-warn/10 text-warn'
  return (
    <span
      className={`num inline-block rounded-full border px-2.5 py-0.5 text-xs font-bold capitalize ${tone}`}
    >
      {status.replace('_', ' ')}
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
 * A copy button that confirms itself.
 *
 * Used for the UPI ID, the wallet address and the licence key — every string
 * here where one mistyped character is a payment that never arrives or a key
 * that never validates. Copying has to be the obvious path, not an option.
 */
export function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)

  return (
    <div className="surface my-3 flex flex-wrap items-center gap-3 rounded-xl px-4 py-3.5">
      <span className="text-[11px] font-bold tracking-[0.1em] text-faint uppercase">{label}</span>
      <code className="num min-w-[200px] flex-1 break-all text-[15px] text-ink">{value}</code>
      <button
        type="button"
        className="surface-hi rounded-lg px-3.5 py-1.5 text-[13px] font-semibold transition hover:border-violet/40"
        onClick={() => {
          void navigator.clipboard.writeText(value)
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1400)
        }}
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}
