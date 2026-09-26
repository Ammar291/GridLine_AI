import type { LlmStatus } from '@/api/types';

function providerLabel(llm: LlmStatus | null): string {
  if (llm?.provider === 'anthropic') return `Anthropic ${llm.model ?? ''}`.trim();
  if (llm?.provider === 'mock') return 'Mock reasoner';
  return 'No backend';
}

export function ProviderBadge({ llm }: { llm: LlmStatus | null }) {
  return (
    <span className="inline-flex items-center h-6 px-2 rounded-[3px] border border-line text-[12px] text-ink-2" title="Reasoning provider">
      {providerLabel(llm)}
    </span>
  );
}
