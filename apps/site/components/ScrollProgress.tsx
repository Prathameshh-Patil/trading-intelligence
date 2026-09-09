'use client'

/**
 * A thin gradient bar showing how far down the page you are.
 *
 * The landing page is long and three of its sections consume extra scroll to
 * play — exactly the situation where a reader starts wondering how much more
 * there is. This answers that without them having to ask.
 */

import { useEffect, useRef } from 'react'

export function ScrollProgress() {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const update = () => {
      const el = ref.current
      if (!el) return
      const max = document.documentElement.scrollHeight - window.innerHeight
      el.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`
    }

    // No requestAnimationFrame gate, on purpose. The obvious version keeps a
    // pending-frame flag and skips while one is in flight — but if that frame
    // never runs (a backgrounded tab throttles rAF to nothing) the flag stays
    // set and the bar is dead for the rest of the session. The work here is a
    // single compositor-only transform write, which is cheaper than the
    // bookkeeping that would guard it.
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update, { passive: true })
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [])

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-50 h-[2px]" aria-hidden>
      <div ref={ref} className="grad h-full origin-left scale-x-0" />
    </div>
  )
}
