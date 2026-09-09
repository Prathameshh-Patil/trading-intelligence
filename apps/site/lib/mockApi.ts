/**
 * The fake backend, so the whole site is clickable with no server.
 *
 * `plans/team/contracts.md` states the pattern this follows: whoever owns a seam
 * ships the type and a fake on the first day, the consumer builds against the
 * fake, and the producer swaps in the real implementation behind the same type.
 * A fake returns realistic, varying, awkward data — not a stub returning null —
 * so the layout discovers today that it breaks on a seven-digit CVD rather than
 * in front of a paying subscriber.
 *
 * IT IS NOT A SECURITY BOUNDARY. Everything here runs in the visitor's own tab
 * against their own storage, so the release gate it implements demonstrates the
 * flow rather than enforcing it. The real gate is a session check in
 * `services/api`, and this file is deleted the day that lands.
 */

import type { PlanId } from '@/content/site'
import { ApiError } from './types'
import type {
  LicenceKey,
  Me,
  Payment,
  PaymentMethod,
  Release,
  Ticket,
  WaitlistEntry,
} from './types'

const STORAGE_KEY = 'ti_mock_v1'

/**
 * The two preview accounts.
 *
 * Committable only because this is the mock: there is no server behind it and
 * no data behind it but the visitor's own. The real accounts are created by a
 * command against `services/api` and their passwords never enter this repo.
 *
 * Two, not one, because they exercise different halves of the gate: signing in
 * as `DEV_ADMIN` gets past the release gate *and* into `/admin`; signing in as
 * `DEV_USER` gets past the release gate and nothing else — which is the
 * account to hand a teammate reviewing the site who has no business seeing the
 * payment queue.
 */
export const DEV_ADMIN = {
  email: 'admin@trading-intelligence.local',
  password: 'preview-only',
} as const

export const DEV_USER = {
  email: 'reviewer@trading-intelligence.local',
  password: 'preview-only',
} as const

type Db = {
  users: { id: string; email: string; password: string; role: 'user' | 'admin' }[]
  sessionUserId: string | null
  payments: Payment[]
  keys: (LicenceKey & { email: string })[]
  tickets: Ticket[]
  waitlist: WaitlistEntry[]
  isPublic: boolean
}

const seed = (): Db => ({
  users: [
    { id: 'u_admin', ...DEV_ADMIN, role: 'admin' },
    { id: 'u_reviewer', ...DEV_USER, role: 'user' },
  ],
  sessionUserId: null,
  payments: [],
  keys: [],
  tickets: [],
  waitlist: [],
  // Closed by default: a stranger with the link sees the holding page. Getting
  // past it takes an account — see `release()` below, not this flag. There is
  // deliberately no build-time escape hatch that opens the site to anyone with
  // the URL; if that is ever wanted again, it is a `DEV_*` account, not a flag
  // baked into a public build.
  isPublic: false,
})

let cache: Db | null = null

/**
 * Lazy, and never touched during server rendering.
 *
 * Next renders these modules on the server too, where `localStorage` does not
 * exist — reading it at module scope would crash the build rather than the page,
 * which is a confusing way to find out.
 */
function db(): Db {
  if (cache) return cache
  if (typeof window === 'undefined') {
    cache = seed()
    return cache
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    cache = raw ? { ...seed(), ...(JSON.parse(raw) as Partial<Db>) } : seed()
  } catch {
    // Private window, cleared site data, storage disabled. The site still works,
    // it just forgets — never let a storage failure blank the page.
    cache = seed()
  }
  return cache
}

function commit(): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db()))
  } catch {
    /* over quota or disabled — in-memory for this tab is good enough */
  }
}

/** Real networks are not instant, and a UI that only ever sees 0ms hides its own jank. */
const latency = () => new Promise((r) => setTimeout(r, 180 + Math.random() * 240))

