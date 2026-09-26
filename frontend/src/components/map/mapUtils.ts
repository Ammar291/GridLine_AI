import type { KeyboardEvent } from 'react';

export interface Point { x: number; y: number }

/** Vertices of an absolute M/L/Z polyline; null for anything else (curves, arcs, relative commands). */
export function pathVertices(d: string): Point[] | null {
  const tokens = d.trim().match(/[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?/g);
  if (!tokens || tokens.length === 0) return null;
  const points: Point[] = [];
  let i = 0;
  while (i < tokens.length) {
    const t = tokens[i] ?? '';
    if (t === 'Z' || t === 'z') { i++; continue; }
    if (t === 'M' || t === 'L') { i++; continue; }
    if (/[A-Za-z]/.test(t)) return null;
    const x = Number(t);
    const y = Number(tokens[i + 1]);
    if (Number.isNaN(x) || Number.isNaN(y)) return null;
    points.push({ x, y });
    i += 2;
  }
  return points.length > 0 ? points : null;
}

/** Point halfway along a polyline by length. */
export function polylineMidpoint(d: string): Point | null {
  const pts = pathVertices(d);
  if (!pts) return null;
  const segments = pts.slice(1).map((p, i) => {
    const a = pts[i] ?? p;
    return { a, b: p, len: Math.hypot(p.x - a.x, p.y - a.y) };
  });
  let remaining = segments.reduce((n, s) => n + s.len, 0) / 2;
  for (const s of segments) {
    if (remaining <= s.len && s.len > 0) {
      const t = remaining / s.len;
      return { x: s.a.x + (s.b.x - s.a.x) * t, y: s.a.y + (s.b.y - s.a.y) * t };
    }
    remaining -= s.len;
  }
  return pts[0] ?? null;
}

/** Average of the vertices; a cheap label anchor for a closed polyline. */
export function vertexCentroid(d: string): Point | null {
  const pts = pathVertices(d);
  if (!pts) return null;
  const closing = pts.length > 1 && pts[0]?.x === pts.at(-1)?.x && pts[0]?.y === pts.at(-1)?.y;
  const unique = closing ? pts.slice(0, -1) : pts;
  return { x: unique.reduce((n, p) => n + p.x, 0) / unique.length, y: unique.reduce((n, p) => n + p.y, 0) / unique.length };
}

/** Short label for a crew marker: the digits of its id ('C-4' → '4'), else the id. */
export function crewNumber(id: string): string {
  const digits = id.replace(/\D/g, '');
  return digits === '' ? id : String(Number(digits));
}

/** Props that make an SVG element a keyboard-reachable button. */
export function selectable(label: string, onActivate: () => void) {
  return {
    role: 'button' as const,
    tabIndex: 0,
    'aria-label': label,
    className: 'cursor-pointer',
    onClick: onActivate,
    onKeyDown: (e: KeyboardEvent<SVGElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onActivate();
      }
    },
  };
}

/** SVG transform that places pixel-sized marker art at (x, y) regardless of zoom. */
export function markerTransform(p: Point, unitsPerPx: number): string {
  return `translate(${String(p.x)} ${String(p.y)}) scale(${String(unitsPerPx)})`;
}
