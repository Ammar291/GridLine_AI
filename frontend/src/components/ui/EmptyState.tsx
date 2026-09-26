export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div role="note" className="p-4 max-w-[60ch]">
      <p className="text-ink-2 text-[13px]">{title}</p>
      {body !== undefined && <p className="text-ink-3 text-[12px] mt-1">{body}</p>}
    </div>
  );
}
