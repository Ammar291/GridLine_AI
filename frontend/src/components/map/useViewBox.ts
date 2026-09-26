import { useCallback, useState } from 'react';
import type { ViewBox } from '@/api/types';

const MIN_SCALE = 0.5;
const MAX_SCALE = 8;

/** Pure zoom around (cx, cy) in viewBox units; factor > 1 zooms in. Scale is clamped to [0.5x, 8x] of `initial`. */
export function zoomViewBox(vb: ViewBox, factor: number, cx: number, cy: number, initial: ViewBox): ViewBox {
  const minWidth = initial.width / MAX_SCALE;
  const maxWidth = initial.width / MIN_SCALE;
  const width = Math.min(maxWidth, Math.max(minWidth, vb.width / factor));
  const ratio = width / vb.width;
  return {
    x: cx - (cx - vb.x) * ratio,
    y: cy - (cy - vb.y) * ratio,
    width,
    height: vb.height * ratio,
  };
}

interface Rect { left: number; top: number; width: number; height: number }

/** Client pixel → viewBox point for preserveAspectRatio="xMidYMid meet". An element with no size maps to the centre. */
export function clientToViewBox(vb: ViewBox, rect: Rect, clientX: number, clientY: number): { x: number; y: number } {
  if (rect.width <= 0 || rect.height <= 0) return { x: vb.x + vb.width / 2, y: vb.y + vb.height / 2 };
  const scale = Math.min(rect.width / vb.width, rect.height / vb.height);
  const offsetX = (rect.width - vb.width * scale) / 2;
  const offsetY = (rect.height - vb.height * scale) / 2;
  return { x: vb.x + (clientX - rect.left - offsetX) / scale, y: vb.y + (clientY - rect.top - offsetY) / scale };
}

/** ViewBox units per screen pixel, so markers and labels can be drawn at a constant pixel size. 1 until measured. */
export function unitsPerPixel(vb: ViewBox, size: { width: number; height: number }): number {
  if (size.width <= 0 || size.height <= 0) return 1;
  return 1 / Math.min(size.width / vb.width, size.height / vb.height);
}

export function useViewBox(initial: ViewBox) {
  const [viewBox, setViewBox] = useState<ViewBox>(initial);
  const zoomAt = useCallback((factor: number, cx: number, cy: number) => {
    setViewBox((vb) => zoomViewBox(vb, factor, cx, cy, initial));
  }, [initial]);
  const panBy = useCallback((dx: number, dy: number) => {
    setViewBox((vb) => ({ ...vb, x: vb.x + dx, y: vb.y + dy }));
  }, []);
  const fit = useCallback(() => { setViewBox(initial); }, [initial]);
  const viewBoxAttr = `${String(viewBox.x)} ${String(viewBox.y)} ${String(viewBox.width)} ${String(viewBox.height)}`;
  return { viewBox, viewBoxAttr, zoomAt, panBy, fit };
}
