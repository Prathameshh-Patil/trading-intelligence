'use client'

/**
 * Who is signed in, from the API client's own state. `bootstrap()` turns a
 * surviving refresh cookie into an access token on load, so a reload does not
 * bounce an admin to the login page.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { AuthState } from '@vision-hub/contracts'

import { api } from './api'

const Ctx = createContext<AuthState>({ user: null, ready: false })

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(api.state())

  useEffect(() => {
    const off = api.subscribe(setState)
    void api.bootstrap()
    return off
  }, [])

  const value = useMemo(() => state, [state])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSession() {
  return useContext(Ctx)
}
