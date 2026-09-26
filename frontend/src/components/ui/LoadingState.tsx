export function LoadingState({ rows = 3, label = 'Loading' }: { rows?: number; label?: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="p-3 flex flex-col gap-2">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-3 bg-line animate-pulse rounded-[2px]" style={{ width: `${String(90 - i * 12)}%` }} />
      ))}
    </div>
  );
}
