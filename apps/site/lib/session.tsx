'use client'

/**
 * Who is signed in, and what the server will show them.
 *
 * Both answers are fetched on every load, never inferred. `canPreview` in
 * particular is the server's word: the pre-release gate is only real because the
 * server refuses the data, and this file asking rather than deciding is what
 * keeps the client honest about that.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { api } from './api'
import type { Me, Release } from './types'

type SessionValue = {
  me: Me | null
  release: Release
  loading: boolean
  /** Whether this visitor may see anything beyond the holding page. */
  canSeeSite: boolean
  signIn: (email: string, password: string) => Promise<Me>
  signUp: (email: string, password: string) => Promise<Me>
  signOut: () => Promise<void>
  refresh: () => Promise<void>
}

const SessionContext = createContext<SessionValue | null>(null)

/** Closed until the server says otherwise — the safe direction to fail. */
const CLOSED: Release = { isPublic: false, canPreview: false }

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [release, setRelease] = useState<Release>(CLOSED)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    // Order matters: what the server will show depends on who is asking.
    const who = await api.me().catch(() => null)
    setMe(who)
    setRelease(await api.release().catch(() => CLOSED))
  }, [])

  useEffect(() => {
    void refresh().finally(() => setLoading(false))
  }, [refresh])

  const signIn = useCallback(
    async (email: string, password: string) => {
      const who = await api.login(email, password)
      await refresh()
      return who
    },
    [refresh],
  )

  const signUp = useCallback(
    async (email: string, password: string) => {
      const who = await api.signup(email, password)
      await refresh()
      return who
    },
    [refresh],
  )

  const signOut = useCallback(async () => {
    await api.logout()
    await refresh()
  }, [refresh])

  const value = useMemo<SessionValue>(
    () => ({
      me,
      release,
      loading,
      canSeeSite: release.isPublic || release.canPreview,
      signIn,
      signUp,
      signOut,
      refresh,
    }),
    [me, release, loading, signIn, signUp, signOut, refresh],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside <SessionProvider>')
  return value
}
