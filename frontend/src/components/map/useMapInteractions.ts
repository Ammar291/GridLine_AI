import { useEffect, useRef, useState, type MouseEvent, type PointerEvent, type RefObject } from 'react';
import type { ViewBox } from '@/api/types';
import { clientToViewBox } from './useViewBox';

const WHEEL_STEP = 1.2;
/** Pointer travel (px) before a press becomes a drag; below it the press is a click on an entity. */
const DRAG_THRESHOLD_PX = 4;

/** Rendered size of an element, kept current with a ResizeObserver. {0, 0} until measured. */
export function useElementSize(ref: RefObject<Element | null>): { width: number; height: number } {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r) setSize({ width: r.width, height: r.height });
    });
    ro.observe(el);
    return () => { ro.disconnect(); };
  }, [ref]);
  return size;
}

/** Wheel zoom around the cursor. Registered natively so preventDefault works (React wheel listeners are passive). */
export function useWheelZoom(ref: RefObject<SVGSVGElement | null>, viewBox: ViewBox, zoomAt: (f: number, cx: number, cy: number) => void): void {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = clientToViewBox(viewBox, el.getBoundingClientRect(), e.clientX, e.clientY);
      zoomAt(e.deltaY < 0 ? WHEEL_STEP : 1 / WHEEL_STEP, p.x, p.y);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => { el.removeEventListener('wheel', onWheel); };
  }, [ref, viewBox, zoomAt]);
}

interface Drag { id: number; x: number; y: number; moved: boolean }

/** Drag to pan. Pointer capture starts only once the press moves, so a plain click still reaches the entity under it. */
export function useDragPan(unitsPerPx: number, panBy: (dx: number, dy: number) => void) {
  const drag = useRef<Drag | null>(null);
  const swallowClick = useRef(false);
  const end = () => {
    if (drag.current?.moved) swallowClick.current = true;
    drag.current = null;
  };
  return {
    onPointerDown: (e: PointerEvent<SVGSVGElement>) => {
      if (e.button !== 0) return;
      drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
    },
    onPointerMove: (e: PointerEvent<SVGSVGElement>) => {
      const d = drag.current;
      if (d?.id !== e.pointerId) return;
      const dx = e.clientX - d.x;
      const dy = e.clientY - d.y;
      if (!d.moved) {
        if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
        const el = e.currentTarget;
        if ('setPointerCapture' in el) el.setPointerCapture(e.pointerId);
      }
      drag.current = { id: d.id, x: e.clientX, y: e.clientY, moved: true };
      panBy(-dx * unitsPerPx, -dy * unitsPerPx);
    },
    onPointerUp: end,
    onPointerCancel: end,
    /** A drag ends with a click event; swallow it so the entity under the pointer is not selected. */
    onClickCapture: (e: MouseEvent<SVGSVGElement>) => {
      if (!swallowClick.current) return;
      swallowClick.current = false;
      e.stopPropagation();
    },
  };
}
