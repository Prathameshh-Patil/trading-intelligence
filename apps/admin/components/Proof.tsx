'use client'

/**
 * A payment proof, fetched with the bearer token and shown from an object
 * URL. `<img src>` cannot carry a header, and the proof route refuses
 * anything without one.
 */

import { useEffect, useState } from 'react'
import type { Payment } from '@vision-hub/contracts'
import { Modal } from '@vision-hub/ui'

import { api } from '@/lib/api'

export function useProof(path: string | null) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!path) return
    let alive = true
    let object: string | null = null
    api
      .blob(path)
      .then((b) => {
        if (!alive) return
        object = URL.createObjectURL(b)
        setUrl(object)
      })
      .catch(() => setUrl(null))
    return () => {
      alive = false
      if (object) URL.revokeObjectURL(object)
    }
  }, [path])
  return url
}

export function ProofThumb({ payment, onOpen }: { payment: Payment; onOpen: () => void }) {
  const url = useProof(payment.proof_url)
  const isPdf = payment.proof_name.toLowerCase().endsWith('.pdf')
  return (
    <button
      type="button"
      onClick={onOpen}
      className="surface grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg text-[10px] text-faint"
      title={payment.proof_name}
    >
      {url && !isPdf ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="" className="h-full w-full object-cover" />
      ) : (
        isPdf ? 'PDF' : '…'
      )}
    </button>
  )
}

export function ProofModal({ payment, onClose }: { payment: Payment; onClose: () => void }) {
  const url = useProof(payment.proof_url)
  const isPdf = payment.proof_name.toLowerCase().endsWith('.pdf')
  return (
    <Modal title={`Proof from ${payment.email}`} onClose={onClose} width="max-w-[900px]">
      <p className="num mb-3 text-[13px] text-faint">
        {payment.plan} · {payment.method.toUpperCase()} · {payment.currency === 'usd' ? '$' : '₹'}
        {payment.amount} · ref {payment.reference}
      </p>
      {url ? (
        isPdf ? (
          <iframe src={url} title={payment.proof_name} className="h-[70vh] w-full rounded-lg bg-white" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={`Payment proof from ${payment.email}`} className="max-h-[70vh] w-full rounded-lg object-contain" />
        )
      ) : (
        <p className="text-sm text-faint">Loading…</p>
      )}
    </Modal>
  )
}
