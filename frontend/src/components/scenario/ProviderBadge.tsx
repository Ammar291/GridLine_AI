import type { LlmStatus } from '@/api/types';

/** `backend`: a live backend is connected; without an LLM status it has no reasoner yet (the LLM layer is PENDING). */
function providerLabel(llm: LlmStatus | null, backend: boolean): string {
  if (llm?.provider === 'anthropic') return `Anthropic ${llm.model ?? ''}`.trim();
  if (llm?.provider === 'mock') return 'Mock reasoner';
  return backend ? 'No reasoner yet' : 'No backend';
}

export function ProviderBadge({ llm, backend = false }: { llm: LlmStatus | null; backend?: boolean }) {
  return (
    <span className="inline-flex items-center h-6 px-2 rounded-[3px] border border-line text-[12px] text-ink-2" title="Reasoning provider">
      {providerLabel(llm, backend)}
    </span>
  );
}
