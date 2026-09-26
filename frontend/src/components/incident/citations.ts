import type { AgentRun, Citation } from '@/api/types';

export type CitationKind = Citation['kind'];
export type CitationRef = Citation | { id: string };

/** Kind from the id convention (`sensor:…`, `state:…`, `event:…`); anything else is a document chunk. */
export function citationKind(id: string): CitationKind {
  if (id.startsWith('sensor:')) return 'sensor';
  if (id.startsWith('state:')) return 'state';
  if (id.startsWith('event:')) return 'event';
  return 'chunk';
}

/** Every citation recorded on the run's steps, first occurrence wins. */
export function runCitations(run: AgentRun | undefined): Citation[] {
  const seen = new Map<string, Citation>();
  for (const step of run?.steps ?? []) for (const c of step.citations) if (!seen.has(c.id)) seen.set(c.id, c);
  return [...seen.values()];
}

/** The full citation for an id when the run recorded one, else the bare id (the chip then shows the id). */
export function resolveCitation(id: string, citations: readonly Citation[]): CitationRef {
  return citations.find((c) => c.id === id) ?? { id };
}
