'use client'

/**
 * Modal, Drawer, and the toast stack. No `window.prompt` anywhere: a reason
 * the user will read deserves a textarea, and a key that was just minted
 * deserves to be shown, not `alert`ed.
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

import { CloseIcon } from './icons'
import { Button } from './primitives'

function useEscape(onClose: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  width = 'max-w-[520px]',
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: string
}) {
  useEscape(onClose)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => box.current?.querySelector<HTMLElement>('input,textarea,button')?.focus(), [])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <button type="button" aria-label="Close" className="vh-fade absolute inset-0 bg-black/70" onClick={onClose} />
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`vh-rise relative w-full ${width} rounded-2xl border border-line-hi bg-panel shadow-[0_30px_80px_-20px_rgba(0,0,0,0.8)]`}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="p-1 text-faint hover:text-ink">
            <CloseIcon size={16} />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer ? <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div> : null}
      </div>
    </div>
  )
}

export function ConfirmModal({
  title,
  body,
  confirmLabel = 'Confirm',
  kind = 'primary',
  onConfirm,
  onClose,
  requireText,
}: {
  title: string
  body: ReactNode
  confirmLabel?: string
  kind?: 'primary' | 'danger' | 'success'
  onConfirm: (text: string) => Promise<void> | void
  onClose: () => void
  /** Ask for a free-text reason; the label is the placeholder. */
  requireText?: string
}) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function go() {
    setBusy(true)
    setError('')
    try {
      await onConfirm(text.trim())
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not work.')
      setBusy(false)
    }
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button kind="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button kind={kind} onClick={go} loading={busy} disabled={requireText ? text.trim().length === 0 : false}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-[14px] text-dim">{body}</div>
      {requireText ? (
        <textarea
          className="mt-3 min-h-[96px]"
          placeholder={requireText}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      ) : null}
      {error ? <p className="mt-3 text-[13px] text-ask">{error}</p> : null}
    </Modal>
  )
}

export function Drawer({
  title,
  subtitle,
  onClose,
  children,
  width = 'max-w-[560px]',
}: {
  title: ReactNode
  subtitle?: ReactNode
  onClose: () => void
  children: ReactNode
  width?: string
}) {
  useEscape(onClose)
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" aria-label="Close" className="vh-fade absolute inset-0 bg-black/60" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        className={`vh-slide relative flex h-full w-full ${width} flex-col border-l border-line-hi bg-panel shadow-[-30px_0_80px_-20px_rgba(0,0,0,0.8)]`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-[16px] font-semibold">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-[13px] text-faint">{subtitle}</p> : null}
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="p-1 text-faint hover:text-ink">
            <CloseIcon size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>
  )
}

// ------------------------------------------------------------------ toasts

type Toast = { id: number; kind: 'info' | 'success' | 'error'; title: string; body?: string }

const ToastContext = createContext<{ push: (t: Omit<Toast, 'id'>) => void } | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Date.now() + Math.random()
    setToasts((all) => [...all, { ...t, id }].slice(-4))
    window.setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), t.kind === 'error' ? 7000 : 4500)
  }, [])

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(360px,calc(100vw-32px))] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`vh-rise pointer-events-auto rounded-xl border px-4 py-3 text-[14px] shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)] ${
              t.kind === 'success'
                ? 'border-bid/30 bg-[#0b1a15] text-bid'
                : t.kind === 'error'
                  ? 'border-ask/30 bg-[#1c0f10] text-ask'
                  : 'border-violet/30 bg-[#14122a] text-violet-lift'
            }`}
          >
            <p className="font-semibold">{t.title}</p>
            {t.body ? <p className="mt-0.5 text-[13px] text-dim">{t.body}</p> : null}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx.push
}
