'use client'

/**
 * Who is signed in, and what the server will show them.
 *
 * The first answer comes from the API client's own state: `bootstrap()` turns
 * a surviving refresh cookie into an access token on load, so a reload does
 * not sign anyone out and nothing is ever kept in `localStorage`.
 *
 * The second -- `release` -- is fetched, never inferred. The pre-release gate
 * is only real because the server refuses the data, and this file asking
 * rather than deciding is what keeps the client honest about that. It is
 * re-fetched whenever the signed-in user changes, because what the server
 * will show depends on who is asking.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { AuthState, Me, Release } from '@vision-hub/contracts'

import { api } from './api'

type SessionValue = AuthState & {
  release: Release
  /** Whether this visitor may see anything beyond the holding page. */
  canSeeSite: boolean
  signIn: (email: string, password: string) => Promise<Me>
  signUp: (email: string, password: string) => Promise<Me>
  signOut: () => Promise<void>
}

/** Closed until the server says otherwise -- the safe direction to fail. */
const CLOSED: Release = { is_public: false, can_preview: false }

const Ctx = createContext<SessionValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(api.state())
  const [release, setRelease] = useState<Release | null>(null)

  useEffect(() => {
    const off = api.subscribe(setAuth)
    void api.bootstrap()
    return off
  }, [])

  // `auth.ready` flips once bootstrap has settled; only then is the release
  // answer for the right person.
  useEffect(() => {
    if (!auth.ready) return
    let live = true
    api
      .release()
      .catch(() => CLOSED)
      .then((r) => live && setRelease(r))
    return () => {
      live = false
    }
  }, [auth.ready, auth.user?.id])

  const value = useMemo<SessionValue>(() => {
    const rel = release ?? CLOSED
    return {
      user: auth.user,
      ready: auth.ready && release !== null,
      release: rel,
      canSeeSite: rel.is_public || rel.can_preview,
      signIn: (email, password) => api.login(email, password),
      signUp: (email, password) => api.signup(email, password),
      signOut: () => api.logout(),
    }
  }, [auth, release])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSession(): SessionValue {
  const value = useContext(Ctx)
  if (!value) throw new Error('useSession must be used inside <SessionProvider>')
  return value
}
