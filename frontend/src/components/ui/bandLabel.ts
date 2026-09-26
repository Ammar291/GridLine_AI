export type BandName = 'normal' | 'watch' | 'warning' | 'critical';

export const BAND_ORDER: readonly BandName[] = ['normal', 'watch', 'warning', 'critical'];

const LABELS: Record<BandName, string> = {
  normal: 'Normal',
  watch: 'Watch',
  warning: 'Warning',
  critical: 'Critical',
};

export function bandLabel(b: BandName): string {
  return LABELS[b];
}

export function bandRank(b: BandName): number {
  return BAND_ORDER.indexOf(b);
}

export function maxBand(bands: readonly BandName[]): BandName {
  let best: BandName = 'normal';
  for (const b of bands) if (bandRank(b) > bandRank(best)) best = b;
  return best;
}
