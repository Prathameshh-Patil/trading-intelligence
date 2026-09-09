/**
 * A seeded generator, so every visitor sees the same tape.
 *
 * `Math.random` would repaint the data on every resize and differ between the
 * server render and the client one. A fixed seed also means the numbers in the
 * captions — 1,940 contracts, three tenths of a point — can be made to match the
 * picture, rather than being decoration next to a different random one.
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const easeInOut = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2

export const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t)

/** Maps a sub-range of overall progress onto its own 0→1. */
export const phase = (p: number, from: number, to: number) => clamp01((p - from) / (to - from))
