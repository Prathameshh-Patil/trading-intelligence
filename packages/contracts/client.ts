/**
 * The one place the browser talks to `services/api`.
 *
 * Every call is a plain REST request. What this file adds is the token
 * lifecycle, which no page has to think about:
 *
 * - The **access token** lives in a closure here -- memory only, never
 *   `localStorage`, so a script injected into the page cannot read it back
 *   out of storage, and closing the tab forgets it.
 * - It is refreshed **before** it expires (a minute early), and **on** a 401
 *   (once, then the request is retried once). Refreshes are single-flight:
 *   ten calls that all hit a 401 at the same moment wait on one refresh.
 * - The **refresh token** is an httpOnly cookie the browser holds; this code
 *   never sees it. Only `/auth/refresh`, `/auth/logout` and `/auth/logout-all`
 *   are called with `credentials: 'include'`, because they are the only routes
 *   that read or clear it.
 * - Tabs share sign-in state over a `BroadcastChannel`, so signing out in one
 *   signs out all of them, and a refresh in one hands the others the new token
 *   rather than each racing to rotate the same cookie.
 */

import { ApiError } from './types'
import type {
  ApproveResponse,
  AuditEntry,
  AuthResponse,
  KeySummary,
  LicenceKey,
  Me,
  Payment,
  Release,
  Role,
  SessionInfo,
  Stats,
  Ticket,
  User,
  UserDetail,
  WaitlistEntry,
} from './types'

export type AuthState = { user: Me | null; ready: boolean }

type Listener = (state: AuthState) => void

type BroadcastMessage =
  | { kind: 'signed-in'; access: string; expiresAt: number; user: Me }
  | { kind: 'signed-out' }

/** Refresh this many ms before the access token expires. */
const EARLY_MS = 60_000

export type PaymentInput = {
  plan: 'core' | 'core_journal'
  method: 'upi' | 'usdt'
  amount: number
  currency: 'usd' | 'inr'
  reference: string
  proof: File
}

export type TicketInput = { email?: string; category: string; subject: string; body: string }

