'use client'

/**
 * Pay, then prove it.
 *
 * There is no processor, so this page *is* the processor: it shows the rail,
 * takes the reference number and the screenshot, and hands both to a human.
 *
 * Two things it deliberately does not do — claim the money arrived, or promise a
 * key in a fixed number of minutes. Both would be guesses, and someone who has
 * just sent money to a stranger on the internet is owed the true answer instead.
 */

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'

import { Banner, Button, CopyField, Field, PageHeader } from '@/components/ui'
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
import { useSession } from '@/lib/session'
import type { PaymentMethod } from '@/lib/types'

/** Big enough for a full-screen retina screenshot, small enough not to wedge the upload. */
const MAX_PROOF_BYTES = 5 * 1024 * 1024

function CheckoutInner() {
  const params = useSearchParams()
  const { me } = useSession()
  const router = useRouter()

  const plan: PlanId = params.get('plan') === 'core_journal' ? 'core_journal' : 'core'
  const [method, setMethod] = useState<PaymentMethod>(
    params.get('currency') === 'inr' ? 'upi' : 'usdt',
  )
  const [reference, setReference] = useState('')
  const [proof, setProof] = useState<{ name: string; url: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!me) {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-16">
        <PageHeader title="Sign in first" lede="A licence key has to belong to an account." />
        <Link href="/login" className="text-violet-lift">Sign in →</Link>
      </main>
    )
  }

  const currency = CURRENCY_OF_METHOD[method]
  const amount = priceOf(plan, currency)

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > MAX_PROOF_BYTES) {
      setError('That screenshot is over 5 MB. Crop it, or export it as a JPEG.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setError('')
      setProof({ name: file.name, url: String(reader.result) })
    }
    reader.onerror = () => setError('That file could not be read. Try a different one.')
    reader.readAsDataURL(file)
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
      await api.submitPayment({
        plan,
        method,
        amount,
        currency,
        reference: reference.trim(),
        proofName: proof.name,
        proofUrl: proof.url,
      })
      router.push('/key')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-[720px] px-6 py-16">
      <PageHeader
        eyebrow="CHECKOUT"
        title={`${planById(plan).name} — ${formatPrice(amount, currency)}/month`}
        lede="Send the payment on whichever rail suits you, then tell us it is done. One of us checks it by hand and issues your key."
      />

      <Banner kind="info">
        <strong>Founding price, permanently.</strong> You are one of the first{' '}
        {PRICING.foundingSeats}. This is what you pay for as long as your subscription runs
        without a break, even after we raise it for everyone else.
      </Banner>

      <div
        role="group"
        aria-label="Payment method"
        className="my-7 inline-flex gap-1 surface rounded-xl p-1"
      >
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
            className={`num rounded-lg px-4 py-2 text-sm font-semibold ${
              method === option.id ? 'grad text-white' : 'text-dim'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <section className="surface rounded-2xl p-7">
        <h2 className="mb-4 text-[19px] font-semibold">
          Step 1 — send {formatPrice(amount, currency)}
        </h2>

        {method === 'upi' ? (
          <>
            <CopyField label="UPI ID" value={PAYMENT.upi.id} />
            <p className="text-sm text-faint">
              The account shows as <strong className="text-ink">{PAYMENT.upi.accountName}</strong>.
              If your app shows a different name, stop and{' '}
              <Link href="/contact" className="text-violet-lift">tell us</Link> before sending anything.
            </p>
          </>
        ) : (
          <>
            {/* Stated above the address and again below it. USDT on the wrong
                network is unrecoverable — by us, by them, by anyone — so this is
                the one place on the site that repeats itself on purpose. */}
            <Banner kind="warn">
              <strong>{PAYMENT.usdt.network} only.</strong> USDT sent on any other network is
              unrecoverable. Check the network in your wallet before you confirm, not after.
            </Banner>
            <CopyField
              label={`USDT address (${PAYMENT.usdt.chain})`}
              value={PAYMENT.usdt.address}
            />
            <p className="text-sm text-faint">
              Send on <strong className="text-ink">{PAYMENT.usdt.network}</strong>, and send
              roughly {formatPrice(amount, currency)} worth. You pay the network fee; a few cents
              either way is fine and we will not chase you for it.
            </p>
          </>
        )}
      </section>

      <form className="mt-5 flex flex-col gap-5 surface rounded-2xl p-7" onSubmit={submit}>
        <h2 className="text-[19px] font-semibold">Step 2 — prove it</h2>

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

        <Field
          label="Screenshot of the payment"
          hint="The confirmation screen from your app or wallet. PNG or JPEG, up to 5 MB."
        >
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onFile} />
        </Field>

        {proof ? (
          <div className="flex items-center gap-4 text-sm text-dim">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={proof.url}
              alt="Payment screenshot preview"
              className="w-28 rounded-lg border border-white/[0.08]"
            />
            <span className="num">{proof.name}</span>
          </div>
        ) : null}

        {error ? <Banner kind="error">{error}</Banner> : null}

        <Button type="submit" disabled={busy}>
          {busy ? 'Submitting…' : 'Submit for review'}
        </Button>

        <p className="text-sm text-faint">
          Submitting does not charge you — you have already paid, and this is you telling us so.
          Nothing renews automatically. By submitting you accept the{' '}
          <Link href="/policy" className="text-violet-lift">terms and the refund policy</Link>.
        </p>
      </form>
    </main>
  )
}

export default function CheckoutPage() {
  // useSearchParams needs a boundary or the whole route opts out of prerendering.
  return (
    <Suspense fallback={null}>
      <CheckoutInner />
    </Suspense>
  )
}
