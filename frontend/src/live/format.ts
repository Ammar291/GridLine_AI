import type { NodeName } from '@/api/types';

const pad = (n: number) => String(n).padStart(2, '0');

/** 'HH:mm' from an ISO sim time (sim times carry no zone), '—' for null. */
export function fmtSimTime(iso: string | null): string {
  return iso === null || iso.length < 16 ? '—' : iso.slice(11, 16);
}

export function fmtSimTimeSec(iso: string | null): string {
  return iso === null || iso.length < 19 ? '—' : iso.slice(11, 19);
}

/** 'HH:mm:ss' in the viewer's local time. */
export function fmtWall(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function fmtPct(x: number): string {
  return `${String(Math.round(x * 100))}%`;
}

export function fmtIndex(x: number): string {
  return x.toFixed(2);
}

export function fmtNumber(n: number): string {
  return n.toLocaleString('en-US');
}

const TOOL_VERBS: Record<string, string> = {
  halt_construction: 'Halt construction',
  close_road: 'Close road',
  deploy_pumps: 'Deploy pumps',
  dispatch_crew: 'Dispatch crew',
  open_shelter: 'Open shelter',
  issue_alert: 'Issue alert',
  schedule_inspection: 'Schedule inspection',
};

/** Human verb for a tool; unknown tools keep their raw name so nothing renders blank. */
export function toolVerb(tool: string): string {
  return TOOL_VERBS[tool] ?? tool;
}

/** 'en_route' → 'En route'. */
export function statusLabel(s: string): string {
  const spaced = s.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export const NODE_LABELS: Record<NodeName, string> = {
  observe: 'Observe',
  retrieve: 'Retrieve evidence',
  assess: 'Assess threat',
  predict: 'Predict',
  cascade: 'Analyse cascade',
  recommend: 'Recommend actions',
  approval_gate: 'Approval gate',
  execute: 'Execute',
  verify: 'Verify',
  replan: 'Re-plan',
};
