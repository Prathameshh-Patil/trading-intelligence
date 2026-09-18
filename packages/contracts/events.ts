/**
 * The event stream, read over `fetch`.
 *
 * `EventSource` cannot send an `Authorization` header, and the stream is a
 * bearer-authenticated route like every other -- so this is a small SSE
 * parser over a streamed `fetch` body. It reconnects with backoff, resends
 * `Last-Event-ID`, and asks the API client to refresh the token when the
 * stream is refused with a 401.
 *
 * Nothing here is a source of truth. Every event is a nudge to re-fetch the
 * REST resource it names; a client that misses one loses a moment, not data.
 */

import { useEffect, useRef, useState } from 'react'

import type { Api } from './client'
import type { ServerEvent } from './types'

export type StreamStatus = 'connecting' | 'open' | 'closed'

export type SubscribeOptions = {
  onEvent: (event: ServerEvent) => void
  onStatus?: (status: StreamStatus) => void
}

const MIN_BACKOFF = 1_000
const MAX_BACKOFF = 30_000

export function subscribe(api: Api, path: string, opts: SubscribeOptions): () => void {
  let stopped = false
  let controller: AbortController | null = null
  let lastId: string | null = null
  let backoff = MIN_BACKOFF

  const status = (s: StreamStatus) => opts.onStatus?.(s)

  async function run() {
    while (!stopped) {
      const token = api.accessToken()
      if (!token) {
        status('closed')
        return
      }
      controller = new AbortController()
      status('connecting')
      try {
        const headers: Record<string, string> = {
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        }
        if (lastId) headers['Last-Event-ID'] = lastId
        const res = await fetch(`${api.base}${path}`, { headers, signal: controller.signal })
        if (res.status === 401) {
          // Token expired mid-stream. Refresh once; the loop retries.
          const ok = await api.bootstrap().then(() => api.accessToken() !== null)
          if (!ok) {
            status('closed')
            return
          }
          continue
        }
        if (!res.ok || !res.body) throw new Error(`stream ${res.status}`)

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let eventName = 'message'
        let data = ''

        for (;;) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          let nl: number
          while ((nl = buffer.indexOf('\n')) >= 0) {
            const line = buffer.slice(0, nl).replace(/\r$/, '')
            buffer = buffer.slice(nl + 1)
            if (line === '') {
              if (data !== '') {
                if (eventName === 'hello') {
                  backoff = MIN_BACKOFF
                  status('open')
                }
                if (eventName !== 'ping') {
                  let parsed: unknown = {}
                  try {
                    parsed = JSON.parse(data)
                  } catch {
                    parsed = {}
                  }
                  opts.onEvent({ type: eventName, data: parsed } as ServerEvent)
                }
              }
              eventName = 'message'
              data = ''
              continue
            }
            if (line.startsWith(':')) continue
            const colon = line.indexOf(':')
            const field = colon < 0 ? line : line.slice(0, colon)
            const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
            if (field === 'event') eventName = value
            else if (field === 'data') data += (data ? '\n' : '') + value
            else if (field === 'id') lastId = value
          }
        }
      } catch {
        if (stopped) return
      }
      status('connecting')
      await new Promise((r) => setTimeout(r, backoff))
      backoff = Math.min(MAX_BACKOFF, backoff * 2)
    }
  }

  void run()

  return () => {
    stopped = true
    controller?.abort()
    status('closed')
  }
}

/**
 * Subscribe for the life of a component. `handler` is kept in a ref so the
 * stream is not torn down every render; `enabled` lets a page wait for auth.
 */
export function useEvents(
  api: Api,
  path: string,
  handler: (event: ServerEvent) => void,
  enabled = true,
): StreamStatus {
  const [status, setStatus] = useState<StreamStatus>('closed')
  const latest = useRef(handler)
  latest.current = handler

  useEffect(() => {
    if (!enabled) {
      setStatus('closed')
      return
    }
    return subscribe(api, path, {
      onEvent: (e) => latest.current(e),
      onStatus: setStatus,
    })
  }, [api, path, enabled])

  return status
}
