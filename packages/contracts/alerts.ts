/**
 * Alerts, and the socket that delivers them.
 *
 * Three tiers, and the tier is the whole contract between the server and the
 * screen: the server says which one an alert is, the client decides what that
 * tier looks like (banner, badge, list, or nothing -- the trader's choice).
 * Nothing about the tier is a recommendation; `breaking` means "read this
 * now", not "trade this".
 *
 * The socket is authenticated by the licence key, not a JWT: an installed
 * client holds a `vh_live_` key and nothing else, and a browser `WebSocket`
 * cannot send headers, so the key travels in the first frame. Every other
 * frame is one of the shapes below and nothing else -- the client rejects
 * anything it does not recognise, and so does the server.
 */

import type { Tier } from './types'

export type AlertTier = 'breaking' | 'signal' | 'analysis'
export const ALERT_TIERS: readonly AlertTier[] = ['breaking', 'signal', 'analysis']

export type Alert = {
  id: number
  tier: AlertTier
  title: string
  body: string
  /** The instrument it is about, when it is about one. Free text, e.g. `XAUUSD`. */
  symbol: string | null
  created_at: string
  /** After this the alert is stale and is not replayed to a reconnecting client. */
  expires_at: string | null
}

/** What an admin sends to publish one. */
export type AlertIn = {
  tier: AlertTier
  title: string
  body: string
  symbol?: string | null
  expires_at?: string | null
}

/** Client -> server. */
export type SocketOut = { type: 'auth'; key: string } | { type: 'ping' }

/** Server -> client. */
export type SocketIn =
  | { type: 'hello'; tier: Tier; expires_at: string | null; server_time: string }
  | { type: 'alert'; alert: Alert }
  /** The key stopped being valid; the server closes with `SOCKET_CLOSE.KEY_INVALID` next. */
  | { type: 'key'; event: 'revoked' | 'rotated' }
  | { type: 'pong' }
  | { type: 'error'; reason: 'unauthenticated' | 'invalid_key' | 'rate_limited' | 'bad_message' }

export const SOCKET_PATH = '/api/v1/ws'

/** Close codes in the 4000-4999 application range. */
export const SOCKET_CLOSE = {
  KEY_INVALID: 4401,
  ORIGIN: 4403,
  AUTH_TIMEOUT: 4408,
  RATE_LIMITED: 4429,
} as const

/** `http(s)://host` -> `ws(s)://host/api/v1/ws`. */
export function socketUrl(apiBase: string): string {
  return apiBase.replace(/^http/, 'ws').replace(/\/+$/, '') + SOCKET_PATH
}
