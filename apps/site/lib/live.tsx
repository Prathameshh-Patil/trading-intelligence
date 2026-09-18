'use client'

/**
 * One event stream for the signed-in visitor.
 *
 * The provider subscribes to `/api/v1/events` -- the user's own channel --
 * once there is someone to subscribe for; pages register handlers. The stream
 * says *when* something changed (an approval, a ticket reply); the page then
 * re-fetches the REST resource, so what it shows is always the server's
 * answer rather than a reconstruction from event payloads.
 */

import { createContext, useContext, useEffect, useRef, type ReactNode } from 'react'
import { useEvents, type ServerEvent, type ServerEventType, type StreamStatus } from '@vision-hub/contracts'

import { api } from './api'
import { useSession } from './session'

type Handler = (e: ServerEvent) => void

const Ctx = createContext<{ status: StreamStatus; on: (h: Handler) => () => void }>({
  status: 'closed',
  on: () => () => {},
})

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useSession()
  const handlers = useRef(new Set<Handler>())
  const status = useEvents(
    api,
    '/api/v1/events',
    (e) => handlers.current.forEach((h) => h(e)),
    user !== null,
  )
  const on = (h: Handler) => {
    handlers.current.add(h)
    return () => handlers.current.delete(h)
  }
  return <Ctx.Provider value={{ status, on }}>{children}</Ctx.Provider>
}

export function useLiveStatus(): StreamStatus {
  return useContext(Ctx).status
}

/** Run `handler` for the listed event types (or all, when `types` is empty). */
export function useLive(types: ServerEventType[], handler: Handler) {
  const { on } = useContext(Ctx)
  const latest = useRef(handler)
  latest.current = handler
  const key = types.join(',')
  useEffect(
    () => on((e) => (types.length === 0 || types.includes(e.type)) && latest.current(e)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [on, key],
  )
}
