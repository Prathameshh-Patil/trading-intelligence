'use client'

/**
 * The most important animation on the site.
 *
 * It performs the thesis rather than asserting it: several hundred individual
 * trades stream in, coloured by which side crossed the spread, and as the reader
 * scrolls they compress into one candle **while the colour drains out of them**.
 * The information loss happens on screen. Nothing else here has to argue.
 *
 * Canvas, not DOM — three hundred animated nodes is a jank machine, and this
 * paints in one pass per frame.
 */

import { useCallback, useEffect, useRef } from 'react'

import { Eyebrow } from '../ui'
import { LOSSY } from '@/content/site'
import { fitCanvas, prefersReducedMotion, useScrubber } from '@/lib/motion'
import { clamp01, easeInOut, mulberry32, phase } from '@/lib/rng'

const COUNT = 280
const BID = '#34d399'
const ASK = '#f87171'
/** What the colour drains *to*: the flat body of an ordinary drawn candle. */
const DRAINED = '#5b6070'

type Trade = { x: number; y: number; size: number; side: 0 | 1; enter: number }

/** Positions are fractions of the canvas, so a resize re-lays-out rather than re-randomises. */
function buildTrades(): { trades: Trade[]; open: number; close: number; high: number; low: number } {
  const rand = mulberry32(77532)
  const trades: Trade[] = []

  let price = 0.5

  for (let i = 0; i < COUNT; i += 1) {
    const t = i / (COUNT - 1)
    // A gentle drift with noise: enough shape that the candle has a real body,
    // not so much that it looks authored.
    price += (rand() - 0.48) * 0.03
    trades.push({
      x: 0.08 + t * 0.84,
      y: price,
      size: 1.6 + rand() * 3.6,
      side: rand() > 0.5 ? 1 : 0,
      // Staggered arrival across the first part of the scroll, so the tape
      // *streams* rather than appearing all at once.
      enter: t * 0.42,
    })
  }

  // Normalise into the canvas rather than trusting the walk to land well. An
  // unnormalised random walk usually occupies a thin band in the middle, which
  // reads as a flat market and wastes the height the section is paying for.
  const values = trades.map((t) => t.y)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  for (const trade of trades) {
    trade.y = 0.12 + ((trade.y - min) / span) * 0.76
  }

  const high = Math.min(...trades.map((t) => t.y))
  const low = Math.max(...trades.map((t) => t.y))

  return { trades, open: trades[0].y, close: trades[COUNT - 1].y, high, low }
}

/** Blend two hex colours. The drain is a lerp toward grey, done per trade. */
function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16))
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16))
  const out = pa.map((v, i) => Math.round(v + (pb[i] - v) * t))
  return `rgb(${out[0]},${out[1]},${out[2]})`
}

function drawCandle(
  ctx: CanvasRenderingContext2D,
  x: number,
  h: number,
  candle: { open: number; close: number; high: number; low: number },
  width: number,
) {
  const top = Math.min(candle.open, candle.close) * h
  const bottom = Math.max(candle.open, candle.close) * h

  ctx.strokeStyle = DRAINED
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(x, candle.high * h)
  ctx.lineTo(x, candle.low * h)
  ctx.stroke()

  ctx.fillStyle = DRAINED
  ctx.fillRect(x - width / 2, top, width, Math.max(2, bottom - top))
}

export function LossyCompression() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const model = useRef(buildTrades())
  const progress = useRef(0)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const fitted = fitCanvas(canvas)
    if (!fitted) return

    const { ctx, w, h } = fitted
    const { trades, open, close, high, low } = model.current
    ctx.clearRect(0, 0, w, h)

    const candleW = 34

    /**
     * Reduced motion gets a composite, not the last frame.
     *
     * The last frame of this sequence is a small grey candle and almost nothing
     * else — which is the correct end of an animation and a useless still. Somebody
     * who never saw the trades move would be looking at an empty canvas under a
     * caption about trades disappearing. So the still says the same thing
     * spatially instead: the tape on the left, in full colour, and the bar it
     * became on the right.
     */
    if (prefersReducedMotion()) {
      for (const trade of trades) {
        ctx.fillStyle = trade.side ? BID : ASK
        ctx.globalAlpha = 0.9
        ctx.beginPath()
        ctx.arc(trade.x * w * 0.62 + w * 0.03, trade.y * h, trade.size, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      drawCandle(ctx, w * 0.84, h, { open, close, high, low }, candleW)

      ctx.fillStyle = '#6b7285'
      ctx.font = '12px ui-monospace, monospace'
      ctx.textAlign = 'center'
      ctx.fillText('every trade, with its side', w * 0.33, h - 8)
      ctx.fillText('the bar', w * 0.84, h - 8)
      return
    }

    const p = progress.current
    // The candle settles where the compressed trades arrive, so the eye follows
    // the movement rather than having to jump to it.
    const candleX = w * 0.72
    const compress = easeInOut(phase(p, 0.46, 0.96))

    for (const trade of trades) {
      const alpha = clamp01((p - trade.enter) * 7)
      if (alpha <= 0) continue

      const x = trade.x * w + (candleX - trade.x * w) * compress
      const y = trade.y * h

      ctx.globalAlpha = alpha * (1 - compress * 0.55)
      ctx.fillStyle = mix(trade.side ? BID : ASK, DRAINED, compress)
      ctx.beginPath()
      ctx.arc(x, y, trade.size * (1 - compress * 0.35), 0, Math.PI * 2)
      ctx.fill()
    }

    // The candle resolves out of the pile it was made from.
    if (compress > 0.02) {
      ctx.globalAlpha = compress
      drawCandle(ctx, candleX, h, { open, close, high, low }, candleW)
    }

    ctx.globalAlpha = 1
  }, [])

  const ref = useScrubber<HTMLDivElement>({
    onProgress: (value) => {
      progress.current = value
      draw()
    },
    end: '+=150%',
  })

  useEffect(() => {
    draw()
    const onResize = () => draw()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [draw])

  return (
    <section ref={ref} className="relative mx-auto max-w-[1200px] px-6 py-24">
      <Eyebrow>{LOSSY.eyebrow}</Eyebrow>
      <h2 className="mt-4 max-w-[18ch] text-[clamp(2rem,4.2vw,3rem)] font-semibold">
        {LOSSY.title}
      </h2>

      {/* Framed like a panel in the app rather than floating on the page —
          a drawing with no edges reads as an unfinished section. */}
      <figure className="surface mt-10 overflow-hidden rounded-2xl">
        <figcaption className="num flex items-center justify-between border-b border-white/[0.08] px-4 py-2.5 text-[11px] text-faint">
          <span>GCZ6 · 280 trades · one minute</span>
          <span>aggressor side retained</span>
        </figcaption>
        <div className="px-4 py-3">
          <canvas
            ref={canvasRef}
            className="h-[340px] w-full sm:h-[400px]"
            role="img"
            aria-label="Hundreds of individual trades, coloured by which side crossed the spread, compressing into a single grey candlestick as the colour drains out of them."
          />
        </div>
      </figure>

      <p className="num mt-8 max-w-[54ch] text-[15px] text-dim">{LOSSY.caption}</p>
    </section>
  )
}
