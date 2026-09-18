'use client'

import { useRouter } from 'next/navigation'
import { useEffect, type ReactNode } from 'react'

import { useSession } from '@/lib/session'

/** Pages wrap themselves in this so a signed-out visit lands on /login. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, ready } = useSession()
  const router = useRouter()
  useEffect(() => {
    if (ready && !user) router.replace('/login')
  }, [ready, user, router])
  if (!ready || !user || user.role !== 'admin') return null
  return <>{children}</>
}
