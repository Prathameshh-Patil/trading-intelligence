/**
 * The one place the site talks to a server.
 *
 * `NEXT_PUBLIC_API_BASE` decides which server. Unset — the default in
 * development — and every call goes to `mockApi`, so the site is clickable end
 * to end with nothing running. Set it, and the identical calls go over HTTP to
 * `services/api`. No page knows which one it got, which is the point: the pages
 * are built against the fake and do not change when the real one lands.
 */

import { mockApi } from './mockApi'
import { ApiError } from './types'
import type { LicenceKey, Me, Payment, Release, Ticket, WaitlistEntry } from './types'

const BASE = process.env.NEXT_PUBLIC_API_BASE

export const USING_MOCK = !BASE

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      // The session is an httpOnly cookie the JS cannot read, which is why it is
      // not in localStorage and why every call has to opt into sending it.
      credentials: 'include',
      headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    // A dead server and a refused request mean different things to a person: one
    // says try again, the other says fix your input.
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.')
  }

  if (res.status === 204) return undefined as T

  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : (detail?.error ?? 'Something went wrong.')
    throw new ApiError(res.status, message)
  }
  return body as T
}

/** Data URLs are how the mock carries a screenshot; the real API wants a file. */
function dataUrlToBlob(dataUrl: string): Blob {
  const [header, encoded] = dataUrl.split(',')
  const mime = /:(.*?);/.exec(header)?.[1] ?? 'application/octet-stream'
  const binary = atob(encoded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

type Api = typeof mockApi

const realApi: Api = {
  release: () => http<Release>('/api/v1/site/release'),

  setPublic: (isPublic) =>
    http<Release>('/api/v1/site/release', {
      method: 'POST',
      body: JSON.stringify({ is_public: isPublic }),
    }),

  me: () => http<Me | null>('/api/v1/auth/me'),

  signup: (email, password) =>
    http<Me>('/api/v1/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) }),

  login: (email, password) =>
    http<Me>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  logout: () => http<void>('/api/v1/auth/logout', { method: 'POST' }),

  submitPayment: (input) => {
    const form = new FormData()
    form.set('plan', input.plan)
    form.set('method', input.method)
    form.set('amount', String(input.amount))
    form.set('currency', input.currency)
    form.set('reference', input.reference)
    form.set('proof_name', input.proofName)
    form.set('proof', dataUrlToBlob(input.proofUrl), input.proofName)
    return http<Payment>('/api/v1/payments', { method: 'POST', body: form })
  },

  myPayments: () => http<Payment[]>('/api/v1/payments/mine'),

  keysMine: () => http<LicenceKey>('/api/v1/keys/mine'),

  adminPayments: () => http<Payment[]>('/api/v1/admin/payments'),

  approvePayment: (paymentId) =>
    http<LicenceKey>(`/api/v1/admin/payments/${paymentId}/approve`, { method: 'POST' }),

  rejectPayment: (paymentId, reason) =>
    http<Payment>(`/api/v1/admin/payments/${paymentId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  createTicket: (input) =>
    http<Ticket>('/api/v1/tickets', { method: 'POST', body: JSON.stringify(input) }),

  myTickets: () => http<Ticket[]>('/api/v1/tickets/mine'),

  adminTickets: () => http<Ticket[]>('/api/v1/admin/tickets'),

  replyToTicket: (ticketId, body) =>
    http<Ticket>(`/api/v1/admin/tickets/${ticketId}/reply`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  closeTicket: (ticketId) =>
    http<Ticket>(`/api/v1/admin/tickets/${ticketId}/close`, { method: 'POST' }),

  joinWaitlist: (email) =>
    http<void>('/api/v1/waitlist', { method: 'POST', body: JSON.stringify({ email }) }),

  waitlist: () => http<WaitlistEntry[]>('/api/v1/admin/waitlist'),
}

export const api: Api = USING_MOCK ? mockApi : realApi
