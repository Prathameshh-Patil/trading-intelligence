'use client'

/**
 * Lenis, wired to GSAP's ticker.
 *
 * The rule from the brief, and the reason this file is so small: **smooth, never
 * hijacked.** Lenis eases the native scroll and nothing more — it does not trap
 * the reader in a section, does not fake momentum, and does not change how far
 * the page actually is. A site that lies about its own length is the fastest way
 * to make a stranger distrust it, which is the opposite of this site's job.
 *
 * Two things must be true or scrubbed sections drift out of sync: Lenis has to
 * be driven by GSAP's ticker rather than its own rAF loop, and ScrollTrigger has
 * to be told to update on every Lenis frame.
 */

import { useEffect } from 'react'

import { prefersReducedMotion } from '@/lib/motion'

export function SmoothScroll() {
  useEffect(() => {
    // Smoothing is motion. Somebody who asked for less of it gets the plain
    // native scroll, which is also the one their assistive tech expects.
    if (prefersReducedMotion()) return

    let destroy = () => {}
    let cancelled = false

    void (async () => {
      const [{ default: Lenis }, { gsap }, { ScrollTrigger }] = await Promise.all([
        import('lenis'),
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ])
      if (cancelled) return
      gsap.registerPlugin(ScrollTrigger)

      const lenis = new Lenis({ duration: 1.05, smoothWheel: true })

      lenis.on('scroll', ScrollTrigger.update)

      const tick = (time: number) => lenis.raf(time * 1000)
      gsap.ticker.add(tick)
      gsap.ticker.lagSmoothing(0)

      destroy = () => {
        gsap.ticker.remove(tick)
        lenis.destroy()
      }
    })()

    return () => {
      cancelled = true
      destroy()
    }
  }, [])

  return null
}
