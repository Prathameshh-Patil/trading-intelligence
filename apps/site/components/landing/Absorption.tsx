'use client'

/**
 * One example, in full — and the most legible one the product has.
 *
 * Size piles into a level while the price line refuses to move, and at the end
 * the candle that would be drawn over it fades in: small, red, unremarkable. The
 * numbers in the caption are computed from the same constants the drawing uses,
 * so the picture and the sentence can never drift apart.
 */

import { useCallback, useEffect, useRef } from 'react'

import { Eyebrow } from '../ui'
import { ABSORPTION } from '@/content/site'
import { fitCanvas, useScrubber } from '@/lib/motion'
import { clamp01, mulberry32, phase } from '@/lib/rng'

const BARS = 26
const SIZES = (() => {
  const rand = mulberry32(1940)
  return Array.from({ length: BARS }, () => 0.35 + rand() * 0.65)
})()

const PRICE_WOBBLE = (() => {
  const rand = mulberry32(303)
  return Array.from({ length: 120 }, () => (rand() - 0.5) * 0.04)
})()

export function Absorption() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const progress = useRef(0)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const fitted = fitCanvas(canvas)
    if (!fitted) return

    const { ctx, w, h } = fitted
    const p = progress.current
    ctx.clearRect(0, 0, w, h)

    const level = h * 0.46
    const fill = phase(p, 0, 0.72)

    // ── the level itself ──────────────────────────────────────────────────
    ctx.strokeStyle = 'rgba(255,255,255,0.10)'
    ctx.setLineDash([4, 5])
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(0, level)
    ctx.lineTo(w, level)
    ctx.stroke()
    ctx.setLineDash([])

    // ── size arriving at it, sell-side, accumulating downward ─────────────
    const barW = (w * 0.62) / BARS
    for (let i = 0; i < BARS; i += 1) {
      const arrived = clamp01((fill * BARS - i) * 1.6)
      if (arrived <= 0) continue
      const height = SIZES[i] * 104 * arrived
      ctx.fillStyle = '#f87171'
      ctx.globalAlpha = 0.28 + arrived * 0.5
      ctx.fillRect(w * 0.06 + i * barW, level + 2, barW - 2, height)
    }
    ctx.globalAlpha = 1

    // ── price, refusing to move ───────────────────────────────────────────
    ctx.strokeStyle = '#a78bfa'
    ctx.lineWidth = 2.5
    ctx.beginPath()
    const shown = Math.max(2, Math.floor(PRICE_WOBBLE.length * clamp01(p * 1.15)))
    for (let i = 0; i < shown; i += 1) {
      const x = (i / (PRICE_WOBBLE.length - 1)) * w * 0.68 + w * 0.06
      const y = level - 62 + PRICE_WOBBLE[i] * h
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()

    // The flat line is the surprising half of this picture and reads as an axis
    // without a word next to it.
    if (p > 0.25) {
      ctx.globalAlpha = Math.min(1, (p - 0.25) * 4)
      ctx.fillStyle = '#8b5cf6'
      ctx.font = '11px ui-monospace, monospace'
      ctx.textAlign = 'left'
      ctx.fillText('price — barely moves', w * 0.06, level - 76)
      ctx.globalAlpha = 1
    }

    // ── and the candle drawn over all of it ───────────────────────────────
    const candle = phase(p, 0.76, 1)
    if (candle > 0.02) {
      const x = w * 0.86
      ctx.globalAlpha = candle
      ctx.strokeStyle = '#5b6070'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.moveTo(x, level - 52)
      ctx.lineTo(x, level - 8)
      ctx.stroke()
      ctx.fillStyle = '#f87171'
      ctx.fillRect(x - 13, level - 42, 26, 26)

      ctx.globalAlpha = candle * 0.75
      ctx.fillStyle = '#6b7285'
      ctx.font = '11px ui-monospace, monospace'
      ctx.textAlign = 'center'
      ctx.fillText('the candle', x, level + 12)
    }
    ctx.globalAlpha = 1
  }, [])

  const ref = useScrubber<HTMLDivElement>({
    onProgress: (value) => {
      progress.current = value
      draw()
    },
    end: '+=130%',
  })

  useEffect(() => {
    draw()
    const onResize = () => draw()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [draw])

  return (
    <section ref={ref} className="relative mx-auto max-w-[1200px] px-6 py-24">
      <Eyebrow>{ABSORPTION.eyebrow}</Eyebrow>
      <h2 className="mt-4 max-w-[20ch] text-[clamp(2rem,4.2vw,3rem)] font-semibold">
        {ABSORPTION.title}
      </h2>

      {/* Framed like a panel in the app rather than floating on the page —
          a drawing with no edges reads as an unfinished section. */}
      <figure className="surface mt-10 overflow-hidden rounded-2xl">
        <figcaption className="num flex items-center justify-between border-b border-white/[0.08] px-4 py-2.5 text-[11px] text-faint">
          <span>GCZ6 · 2418.40 · 90 seconds</span>
          <span>sell-side absorption</span>
        </figcaption>
        <div className="px-4 py-3">
          <canvas
            ref={canvasRef}
            className="h-[300px] w-full sm:h-[350px]"
            role="img"
            aria-label="Sell size accumulating into one price level while the price line stays flat, and the small red candle that gets drawn over it."
          />
        </div>
      </figure>

      <p className="num mt-8 max-w-[58ch] text-[15px] text-dim">{ABSORPTION.caption}</p>
    </section>
  )
}
