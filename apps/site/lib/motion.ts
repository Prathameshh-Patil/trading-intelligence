'use client'

/**
 * The two motion primitives the site uses, and nothing else.
 *
 *   `useReveal`   — entry reveals. Plain IntersectionObserver, no library.
 *   `useScrubber` — ties a callback to scroll position through GSAP ScrollTrigger.
 *
 * Reveals do not need GSAP and are far cheaper without it, so the dependency is
 * spent only where it earns itself: the three scrubbed data sequences and the
 * one pinned section, which is work an observer genuinely cannot do.
 *
 * Both honour `prefers-reduced-motion` by jumping to the final state — not by
 * running a shorter animation. Reduced motion means the end frame, immediately.
 */

import { useEffect, useRef, type RefObject } from 'react'

export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Adds `.is-in` when the element enters the viewport, once.
 *
 * The element is styled and readable before this fires — `.reveal` only offsets
 * and fades it — so a failed script, a crawler or a slow device still sees a
 * complete page. Nothing is revealed *by* animation.
 */
export function useReveal<T extends HTMLElement>(options?: {
  /** Stagger children matching this selector instead of the element itself. */
  childSelector?: string
  stepMs?: number
}): RefObject<T | null> {
  const ref = useRef<T | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const targets: HTMLElement[] = options?.childSelector
      ? Array.from(el.querySelectorAll<HTMLElement>(options.childSelector))
      : [el]

    if (prefersReducedMotion()) {
      targets.forEach((t) => t.classList.add('is-in'))
      return
    }

    targets.forEach((t) => t.classList.add('reveal'))

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          const index = targets.indexOf(entry.target as HTMLElement)
          const delay = index > 0 ? index * (options?.stepMs ?? 70) : 0
          window.setTimeout(() => entry.target.classList.add('is-in'), delay)
          observer.unobserve(entry.target)
        })
      },
      // Fire a little before the element is fully on screen, so the movement has
      // finished by the time the reader's eye arrives at it.
      { rootMargin: '0px 0px -12% 0px', threshold: 0.08 },
    )

    targets.forEach((t) => observer.observe(t))
    return () => observer.disconnect()
  }, [options?.childSelector, options?.stepMs])

  return ref
}

type ScrubOptions = {
  /** Called with 0→1 as the trigger travels its scroll distance. */
  onProgress: (progress: number) => void
  /** How much scroll the sequence occupies. Default: one extra viewport. */
  end?: string
  /**
   * Where the sequence begins. Default `top 75%` — a quarter of the way up the
   * viewport, so a scrubbed drawing has started by the time it is properly in
   * view. **A pinned trigger must use `top top` instead**: pinning from part-way
   * down the viewport strands the pin spacer above the section, which reads as a
   * screen and a half of dead space.
   */
  start?: string
  /** Pin the trigger while it plays. */
  pin?: boolean
}

/**
 * Drives a callback from scroll position.
 *
 * Deliberately does NOT animate anything itself — it hands out a number and the
 * caller decides what that means. The three data sequences paint to canvas from
 * it, which keeps hundreds of trade marks off the DOM.
 *
 * GSAP is imported dynamically because it touches `window` at module scope, and
 * this app server-renders every page it appears on.
 */
export function useScrubber<T extends HTMLElement>(options: ScrubOptions): RefObject<T | null> {
  const ref = useRef<T | null>(null)
  const onProgress = useRef(options.onProgress)
  onProgress.current = options.onProgress

  useEffect(() => {
    const el = ref.current
    if (!el) return

    // Reduced motion gets the finished picture rather than an empty canvas.
    if (prefersReducedMotion()) {
      onProgress.current(1)
      return
    }

    let cleanup = () => {}
    let cancelled = false

    void (async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ])
      if (cancelled) return
      gsap.registerPlugin(ScrollTrigger)

      const trigger = ScrollTrigger.create({
        trigger: el,
        start: options.start ?? 'top 75%',
        end: options.end ?? '+=100%',
        pin: options.pin ?? false,
        scrub: 0.6,
        onUpdate: (self) => onProgress.current(self.progress),
        onRefresh: (self) => onProgress.current(self.progress),
      })

      cleanup = () => trigger.kill()
    })()

    return () => {
      cancelled = true
      cleanup()
    }
  }, [options.end, options.pin, options.start])

  return ref
}

/**
 * Canvas sizing that survives retina and resize.
 *
 * Every sequence needs this and getting it wrong is the difference between crisp
 * and slightly blurry, which on a site arguing for precision is worse than it
 * sounds.
 */
export function fitCanvas(canvas: HTMLCanvasElement): { w: number; h: number; ctx: CanvasRenderingContext2D } | null {
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const rect = canvas.getBoundingClientRect()
  canvas.width = Math.round(rect.width * dpr)
  canvas.height = Math.round(rect.height * dpr)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return { w: rect.width, h: rect.height, ctx }
}
