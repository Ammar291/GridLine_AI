import type { BandName } from '@/components/ui/bandLabel';

interface StatTileProps {
  label: string;
  value: string;
  detail?: string;
  band?: BandName;
  onClick?: () => void;
  testId?: string;
}

const BAND_BORDER: Record<BandName, string> = {
  normal: 'border-l-band-normal',
  watch: 'border-l-band-watch',
  warning: 'border-l-band-warning',
  critical: 'border-l-band-critical',
};
const BAND_TEXT: Record<BandName, string> = {
  normal: 'text-band-normal-text',
  watch: 'text-band-watch-text',
  warning: 'text-band-warning-text',
  critical: 'text-band-critical-text',
};

export function StatTile({ label, value, detail, band, onClick, testId }: StatTileProps) {
  const body = (
    <>
      <span className="block text-[11px] text-ink-2">{label}</span>{' '}
      <span className={`block condensed text-[26px] leading-7 font-medium truncate ${band ? BAND_TEXT[band] : 'text-ink'}`}>{value}</span>{' '}
      {detail !== undefined && <span className="block text-[11px] text-ink-3 truncate">{detail}</span>}
    </>
  );
  return (
    <div
      role="group"
      aria-label={label}
      data-testid={testId}
      data-band={band}
      className={`min-w-0 h-full border-r border-line last:border-r-0 ${band ? `border-l-2 ${BAND_BORDER[band]}` : ''}`}
    >
      {onClick ? (
        <button type="button" onClick={onClick} className="w-full h-full text-left px-3 py-1.5 hover:bg-raised">
          {body}
        </button>
      ) : (
        <div className="px-3 py-1.5">{body}</div>
      )}
    </div>
  );
}
