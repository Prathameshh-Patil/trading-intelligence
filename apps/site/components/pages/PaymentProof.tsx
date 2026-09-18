'use client'

/**
 * Pay, then prove it -- the old checkout, now a card on the account page.
 *
 * There is no processor, so this form *is* the processor: it shows the rail,
 * takes the reference and the screenshot, and hands both to a human. It is
 * deliberately off the path to the key: approval is of the account, and this
 * is an attachment the approver can see, not a gate.
 *
 * Two things it does not do -- claim the money arrived, or promise anything
 * in a fixed number of minutes. Both would be guesses, and someone who has
 * just sent money to a stranger on the internet is owed the true answer.
 */

import Link from 'next/link'
import { useState } from 'react'
import type { PaymentMethod } from '@vision-hub/contracts'
import { Banner, Button, CopyField, Field, useToast } from '@vision-hub/ui'

import {
  CURRENCY_OF_METHOD,
  PAYMENT,
  PRICING,
  formatPrice,
  planById,
  priceOf,
  type PlanId,
} from '@/content/site'
import { api } from '@/lib/api'

/** Big enough for a full-screen retina screenshot, small enough not to wedge the upload. */
const MAX_PROOF_BYTES = 5 * 1024 * 1024

export function PaymentProof({ onSubmitted }: { onSubmitted: () => void }) {
  const toast = useToast()
  const [plan, setPlan] = useState<PlanId>('core')
  const [method, setMethod] = useState<PaymentMethod>('usdt')
  const [reference, setReference] = useState('')
  const [proof, setProof] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const currency = CURRENCY_OF_METHOD[method]
  const amount = priceOf(plan, currency)

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > MAX_PROOF_BYTES) {
      setError('That screenshot is over 5 MB. Crop it, or export it as a JPEG.')
      return
    }
    setError('')
    setProof(file)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(URL.createObjectURL(file))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!proof) {
      setError('Attach the screenshot — it is what we check against.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await api.submitPayment({ plan, method, amount, currency, reference: reference.trim(), proof })
      toast({ kind: 'success', title: 'Receipt attached', body: 'It is on your account for the person approving you.' })
      setReference('')
      setProof(null)
      if (preview) URL.revokeObjectURL(preview)
      setPreview(null)
      onSubmitted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="surface rounded-2xl p-6">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Plan" className="surface inline-flex gap-1 rounded-xl p-1">
            {PRICING.plans.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPlan(p.id)}
                className={`rounded-lg px-3 py-1.5 text-[13px] font-semibold ${plan === p.id ? 'grad text-white' : 'text-dim'}`}
              >
                {p.name}
              </button>
            ))}
          </div>
          <div role="group" aria-label="Payment method" className="surface inline-flex gap-1 rounded-xl p-1">
            {(
              [
                { id: 'upi', label: 'UPI · ₹' },
                { id: 'usdt', label: 'USDT · $' },
              ] as const
            ).map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setMethod(option.id)}
                className={`num rounded-lg px-3 py-1.5 text-[13px] font-semibold ${method === option.id ? 'grad text-white' : 'text-dim'}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <h3 className="mb-3 text-[16px] font-semibold">
          Step 1 — send {formatPrice(amount, currency)} for {planById(plan).name}
        </h3>

        {method === 'upi' ? (
          <>
            <CopyField label="UPI ID" value={PAYMENT.upi.id} />
            <p className="text-[13px] text-faint">
              The account shows as <strong className="text-ink">{PAYMENT.upi.accountName}</strong>. If
              your app shows a different name, stop and{' '}
              <Link href="/contact" className="text-violet-lift">tell us</Link> before sending anything.
            </p>
          </>
        ) : (
          <>
            {/* Stated above the address and again below it. USDT on the wrong
                network is unrecoverable -- by us, by them, by anyone -- so this
                is the one place on the site that repeats itself on purpose. */}
            <Banner kind="warn">
              <strong>{PAYMENT.usdt.network} only.</strong> USDT sent on any other network is
              unrecoverable. Check the network in your wallet before you confirm, not after.
            </Banner>
            <CopyField label={`USDT address (${PAYMENT.usdt.chain})`} value={PAYMENT.usdt.address} />
            <p className="text-[13px] text-faint">
              Send on <strong className="text-ink">{PAYMENT.usdt.network}</strong>, roughly{' '}
              {formatPrice(amount, currency)} worth. You pay the network fee; a few cents either way
              is fine.
            </p>
          </>
        )}
      </section>

      <form className="surface flex flex-col gap-4 rounded-2xl p-6" onSubmit={submit}>
        <h3 className="text-[16px] font-semibold">Step 2 — attach the receipt</h3>

        <Field
          label={method === 'upi' ? 'UPI transaction ID' : 'Transaction hash'}
          hint={
            method === 'upi'
              ? 'The 12-digit reference your UPI app shows after a successful payment.'
              : 'The transaction hash from your wallet or the block explorer.'
          }
        >
          <input
            required
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder={method === 'upi' ? '417200000000' : '0x…'}
            className="num"
          />
        </Field>

        <Field label="Screenshot of the payment" hint="PNG, JPEG or WebP, up to 5 MB.">
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onFile} />
        </Field>

        {preview && proof ? (
          <div className="flex items-center gap-4 text-sm text-dim">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="Payment screenshot preview" className="w-24 rounded-lg border border-line" />
            <span className="num truncate">{proof.name}</span>
          </div>
        ) : null}

        {error ? <Banner kind="error">{error}</Banner> : null}

        <Button type="submit" loading={busy}>
          Attach receipt
        </Button>

        <p className="text-[12.5px] text-faint">
          Attaching does not charge you — you have already paid, and this is you telling us so.
          Nothing renews automatically. By attaching you accept the{' '}
          <Link href="/policy" className="text-violet-lift">terms and the refund policy</Link>.
        </p>
      </form>
    </div>
  )
}
