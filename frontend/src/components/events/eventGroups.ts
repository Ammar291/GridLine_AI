import type { EventGroup } from '@/live/describeEvent';

export type FeedFilter = EventGroup | 'all';

/** Filter chips in display order. `noun` names the group inside sentences ("No alert events yet."). */
export const FEED_FILTERS: readonly { value: FeedFilter; label: string; noun: string }[] = [
  { value: 'all', label: 'All', noun: '' },
  { value: 'simulation', label: 'Simulation', noun: 'simulation' },
  { value: 'threat', label: 'Threats', noun: 'threat' },
  { value: 'agent', label: 'Agent', noun: 'agent' },
  { value: 'approval', label: 'Approvals', noun: 'approval' },
  { value: 'action', label: 'Actions', noun: 'action' },
  { value: 'alert', label: 'Alerts', noun: 'alert' },
];

/** Left-edge tint per group; the row text always names the event, so colour is never the only carrier. */
export const GROUP_BORDER: Record<EventGroup, string> = {
  simulation: 'border-l-line-strong',
  threat: 'border-l-band-watch',
  agent: 'border-l-accent',
  approval: 'border-l-band-warning',
  action: 'border-l-ok',
  alert: 'border-l-band-critical',
};

export const FEED_MOTION_CSS = '@keyframes gl-feed-in{from{opacity:0}to{opacity:1}}.gl-feed-in{animation:gl-feed-in 300ms ease-out}';
