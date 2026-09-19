/**
 * The two calls a client makes with a licence key and nothing else.
 *
 * Neither goes through `createApi`: that client owns a signed-in user's JWT
 * lifecycle, and an installed app has no user, no cookie and no JWT -- it has
 * a `vh_live_` key in the OS keychain (desktop) or extension storage. The key
 * goes in `X-API-Key` and the server answers with S3's shape.
 *
 * Both THROW when there was no answer -- a network failure, a 5xx, a body
 * that is not the contract -- and RETURN the server's answer otherwise,
 * including `valid: false`. The caller decides what "no answer" means (the
 * offline grace in `@vision-hub/core`); these functions do not guess.
 */

import type { Alert } from './alerts'
import type { ValidateResponse } from './types'

const strip = (base: string) => base.replace(/\/+$/, '')

/** S3: `POST /api/v1/keys/validate`. `valid: false` is a 200, not a 401. */
export async function validateKey(
  apiBase: string,
  key: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ValidateResponse> {
  const r = await fetchImpl(`${strip(apiBase)}/api/v1/keys/validate`, {
    method: 'POST',
    headers: { 'X-API-Key': key },
  })
  if (!r.ok) throw new Error(`key service answered ${r.status}`)
  const body = (await r.json()) as Partial<ValidateResponse>
  if (typeof body.valid !== 'boolean') throw new Error('key service answered with the wrong shape')
  return body as ValidateResponse
}

/**
 * Alerts newer than `sinceId`, oldest first, unexpired. The reconnect
 * catch-up: the socket has no replay, so a client that was away asks for
 * what it missed by id before listening again.
 */
export async function alertsSince(
  apiBase: string,
  key: string,
  sinceId: number,
  fetchImpl: typeof fetch = fetch,
): Promise<Alert[]> {
  const r = await fetchImpl(`${strip(apiBase)}/api/v1/alerts?since=${sinceId}`, {
    headers: { 'X-API-Key': key },
  })
  if (r.status === 401) throw new KeyRejected()
  if (!r.ok) throw new Error(`alerts answered ${r.status}`)
  const body = (await r.json()) as unknown
  if (!Array.isArray(body)) throw new Error('alerts answered with the wrong shape')
  return body as Alert[]
}

/** The server said the key is not good any more -- distinct from "could not reach it". */
export class KeyRejected extends Error {
  constructor() {
    super('licence key rejected')
    this.name = 'KeyRejected'
  }
}
