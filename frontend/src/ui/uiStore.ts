import { create } from 'zustand';
import type { EventGroup } from '@/live/describeEvent';

export type LayerId = 'hills' | 'water' | 'zones' | 'drainage' | 'roads' | 'construction' | 'hospitals' | 'shelters' | 'crews' | 'sensors' | 'threats';
export const ALL_LAYERS: readonly LayerId[] = ['hills', 'water', 'zones', 'drainage', 'roads', 'construction', 'hospitals', 'shelters', 'crews', 'sensors', 'threats'];

export interface EntityRef {
  kind: 'zone' | 'road' | 'bridge' | 'channel' | 'project' | 'crew' | 'shelter' | 'hospital' | 'sensor' | 'pump_depot';
  id: string;
}
export type WhyTarget =
  | { kind: 'action'; actionId: string; incidentId: string }
  | { kind: 'step'; stepId: string; runId: string; incidentId: string };

export interface UiState {
  selectedEntity: EntityRef | null;
  selectedIncidentId: string | null;
  activeLayers: ReadonlySet<LayerId>;
  whyTarget: WhyTarget | null;
  sourceCitationId: string | null;
  feedFilter: EventGroup | 'all';
  timelineZoneId: string | null;
  /** For a zone, pass findOpenIncidentForZone(...) so the zone's open incident becomes the selected one. */
  selectEntity: (ref: EntityRef | null, incidentIdForZone?: string | null) => void;
  selectIncident: (id: string | null) => void;
  toggleLayer: (l: LayerId) => void;
  openWhy: (t: WhyTarget) => void;
  closeWhy: () => void;
  openSource: (citationId: string) => void;
  closeSource: () => void;
  setFeedFilter: (f: EventGroup | 'all') => void;
  setTimelineZone: (id: string | null) => void;
  reset: () => void;
}

const initial = () => ({
  selectedEntity: null,
  selectedIncidentId: null,
  activeLayers: new Set<LayerId>(ALL_LAYERS) as ReadonlySet<LayerId>,
  whyTarget: null,
  sourceCitationId: null,
  feedFilter: 'all' as const,
  timelineZoneId: null,
});

export const useUiStore = create<UiState>()((set) => ({
  ...initial(),
  selectEntity: (ref, incidentIdForZone) => {
    set((s) => ({
      selectedEntity: ref,
      selectedIncidentId: ref?.kind === 'zone' && incidentIdForZone != null ? incidentIdForZone : s.selectedIncidentId,
    }));
  },
  selectIncident: (id) => { set({ selectedIncidentId: id }); },
  toggleLayer: (l) => {
    set((s) => {
      const next = new Set(s.activeLayers);
      if (next.has(l)) next.delete(l);
      else next.add(l);
      return { activeLayers: next };
    });
  },
  openWhy: (t) => { set({ whyTarget: t }); },
  closeWhy: () => { set({ whyTarget: null }); },
  openSource: (citationId) => { set({ sourceCitationId: citationId }); },
  closeSource: () => { set({ sourceCitationId: null }); },
  setFeedFilter: (f) => { set({ feedFilter: f }); },
  setTimelineZone: (id) => { set({ timelineZoneId: id }); },
  reset: () => { set(initial()); },
}));
