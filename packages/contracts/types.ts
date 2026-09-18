/**
 * The wire shapes `services/api` speaks. Mirrored by `app/schemas/__init__.py`
 * -- change both.
 *
 * `LicenceKey` and `Tier` are fixed by `plans/team/contracts.md` (S3/S5) and a
 * desktop application reads them; the rest is this backend's own surface.
 */

export type Role = 'user' | 'admin'
export type Status = 'pending' | 'approved' | 'rejected' | 'suspended'
export type Tier = 'core' | 'core_journal'

export type Me = {
  id: number
  email: string
  role: Role
  status: Status
  created_at: string
}

export type AuthResponse = {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: Me
}

export type SessionInfo = {
  family_id: string
  created_at: string
  last_used_at: string | null
  user_agent: string | null
  ip: string | null
  current: boolean
}

export type Release = {
  is_public: boolean
  can_preview: boolean
}

/** Frozen: `key` is `vh_live_` followed by exactly 32 characters. */
export type LicenceKey = {
  key: string
  tier: Tier
  created_at: string
}

/** Has the desktop app ever validated the key? Own route, so S5's shape stays frozen. */
export type Activation = {
  activated: boolean
  last_validated_at: string | null
}

/** S3: `valid: false` is a 200. */
export type ValidateResponse =
  | { valid: true; tier: Tier; expires_at: string | null; reason: null }
  | { valid: false; tier: null; expires_at: null; reason: 'expired' | 'revoked' | 'unknown' }

export type PaymentMethod = 'upi' | 'usdt'
export type PaymentStatus = 'pending' | 'approved' | 'rejected'

export type Payment = {
  id: number
  user_id: number
  email: string
  plan: Tier
  method: PaymentMethod
  amount: number
  currency: 'usd' | 'inr'
  reference: string
  proof_name: string
  /** Relative to the API base; needs the bearer token -- fetch as a blob. */
  proof_url: string
  status: PaymentStatus
  rejection_reason: string | null
  created_at: string
  reviewed_at: string | null
}

export type TicketStatus = 'open' | 'answered' | 'closed'

export type TicketReply = {
  id: number
  body: string
  created_at: string
  from_staff: boolean
}

export type Ticket = {
  id: number
  /** Short and quotable on a phone call, e.g. VH-4F2A. */
  ref: string
  email: string
  category: string
  subject: string
  body: string
  status: TicketStatus
  created_at: string
  replies: TicketReply[]
}

export type WaitlistEntry = {
  email: string
  created_at: string
}

export type KeySummary = {
  id: number
  user_id: number
  email: string
  prefix: string
  tier: Tier
  status: 'active' | 'revoked'
  created_at: string
  expires_at: string | null
  revoked_at: string | null
  last_validated_at: string | null
}

export type User = {
  id: number
  email: string
  role: Role
  status: Status
  created_at: string
  last_login_at: string | null
  approved_at: string | null
  approved_by: string | null
  rejection_reason: string | null
  admin_note: string | null
  key: KeySummary | null
  payments_count: number
  open_tickets: number
}

export type UserDetail = User & {
  payments: Payment[]
  tickets: Ticket[]
  sessions: SessionInfo[]
}

export type ApproveResponse = {
  user: User
  key: LicenceKey
  minted: boolean
}

export type Stats = {
  pending: number
  approved: number
  rejected: number
  suspended: number
  active_keys: number
  validations_24h: number
  open_tickets: number
  waitlist: number
  signups_7d: number
  live_admins: number
}

export type AuditEntry = {
  id: number
  actor: string | null
  action: string
  target_type: string
  target_id: string
  detail: Record<string, unknown> | null
  ip: string | null
  created_at: string
}

/** What comes down the event stream. `hello` opens every stream. */
export type ServerEvent =
  | { type: 'hello'; data: Record<string, never> }
  | { type: 'user.signed_up'; data: { user_id: number; email: string } }
  | { type: 'user.approved'; data: UserEventData & { prefix: string } }
  | { type: 'user.rejected'; data: UserEventData & { reason: string } }
  | { type: 'user.suspended'; data: UserEventData }
  | { type: 'user.reinstated'; data: UserEventData }
  | { type: 'user.role_changed'; data: UserEventData & { role: Role } }
  | { type: 'key.rotated'; data: { prefix: string; user_id?: number; email?: string } }
  | { type: 'key.revoked'; data: UserEventData & { prefix: string } }
  | { type: 'key.activated'; data: { prefix: string; at: string } }
  | { type: 'payment.submitted'; data: { user_id: number; email: string; payment_id: number } }
  | { type: 'ticket.created'; data: { ticket_id: number; ref: string; email: string } }
  | { type: 'ticket.replied'; data: { ticket_id: number; ref: string; by?: string } }
  | { type: 'ticket.closed'; data: { ticket_id: number; ref: string; by?: string } }
  | { type: 'release.changed'; data: { is_public: boolean; by: string } }
  | { type: 'waitlist.joined'; data: { email: string } }

type UserEventData = { user_id: number; email: string; status: Status }

export type ServerEventType = ServerEvent['type']

/** `status` lets callers branch on 404, which is a real answer here, not a failure. */
export class ApiError extends Error {
  status: number
  detail: Record<string, unknown> | null
  constructor(status: number, message: string, detail: Record<string, unknown> | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}
