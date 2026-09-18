import { createApi } from '@vision-hub/contracts'

/**
 * `NEXT_PUBLIC_API_BASE` is the one deployment setting this app has. It is
 * baked in at build time; a build without it is a build that talks to a local
 * API, which is only ever right on a developer machine.
 */
const BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')

if (!BASE && typeof window !== 'undefined') {
  console.error('NEXT_PUBLIC_API_BASE is not set; every request will fail.')
}

export const api = createApi(BASE)
