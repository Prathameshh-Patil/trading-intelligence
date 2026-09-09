/**
 * The wire shapes the site speaks.
 *
 * Two are fixed by an existing contract (`plans/team/contracts.md`) and are
 * copied here rather than invented, because a desktop application already reads
 * them: `LicenceKey` is S5's `GET /api/v1/keys/mine` response, and `Tier` is
 * S3's `tier` field. Changing either means changing that file first.
 *
 * Everything else is new. S5 assumed a payment-processor webhook and there is no
 * processor — a buyer pays on UPI or in USDT, uploads proof, and a human
 * approves it. That replaces the webhook with a person and leaves S5's exit door
 * exactly as frozen.
 */

import type { PlanId } from '@/content/site'

/** Exactly these two values exist. */
export type Tier = 'core' | 'core_journal'

/** Frozen: `key` is `ti_live_` followed by exactly 32 characters. */
export type LicenceKey = {
  key: string
  tier: Tier
  created_at: string
}

export type Role = 'user' | 'admin'

export type Me = {
  id: string
  email: string
  role: Role
}

/**
 * What the server will show this visitor.
 *
 * `isPublic` is the release switch. `canPreview` is whether THIS session may see
 * the pre-release pages regardless — true for any signed-in account, not only
 * an admin, because pre-release access is granted by having a login at all.
 * The client never decides `canPreview`; it asks. A flag compiled into a
 * bundle is a flag anyone can read.
 */
export type Release = {
  isPublic: boolean
  canPreview: boolean
}

export type PaymentMethod = 'upi' | 'usdt'
export type PaymentStatus = 'pending' | 'approved' | 'rejected'

export type Payment = {
  id: string
  email: string
  plan: PlanId
  method: PaymentMethod
  amount: number
  currency: 'usd' | 'inr'
  /** UPI transaction id, or the USDT transaction hash. */
  reference: string
  proofName: string
  /** Data URL in the mock; a served file URL against the real API. */
  proofUrl: string
  status: PaymentStatus
  /** Shown verbatim to the buyer, so it is written for them. */
  rejectionReason: string | null
  createdAt: string
  reviewedAt: string | null
}

export type TicketStatus = 'open' | 'answered' | 'closed'

export type TicketReply = {
  id: string
  body: string
  createdAt: string
}

export type Ticket = {
  id: string
  /** Short and quotable on a phone call, e.g. TI-4F2A. */
  ref: string
  email: string
  category: string
  subject: string
  body: string
  status: TicketStatus
  createdAt: string
  replies: TicketReply[]
}

export type WaitlistEntry = {
  email: string
  createdAt: string
}

/** `status` lets callers branch on 404, which is a real answer here, not a failure. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
