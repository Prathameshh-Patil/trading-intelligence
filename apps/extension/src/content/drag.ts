/**
 * Drag a fixed-position element by a handle. Pointer capture so a fast drag
 * that leaves the handle keeps following; clamped so the panel can always be
 * grabbed again; `onEnd` gets the settled position for persisting.
 */

export interface Point {
  x: number;
  y: number;
}

export function clamp(p: Point, el: HTMLElement): Point {
  const w = el.offsetWidth || 380;
  const h = el.offsetHeight || 48;
  const maxX = Math.max(0, window.innerWidth - w);
  const maxY = Math.max(0, window.innerHeight - Math.min(h, 48));
  return { x: Math.min(Math.max(0, p.x), maxX), y: Math.min(Math.max(0, p.y), maxY) };
}

export function draggable(
  handle: HTMLElement,
  el: HTMLElement,
  get: () => Point,
  set: (p: Point) => void,
  onEnd: (p: Point) => void,
): () => void {
  let start: Point | null = null;
  let origin: Point = get();

  const down = (e: PointerEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("button, input, select, a")) return;
    start = { x: e.clientX, y: e.clientY };
    origin = get();
    handle.setPointerCapture(e.pointerId);
    e.preventDefault();
  };
  const move = (e: PointerEvent) => {
    if (!start) return;
    set(clamp({ x: origin.x + e.clientX - start.x, y: origin.y + e.clientY - start.y }, el));
  };
  const up = (e: PointerEvent) => {
    if (!start) return;
    start = null;
    handle.releasePointerCapture(e.pointerId);
    onEnd(get());
  };

  handle.addEventListener("pointerdown", down);
  handle.addEventListener("pointermove", move);
  handle.addEventListener("pointerup", up);
  handle.addEventListener("pointercancel", up);
  return () => {
    handle.removeEventListener("pointerdown", down);
    handle.removeEventListener("pointermove", move);
    handle.removeEventListener("pointerup", up);
    handle.removeEventListener("pointercancel", up);
  };
}