export function createApi(base: string) {
  const root = base.replace(/\/+$/, '')

  let access: string | null = null
  let expiresAt = 0
  let user: Me | null = null
  let ready = false
  let refreshing: Promise<boolean> | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  const listeners = new Set<Listener>()

  const channel =
    typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('vh-auth') : null

  function emit() {
    const state: AuthState = { user, ready }
    listeners.forEach((l) => l(state))
  }

  function schedule() {
    if (timer) clearTimeout(timer)
    timer = null
    if (!access) return
    const delay = Math.max(1_000, expiresAt - Date.now() - EARLY_MS)
    timer = setTimeout(() => void refresh(), delay)
  }

  function setSignedIn(body: AuthResponse, broadcast: boolean) {
    access = body.access_token
    expiresAt = Date.now() + body.expires_in * 1_000
    user = body.user
    ready = true
    schedule()
    emit()
    if (broadcast) channel?.postMessage({ kind: 'signed-in', access, expiresAt, user } satisfies BroadcastMessage)
  }

  function setSignedOut(broadcast: boolean) {
    const was = access !== null || user !== null
    access = null
    expiresAt = 0
    user = null
    ready = true
    if (timer) clearTimeout(timer)
    timer = null
    emit()
    if (broadcast && was) channel?.postMessage({ kind: 'signed-out' } satisfies BroadcastMessage)
  }

  if (channel) {
    channel.onmessage = (ev: MessageEvent<BroadcastMessage>) => {
      const msg = ev.data
      if (msg.kind === 'signed-in') {
        access = msg.access
        expiresAt = msg.expiresAt
        user = msg.user
        ready = true
        schedule()
        emit()
      } else if (msg.kind === 'signed-out') {
        setSignedOut(false)
      }
    }
  }

  async function parse<T>(res: Response): Promise<T> {
    if (res.status === 204) return undefined as T
    const body = await res.json().catch(() => null)
    if (!res.ok) {
      const detail = body?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : typeof detail?.error === 'string'
            ? detail.error
            : Array.isArray(detail) && detail[0]?.msg
              ? String(detail[0].msg)
              : 'Something went wrong.'
      throw new ApiError(res.status, message, typeof detail === 'object' && detail && !Array.isArray(detail) ? detail : null)
    }
    return body as T
  }

  async function refresh(): Promise<boolean> {
    if (refreshing) return refreshing
    refreshing = (async () => {
      try {
        const res = await fetch(`${root}/api/v1/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
        })
        if (!res.ok) {
          setSignedOut(true)
          return false
        }
        setSignedIn(await parse<AuthResponse>(res), true)
        return true
      } catch {
        // Network down: keep whatever we have; the next call decides.
        ready = true
        emit()
        return false
      } finally {
        refreshing = null
      }
    })()
    return refreshing
  }

  type ReqInit = RequestInit & { auth?: boolean; retry?: boolean; cookie?: boolean }

  async function request<T>(path: string, init: ReqInit = {}): Promise<T> {
    const { auth = true, retry = true, cookie = false, headers: extra, ...rest } = init

    // A token that is about to expire is refreshed first rather than after
    // a wasted round trip.
    if (auth && access && Date.now() > expiresAt - 5_000) await refresh()

    const headers = new Headers(extra)
    if (!(rest.body instanceof FormData) && rest.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    if (auth && access) headers.set('Authorization', `Bearer ${access}`)

    let res: Response
    try {
      res = await fetch(`${root}${path}`, { ...rest, headers, credentials: cookie ? 'include' : 'same-origin' })
    } catch {
      throw new ApiError(0, 'Could not reach the server. Check your connection and try again.')
    }

    if (res.status === 401 && auth && retry) {
      if (await refresh()) return request<T>(path, { ...init, retry: false })
      setSignedOut(true)
    }
    return parse<T>(res)
  }

  const api = {
    /** Base URL, for anything that needs to build an absolute URL. */
    base: root,

    /** Current state, synchronously. */
    state(): AuthState {
      return { user, ready }
    },

    /** Current access token, for the event stream. */
    accessToken(): string | null {
      return access
    },

    subscribe(listener: Listener): () => void {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },

    /**
     * Called once on page load. If the browser still holds a refresh cookie,
     * this turns it into an access token -- the silent sign-in that survives a
     * reload without anything in `localStorage`.
     */
    async bootstrap(): Promise<Me | null> {
      if (access) return user
      await refresh()
      return user
    },

    // ---------------------------------------------------------------- auth

    async signup(email: string, password: string): Promise<Me> {
      const body = await request<AuthResponse>('/api/v1/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
        auth: false,
        cookie: true,
      })
      setSignedIn(body, true)
      return body.user
    },

    async login(email: string, password: string): Promise<Me> {
      const body = await request<AuthResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
        auth: false,
        cookie: true,
      })
      setSignedIn(body, true)
      return body.user
    },

    async logout(): Promise<void> {
      try {
        await request<void>('/api/v1/auth/logout', { method: 'POST', auth: false, cookie: true })
      } finally {
        setSignedOut(true)
      }
    },

    async logoutAll(): Promise<void> {
      try {
        await request<void>('/api/v1/auth/logout-all', { method: 'POST', cookie: true, retry: false })
      } finally {
        setSignedOut(true)
      }
    },

    me: () => request<Me>('/api/v1/auth/me'),
    sessions: () => request<SessionInfo[]>('/api/v1/auth/sessions'),
    endSession: (familyId: string) =>
      request<void>(`/api/v1/auth/sessions/${encodeURIComponent(familyId)}`, { method: 'DELETE' }),

    // ---------------------------------------------------------------- site

    release: () => request<Release>('/api/v1/site/release'),
    setPublic: (isPublic: boolean) =>
      request<Release>('/api/v1/site/release', { method: 'POST', body: JSON.stringify({ is_public: isPublic }) }),

    // ---------------------------------------------------------------- keys

    /** 404 means "not yet" -- `ApiError.detail.reason` says why. */
    keysMine: () => request<LicenceKey>('/api/v1/keys/mine'),
    rotateMyKey: () => request<LicenceKey>('/api/v1/keys/mine/rotate', { method: 'POST' }),

    // ------------------------------------------------------------ payments

    submitPayment(input: PaymentInput) {
      const form = new FormData()
      form.set('plan', input.plan)
      form.set('method', input.method)
      form.set('amount', String(input.amount))
      form.set('currency', input.currency)
      form.set('reference', input.reference)
      form.set('proof', input.proof, input.proof.name)
      return request<Payment>('/api/v1/payments', { method: 'POST', body: form })
    },
    myPayments: () => request<Payment[]>('/api/v1/payments/mine'),

    /** The proof needs the bearer token, so it cannot be an `<img src>`. */
    async blob(path: string): Promise<Blob> {
      const headers = new Headers()
      if (access) headers.set('Authorization', `Bearer ${access}`)
      const res = await fetch(`${root}${path}`, { headers })
      if (!res.ok) throw new ApiError(res.status, 'Could not load the file.')
      return res.blob()
    },

    // ------------------------------------------------------------- tickets

    createTicket: (input: TicketInput) =>
      request<Ticket>('/api/v1/tickets', { method: 'POST', body: JSON.stringify(input), auth: true }),
    myTickets: () => request<Ticket[]>('/api/v1/tickets/mine'),

    // ------------------------------------------------------------ waitlist

    joinWaitlist: (email: string) =>
      request<void>('/api/v1/waitlist', { method: 'POST', body: JSON.stringify({ email }), auth: false }),

    // --------------------------------------------------------------- admin

    admin: {
      stats: () => request<Stats>('/api/v1/admin/stats'),
      users: (params: { status?: string; q?: string } = {}) => {
        const qs = new URLSearchParams()
        if (params.status) qs.set('status', params.status)
        if (params.q) qs.set('q', params.q)
        const suffix = qs.toString() ? `?${qs}` : ''
        return request<User[]>(`/api/v1/admin/users${suffix}`)
      },
      user: (id: number) => request<UserDetail>(`/api/v1/admin/users/${id}`),
      approve: (id: number) => request<ApproveResponse>(`/api/v1/admin/users/${id}/approve`, { method: 'POST' }),
      reject: (id: number, reason: string) =>
        request<User>(`/api/v1/admin/users/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
      suspend: (id: number) => request<User>(`/api/v1/admin/users/${id}/suspend`, { method: 'POST' }),
      reinstate: (id: number) => request<User>(`/api/v1/admin/users/${id}/reinstate`, { method: 'POST' }),
      setRole: (id: number, role: Role) =>
        request<User>(`/api/v1/admin/users/${id}/role`, { method: 'POST', body: JSON.stringify({ role }) }),
      setNote: (id: number, note: string) =>
        request<User>(`/api/v1/admin/users/${id}/note`, { method: 'POST', body: JSON.stringify({ note }) }),
      logoutAll: (id: number) => request<void>(`/api/v1/admin/users/${id}/logout-all`, { method: 'POST' }),
      rotateKey: (id: number) =>
        request<ApproveResponse>(`/api/v1/admin/users/${id}/keys/rotate`, { method: 'POST' }),
      promote: (email: string) =>
        request<User>('/api/v1/admin/promote', { method: 'POST', body: JSON.stringify({ email }) }),
      keys: () => request<KeySummary[]>('/api/v1/admin/keys'),
      revokeKey: (id: number) => request<KeySummary>(`/api/v1/admin/keys/${id}/revoke`, { method: 'POST' }),
      payments: () => request<Payment[]>('/api/v1/admin/payments'),
      tickets: () => request<Ticket[]>('/api/v1/admin/tickets'),
      reply: (id: number, body: string) =>
        request<Ticket>(`/api/v1/admin/tickets/${id}/reply`, { method: 'POST', body: JSON.stringify({ body }) }),
      closeTicket: (id: number) => request<Ticket>(`/api/v1/admin/tickets/${id}/close`, { method: 'POST' }),
      waitlist: () => request<WaitlistEntry[]>('/api/v1/admin/waitlist'),
      audit: () => request<AuditEntry[]>('/api/v1/admin/audit'),
    },
  }

  return api
}

export type Api = ReturnType<typeof createApi>
