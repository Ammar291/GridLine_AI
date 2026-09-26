// Map colours and sizes, all from the design tokens. Band colours carry severity; nothing else is saturated.
import type { Band, Crew } from '@/api/types';
import type { LayerId } from '@/ui/uiStore';

export const LAYER_LABELS: Record<LayerId, string> = {
  hills: 'Hills',
  water: 'Rivers and lakes',
  zones: 'Zones',
  drainage: 'Drainage',
  roads: 'Roads',
  construction: 'Construction',
  hospitals: 'Hospitals',
  shelters: 'Shelters',
  crews: 'Emergency teams',
  sensors: 'Sensors',
  threats: 'Threat overlay',
};

export const INK = 'var(--color-ink)';
export const INK_2 = 'var(--color-ink-2)';
export const INK_3 = 'var(--color-ink-3)';
export const PAGE = 'var(--color-page)';
export const RAISED = 'var(--color-raised)';
export const LINE_STRONG = 'var(--color-line-strong)';
export const ACCENT = 'var(--color-accent)';
export const OK = 'var(--color-ok)';
export const WATER = 'var(--color-viz-flood)';

export const bandColor = (b: Band): string => `var(--color-band-${b})`;

export const ZONE_FILL_OPACITY: Record<Band, number> = { normal: 0.12, watch: 0.28, warning: 0.36, critical: 0.42 };

export const CREW_FILL: Record<Crew['status'], string> = {
  available: OK,
  dispatched: ACCENT,
  en_route: ACCENT,
  on_site: bandColor('watch'),
  blocked: bandColor('critical'),
};

/** Channels count as blocked on the map above this fraction. */
export const BLOCKED_THRESHOLD = 0.3;

/** Halo behind SVG text so labels stay legible over fills and lines. */
export const TEXT_HALO = { stroke: PAGE, strokeWidth: 3, paintOrder: 'stroke' as const, strokeLinejoin: 'round' as const };

export const NON_SCALING = { vectorEffect: 'non-scaling-stroke' as const };

/** Crews en route drift toward their target; disabled by the global prefers-reduced-motion rule. */
export const MAP_MOTION_CSS =
  '@keyframes gl-crew-move{from{transform:translate(0,0)}to{transform:translate(var(--dx),var(--dy))}}' +
  '.gl-crew-move{animation:gl-crew-move 1.6s ease-in-out infinite alternate}';
