'use client'

/**
 * The claim that cannot be argued with.
 *
 * Two panels, and the candle in each is drawn from **one shared geometry
 * object** — not two similar ones. That is deliberate: if the two candles were
 * generated separately they could drift apart by a pixel under some rounding,
 * and the entire point is that they are identical. The cumulative-delta lines
 * beneath them are what differ, and the scroll draws them apart.
 */

import { useCallback, useEffect, useRef } from 'react'

import { Eyebrow } from '../ui'
import { TWO_CANDLES } from '@/content/site'
import { fitCanvas, useScrubber } from '@/lib/motion'
import { clamp01, mulberry32 } from '@/lib/rng'

/** One candle. Both panels render this exact object. */
const CANDLE = { open: 0.62, close: 0.44, high: 0.3, low: 0.78 }

const POINTS = 90

function cvdPath(seed: number, direction: 1 | -1): number[] {
  const rand = mulberry32(seed)
  let value = 0
  return Array.from({ length: POINTS }, (_, i) => {
    // Drift in the given direction with real noise on top, so neither line looks
    // like a drawn arrow. The last point is what the reader compares.
    value += direction * (0.4 + rand() * 0.9) + (rand() - 0.5) * 1.6
    return value * (0.5 + (i / POINTS) * 0.5)
  })
}

const LINES = {
  left: cvdPath(4218, 1),
  right: cvdPath(612, -1),
}

function drawPanel(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  series: number[],
  progress: number,
  colour: string,
) {
  ctx.clearRect(0, 0, w, h)

  const candleZone = h * 0.42
  const centre = w / 2
  const width = 30

  // ── the candle: identical in both panels, and always fully drawn ──────────
  ctx.strokeStyle = '#5b6070'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(centre, CANDLE.high * candleZone + 20)
  ctx.lineTo(centre, CANDLE.low * candleZone + 20)
  ctx.stroke()

  const top = Math.min(CANDLE.open, CANDLE.close) * candleZone + 20
  const bottom = Math.max(CANDLE.open, CANDLE.close) * candleZone + 20
  ctx.fillStyle = '#5b6070'
  ctx.fillRect(centre - width / 2, top, width, bottom - top)

  // ── the CVD line: this is what the scroll reveals ─────────────────────────
  const lineTop = candleZone + 54
  const lineHeight = h - lineTop - 16
  const extent = Math.max(...LINES.left.concat(LINES.right).map(Math.abs)) || 1
  const shown = Math.max(2, Math.floor(series.length * clamp01(progress)))

  ctx.strokeStyle = 'rgba(255,255,255,0.10)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(0, lineTop + lineHeight / 2)
  ctx.lineTo(w, lineTop + lineHeight / 2)
  ctx.stroke()

  ctx.strokeStyle = colour
  ctx.lineWidth = 2
  ctx.beginPath()
  for (let i = 0; i < shown; i += 1) {
    const x = (i / (series.length - 1)) * w
    const y = lineTop + lineHeight / 2 - (series[i] / extent) * (lineHeight / 2) * 0.9
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.stroke()
}

export function TwoCandles() {
  const leftRef = useRef<HTMLCanvasElement | null>(null)
  const rightRef = useRef<HTMLCanvasElement | null>(null)
  const progress = useRef(0)

  const draw = useCallback(() => {
    const left = leftRef.current && fitCanvas(leftRef.current)
    const right = rightRef.current && fitCanvas(rightRef.current)
    if (left) drawPanel(left.ctx, left.w, left.h, LINES.left, progress.current, '#34d399')
    if (right) drawPanel(right.ctx, right.w, right.h, LINES.right, progress.current, '#f87171')
  }, [])

  const ref = useScrubber<HTMLDivElement>({
    onProgress: (value) => {
      progress.current = value
      draw()
    },
    end: '+=120%',
  })

  useEffect(() => {
    draw()
    const onResize = () => draw()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [draw])

  return (
    <section ref={ref} className="relative mx-auto max-w-[1200px] px-6 py-24">
      <Eyebrow>{TWO_CANDLES.eyebrow}</Eyebrow>
      <h2 className="mt-4 max-w-[20ch] text-[clamp(2rem,4.2vw,3rem)] font-semibold">
        {TWO_CANDLES.title}
      </h2>

      <div className="mt-10 grid gap-5 md:grid-cols-2">
        {(
          [
            { key: 'left', label: 'Session A', ref: leftRef, cvd: '+4,218' },
            { key: 'right', label: 'Session B', ref: rightRef, cvd: '−3,904' },
          ] as const
        ).map((panel) => (
          <div key={panel.key} className="surface rounded-2xl p-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="num text-xs text-faint">{panel.label}</span>
              <span
                className={`num text-xs ${panel.key === 'left' ? 'text-bid' : 'text-ask'}`}
              >
                CVD {panel.cvd}
              </span>
            </div>
            <canvas
              ref={panel.ref}
              className="h-[300px] w-full"
              role="img"
              aria-label={`${panel.label}: an identical candlestick above a cumulative delta line that ends at ${panel.cvd}.`}
            />
            <div className="num mt-2 flex justify-between text-[11px] text-faint">
              <span>O 2418.1 · H 2419.4 · L 2416.8 · C 2418.9</span>
            </div>
          </div>
        ))}
      </div>

      <p className="num mt-8 max-w-[58ch] text-[15px] text-dim">{TWO_CANDLES.caption}</p>
    </section>
  )
}
