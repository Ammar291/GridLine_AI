import type { ReactNode } from 'react';

interface IconProps { className?: string; title?: string }

function Svg({ className, title, children }: IconProps & { children: ReactNode }) {
  const labelled = title !== undefined;
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={labelled ? 'img' : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-label={title}
    >
      {labelled && <title>{title}</title>}
      {children}
    </svg>
  );
}

export function IconCheck(p: IconProps) {
  return <Svg {...p}><path d="M3 8.5l3 3 7-7" /></Svg>;
}
export function IconWarning(p: IconProps) {
  return <Svg {...p}><path d="M8 2l6.5 11.5h-13z" /><path d="M8 6.5v3" /><path d="M8 11.8v.2" /></Svg>;
}
export function IconReplan(p: IconProps) {
  return <Svg {...p}><path d="M13 8a5 5 0 1 1-1.5-3.6" /><path d="M13 2.5v3h-3" /></Svg>;
}
export function IconPending(p: IconProps) {
  return <Svg {...p}><circle cx="8" cy="8" r="5.5" strokeDasharray="3 2.5" /></Svg>;
}
export function IconClose(p: IconProps) {
  return <Svg {...p}><path d="M4 4l8 8M12 4l-8 8" /></Svg>;
}
export function IconZoomIn(p: IconProps) {
  return <Svg {...p}><path d="M8 3v10M3 8h10" /></Svg>;
}
export function IconZoomOut(p: IconProps) {
  return <Svg {...p}><path d="M3 8h10" /></Svg>;
}
export function IconFit(p: IconProps) {
  return <Svg {...p}><path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" /></Svg>;
}
export function IconPlay(p: IconProps) {
  return <Svg {...p}><path d="M5 3l8 5-8 5z" fill="currentColor" /></Svg>;
}
export function IconPause(p: IconProps) {
  return <Svg {...p}><path d="M5.5 3v10M10.5 3v10" strokeWidth="2" /></Svg>;
}
export function IconReset(p: IconProps) {
  return <Svg {...p}><path d="M3 8a5 5 0 1 0 1.5-3.6" /><path d="M3 2.5v3h3" /></Svg>;
}
export function IconChevron(p: IconProps) {
  return <Svg {...p}><path d="M6 3.5L10.5 8 6 12.5" /></Svg>;
}
export function IconHospital(p: IconProps) {
  return <Svg {...p}><rect x="2.5" y="2.5" width="11" height="11" rx="1.5" /><path d="M8 5v6M5 8h6" /></Svg>;
}
export function IconShelter(p: IconProps) {
  return <Svg {...p}><path d="M2 8l6-5.5L14 8" /><path d="M4 7v6.5h8V7" /></Svg>;
}
export function IconCrew(p: IconProps) {
  return <Svg {...p}><path d="M3 12l5-8 5 8-5-2.5z" /></Svg>;
}
export function IconConstruction(p: IconProps) {
  return <Svg {...p}><rect x="2.5" y="2.5" width="11" height="11" /><path d="M2.5 9.5l7-7M6.5 13.5l7-7" /></Svg>;
}
export function IconSensor(p: IconProps) {
  return <Svg {...p}><circle cx="8" cy="8" r="1.8" fill="currentColor" /><path d="M4.5 4.5a5 5 0 0 0 0 7M11.5 4.5a5 5 0 0 1 0 7" /></Svg>;
}
export function IconDrop(p: IconProps) {
  return <Svg {...p}><path d="M8 2.5s4 4.5 4 7.2a4 4 0 0 1-8 0C4 7 8 2.5 8 2.5z" /></Svg>;
}
export function IconSlope(p: IconProps) {
  return <Svg {...p}><path d="M2 13.5h12L2 4z" /><path d="M9 6.5l1.5-1M11 8.5l1.5-1" /></Svg>;
}
