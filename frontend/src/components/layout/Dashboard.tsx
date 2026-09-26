import type { ReactNode } from 'react';
import { OverviewStrip } from '@/components/overview/OverviewStrip';
import { ModeBanner } from '@/components/scenario/ModeBanner';
import { ScenarioBar } from '@/components/scenario/ScenarioBar';
import { useLiveStore } from '@/live/liveStore';

interface DashboardProps {
  map: ReactNode;
  timeline: ReactNode;
  feed: ReactNode;
  incident: ReactNode;
  approvals: ReactNode;
  actions: ReactNode;
}

const cell = 'min-h-0 min-w-0';

export function Dashboard({ map, timeline, feed, incident, approvals, actions }: DashboardProps) {
  const mode = useLiveStore((s) => s.mode);
  const connection = useLiveStore((s) => s.connection);
  return (
    <div
      data-testid="dashboard"
      className="grid h-screen overflow-hidden bg-page text-ink gap-px grid-cols-[58fr_42fr] grid-rows-[64px_auto_55fr_22fr_23fr_44px]"
    >
      <div className={`${cell} col-span-2`}><OverviewStrip /></div>
      <div className={`${cell} col-span-2`}><ModeBanner mode={mode} connection={connection} /></div>
      <div className={cell}>{map}</div>
      <div className={cell}>{incident}</div>
      <div className={cell}>{timeline}</div>
      <div className={cell}>{approvals}</div>
      <div className={cell}>{feed}</div>
      <div className={cell}>{actions}</div>
      <div className={`${cell} col-span-2`}><ScenarioBar /></div>
    </div>
  );
}
