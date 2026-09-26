import { bandLabel, type BandName } from './bandLabel';

const BAND_CLASSES: Record<BandName, string> = {
  normal: 'bg-band-normal text-white',
  watch: 'bg-band-watch text-page',
  warning: 'bg-band-warning text-page',
  critical: 'bg-band-critical text-white',
};

export function SeverityChip({ band, size = 'sm' }: { band: BandName; size?: 'sm' | 'md' }) {
  const sizeClass = size === 'md' ? 'px-2 text-[12px] leading-6' : 'px-1.5 text-[11px] leading-5';
  return (
    <span data-band={band} className={`inline-block rounded-[3px] font-medium ${sizeClass} ${BAND_CLASSES[band]}`}>
      {bandLabel(band)}
    </span>
  );
}
