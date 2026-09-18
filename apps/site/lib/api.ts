import { createApi } from '@vision-hub/contracts'

/**
 * The one place the site talks to a server.
 *
 * `NEXT_PUBLIC_API_BASE` decides which server, and it is baked in at build
 * time. Unset in development it falls back to a local `services/api`; unset in
 * a production build it is a misconfiguration, and the console says so rather
 * than the pages quietly failing one fetch at a time.
 *
 * Everything about tokens -- the in-memory access token, the silent refresh on
 * load, the one retry on 401, the cross-tab sign-out -- lives in the client
 * from `@vision-hub/contracts`. No page here ever sees a token.
 */
const BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')

if (!BASE && typeof window !== 'undefined') {
  console.error('NEXT_PUBLIC_API_BASE is not set; every request will fail.')
}

export const api = createApi(BASE)
