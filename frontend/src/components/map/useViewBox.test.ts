import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { clientToViewBox, unitsPerPixel, useViewBox, zoomViewBox } from './useViewBox';

const init = { x: 0, y: 0, width: 1000, height: 700 };

describe('zoomViewBox', () => {
  it('zooms in around the given point', () => {
    expect(zoomViewBox(init, 2, 500, 350, init)).toEqual({ x: 250, y: 175, width: 500, height: 350 });
  });
  it('keeps the point under the cursor fixed', () => {
    const vb = zoomViewBox(init, 2, 100, 100, init);
    expect(vb.x).toBe(50);
    expect(vb.y).toBe(50);
  });
  it('clamps zooming out at 0.5x of the initial box', () => {
    const vb = zoomViewBox(init, 0.25, 500, 350, init);
    expect(vb.width).toBe(2000);
    expect(vb.height).toBe(1400);
  });
  it('clamps zooming in at 8x of the initial box', () => {
    const vb = zoomViewBox(init, 100, 500, 350, init);
    expect(vb.width).toBe(125);
    expect(vb.height).toBeCloseTo(87.5);
  });
});

describe('useViewBox', () => {
  it('panBy shifts x and y, fit restores the initial box', () => {
    const { result } = renderHook(() => useViewBox(init));
    act(() => { result.current.panBy(10, 20); });
    expect(result.current.viewBox).toEqual({ x: 10, y: 20, width: 1000, height: 700 });
    expect(result.current.viewBoxAttr).toBe('10 20 1000 700');
    act(() => { result.current.zoomAt(2, 500, 350); });
    expect(result.current.viewBox.width).toBe(500);
    act(() => { result.current.fit(); });
    expect(result.current.viewBox).toEqual(init);
  });
});

describe('clientToViewBox', () => {
  it('maps client pixels into viewBox units with letterboxing (xMidYMid meet)', () => {
    // 1000x700 box drawn into a 2000x700 element: scale 1, 500px of letterbox on each side.
    const rect = { left: 0, top: 0, width: 2000, height: 700 };
    expect(clientToViewBox(init, rect, 500, 0)).toEqual({ x: 0, y: 0 });
    expect(clientToViewBox(init, rect, 1500, 700)).toEqual({ x: 1000, y: 700 });
  });
  it('falls back to the centre of the box when the element has no size', () => {
    expect(clientToViewBox(init, { left: 0, top: 0, width: 0, height: 0 }, 0, 0)).toEqual({ x: 500, y: 350 });
  });
  it('unitsPerPixel follows the limiting dimension and defaults to 1', () => {
    expect(unitsPerPixel(init, { width: 500, height: 700 })).toBe(2);
    expect(unitsPerPixel(init, { width: 0, height: 0 })).toBe(1);
  });
});
