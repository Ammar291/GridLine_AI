import { describe, expect, it } from 'vitest';
import { crewNumber, pathVertices, polylineMidpoint, vertexCentroid } from './mapUtils';

describe('map path helpers', () => {
  it('parses absolute M/L polylines, with or without commas', () => {
    expect(pathVertices('M0 0 L10 0L10,10 Z')).toEqual([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }]);
  });
  it('returns null for curves or relative commands', () => {
    expect(pathVertices('M0 0 C10 10 20 20 30 30')).toBeNull();
    expect(pathVertices('m0 0 l10 0')).toBeNull();
    expect(pathVertices('')).toBeNull();
  });
  it('finds the midpoint by length along the polyline', () => {
    expect(polylineMidpoint('M0 0 L10 0 L10 30')).toEqual({ x: 10, y: 10 });
    expect(polylineMidpoint('M0 0 A5 5 0 1 0 10 0')).toBeNull();
  });
  it('averages vertices for a label anchor', () => {
    expect(vertexCentroid('M0 0 L10 0 L10 10 L0 10 Z')).toEqual({ x: 5, y: 5 });
  });
  it('crewNumber takes the digits of the id', () => {
    expect(crewNumber('C-4')).toBe('4');
    expect(crewNumber('c3')).toBe('3');
    expect(crewNumber('alpha')).toBe('alpha');
  });
});