const id = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 10)}`
const now = () => new Date().toISOString()

function currentUser(): Me | null {
  const u = db().users.find((x) => x.id === db().sessionUserId)
  return u ? { id: u.id, email: u.email, role: u.role } : null
}

function requireUser(): Me {
  const me = currentUser()
  if (!me) throw new ApiError(401, 'Sign in to continue.')
  return me
}

function requireAdmin(): Me {
  const me = requireUser()
  if (me.role !== 'admin') throw new ApiError(403, 'Admins only.')
  return me
}

/** `ti_live_` + exactly 32 characters, per S3 — the desktop app rejects anything else. */
function mintKey(): string {
  const alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let body = ''
  for (let i = 0; i < 32; i += 1) body += alphabet[Math.floor(Math.random() * alphabet.length)]
  return `ti_live_${body}`
}

export const mockApi = {
  async release(): Promise<Release> {
    await latency()
    // Any signed-in account gets past the gate, not only an admin. Pre-release
    // access is "you were given a login", not "you are staff" — a teammate
    // reviewing the site signs in as a plain user and never sees /admin, which
    // stays behind its own role check.
    return { isPublic: db().isPublic, canPreview: Boolean(currentUser()) }
  },

  async setPublic(isPublic: boolean): Promise<Release> {
    await latency()
    requireAdmin()
    db().isPublic = isPublic
    commit()
    return { isPublic, canPreview: true }
  },

  async me(): Promise<Me | null> {
    await latency()
    return currentUser()
  },

  async signup(email: string, password: string): Promise<Me> {
    await latency()
    const clean = email.trim().toLowerCase()
    if (db().users.some((u) => u.email === clean)) {
      throw new ApiError(409, 'An account with that email already exists.')
    }
    const user = { id: id('u'), email: clean, password, role: 'user' as const }
    db().users.push(user)
    db().sessionUserId = user.id
    commit()
    return { id: user.id, email: user.email, role: user.role }
  },

  async login(email: string, password: string): Promise<Me> {
    await latency()
    const clean = email.trim().toLowerCase()
    const user = db().users.find((u) => u.email === clean && u.password === password)
    // One message for both branches: "no such account" tells a stranger which
    // addresses are registered.
    if (!user) throw new ApiError(401, 'That email and password do not match.')
    db().sessionUserId = user.id
    commit()
    return { id: user.id, email: user.email, role: user.role }
  },

  async logout(): Promise<void> {
    await latency()
    db().sessionUserId = null
    commit()
  },

  async submitPayment(input: {
    plan: PlanId
    method: PaymentMethod
    amount: number
    currency: 'usd' | 'inr'
    reference: string
    proofName: string
    proofUrl: string
  }): Promise<Payment> {
    await latency()
    const me = requireUser()
    const payment: Payment = {
      id: id('pay'),
      email: me.email,
      ...input,
      status: 'pending',
      rejectionReason: null,
      createdAt: now(),
      reviewedAt: null,
    }
    db().payments.unshift(payment)
    commit()
    return payment
  },

  async myPayments(): Promise<Payment[]> {
    await latency()
    const me = requireUser()
    return db().payments.filter((p) => p.email === me.email)
  },

  /** S5's exit door: the key, or a 404 meaning "not yet" — never an error. */
  async keysMine(): Promise<LicenceKey> {
    await latency()
    const me = requireUser()
    const found = db().keys.find((k) => k.email === me.email)
    if (!found) throw new ApiError(404, 'No key yet.')
    return { key: found.key, tier: found.tier, created_at: found.created_at }
  },

  async adminPayments(): Promise<Payment[]> {
    await latency()
    requireAdmin()
    return db().payments
  },

  /**
   * Idempotent on the payment, not on the click.
   *
   * S5's rule was "webhooks arrive twice — the handler is idempotent or it issues
   * two keys and bills once". Manual approval has the same failure with a
   * different trigger: two admins with the queue open, or one double-click. So
   * approving an already-approved payment returns the key that exists.
   */
  async approvePayment(paymentId: string): Promise<LicenceKey> {
    await latency()
    requireAdmin()
    const payment = db().payments.find((p) => p.id === paymentId)
    if (!payment) throw new ApiError(404, 'No such payment.')

    const existing = db().keys.find((k) => k.email === payment.email)
    if (existing) {
      payment.status = 'approved'
      payment.reviewedAt = payment.reviewedAt ?? now()
      commit()
      return { key: existing.key, tier: existing.tier, created_at: existing.created_at }
    }

    const minted = { key: mintKey(), tier: payment.plan, created_at: now(), email: payment.email }
    db().keys.push(minted)
    payment.status = 'approved'
    payment.reviewedAt = now()
    commit()
    return { key: minted.key, tier: minted.tier, created_at: minted.created_at }
  },

  async rejectPayment(paymentId: string, reason: string): Promise<Payment> {
    await latency()
    requireAdmin()
    const payment = db().payments.find((p) => p.id === paymentId)
    if (!payment) throw new ApiError(404, 'No such payment.')
    payment.status = 'rejected'
    payment.rejectionReason = reason
    payment.reviewedAt = now()
    commit()
    return payment
  },

  async createTicket(input: {
    email: string
    category: string
    subject: string
    body: string
  }): Promise<Ticket> {
    await latency()
    const ticket: Ticket = {
      id: id('tkt'),
      ref: `TI-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
      ...input,
      email: input.email.trim().toLowerCase(),
      status: 'open',
      createdAt: now(),
      replies: [],
    }
    db().tickets.unshift(ticket)
    commit()
    return ticket
  },

  async myTickets(): Promise<Ticket[]> {
    await latency()
    const me = requireUser()
    return db().tickets.filter((t) => t.email === me.email)
  },

  async adminTickets(): Promise<Ticket[]> {
    await latency()
    requireAdmin()
    return db().tickets
  },

  async replyToTicket(ticketId: string, body: string): Promise<Ticket> {
    await latency()
    requireAdmin()
    const ticket = db().tickets.find((t) => t.id === ticketId)
    if (!ticket) throw new ApiError(404, 'No such ticket.')
    ticket.replies.push({ id: id('rep'), body, createdAt: now() })
    ticket.status = 'answered'
    commit()
    return ticket
  },

  async closeTicket(ticketId: string): Promise<Ticket> {
    await latency()
    requireAdmin()
    const ticket = db().tickets.find((t) => t.id === ticketId)
    if (!ticket) throw new ApiError(404, 'No such ticket.')
    ticket.status = 'closed'
    commit()
    return ticket
  },

  async joinWaitlist(email: string): Promise<void> {
    await latency()
    const clean = email.trim().toLowerCase()
    if (!db().waitlist.some((w) => w.email === clean)) {
      db().waitlist.push({ email: clean, createdAt: now() })
      commit()
    }
  },

  async waitlist(): Promise<WaitlistEntry[]> {
    await latency()
    requireAdmin()
    return db().waitlist
  },
}
