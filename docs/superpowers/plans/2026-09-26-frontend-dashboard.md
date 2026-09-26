# GridLine AI Frontend Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the single-screen Emergency Operations Center dashboard for GridLine AI (Nandipur) in `frontend/`: map, live feed, risk timeline, incident reasoning with citations, approvals, actions with verification, and a "Why?" drawer, running today against a mock client and later against the FastAPI backend without code changes.

**Architecture:** An `ApiClient` interface has two implementations (`HttpApiClient`, `MockApiClient`) chosen by `VITE_API_MODE`. Static and on-demand data flow through TanStack Query; everything that changes per tick arrives over one WebSocket into a Zustand store through a pure `applyEvent` reducer. Panels are small presentational components that read the store through hooks; the only stateful UI is a `uiStore` for selection, layers and drawers. Types are generated from an interim `openapi.yaml` that mirrors ARCHITECTURE.md §12 plus the additions in the spec §9.

**Tech Stack:** Vite 8, React 19.3, TypeScript 5.9 (strict), Tailwind v4 (`@tailwindcss/vite`), TanStack Query 5, Zustand 5, Recharts 3, openapi-typescript 7, Vitest 5 + Testing Library + jsdom, ESLint 10 + typescript-eslint 8, `@fontsource-variable/archivo`.

**Spec:** `docs/superpowers/specs/2026-09-26-frontend-dashboard-design.md` (read it first; this plan argues from it). Also read `CLAUDE.md` and ARCHITECTURE.md §12–13.

## Global Constraints

- Frontend only. No AI logic, no simulation model, no RAG, no backend code. The mock replays scripted simulation/detector events and **never** fabricates agent, approval, action or verification data (spec F1).
- `strict: true`, no `any`, no non-null assertions except in tests, no default exports except `App`. Domain types come only from `src/api/types.ts` (re-exports of the generated `schema.d.ts`); never hand-write payload types.
- TypeScript pinned `~5.9.3` (typescript-eslint and openapi-typescript do not accept TS 7 yet). Vite `^8`, Vitest `^5`, Recharts `^3`, React `^19.3`.
- Server state through TanStack Query; live state through the Zustand `liveStore`; components presentational; data access in hooks.
- Naming follows the domain: zone, channel, project, crew, incident, run, step, approval, action, claim, citation. No synonyms (no "team", "task list", "alerting rule").
- Every panel implements loading, empty, populated and error states. Empty-state copy names what would fill the panel, in sentence case, one sentence.
- Files under ~300 lines. One component per file. Tests beside the file as `*.test.tsx` / `*.test.ts`.
- Runs offline after `npm install`: fonts self-hosted via fontsource; no CDN links.
- **Do not commit.** CLAUDE.md: commit only when asked. Skip every "commit" step you might be inclined to add.
- Windows dev machine (PowerShell), but all npm scripts must also run in bash.
- **Design tokens are fixed** (validated with the dataviz palette validator on 2026-09-26). Use only these, via Tailwind utilities generated from `@theme`:

```css
/* src/styles/tokens.css */
@import "tailwindcss";
@import "@fontsource-variable/archivo/wdth.css";

@theme {
  --font-sans: "Archivo Variable", system-ui, sans-serif;

  --color-page: #0F1620;        /* app background */
  --color-panel: #151E2A;       /* panel surface */
  --color-raised: #1C2735;      /* hover, popovers, drawers */
  --color-line: #2A3644;        /* hairline borders */
  --color-line-strong: #3A4858; /* focused / selected borders */

  --color-ink: #E6EBF0;         /* primary text */
  --color-ink-2: #9AA7B5;       /* secondary text */
  --color-ink-3: #6B7A8A;       /* muted text, ≥3:1 only for labels ≥14px or non-text */

  --color-accent: #6FA3DC;      /* interactive: links, focus ring, primary button */
  --color-accent-strong: #8FBBEA;

  --color-band-normal: #4C8C89;      --color-band-normal-text: #6FB3AF;
  --color-band-watch: #F2C744;       --color-band-watch-text: #F2C744;
  --color-band-warning: #EE7A2A;     --color-band-warning-text: #EE7A2A;
  --color-band-critical: #C92B2B;    --color-band-critical-text: #F07A7A;

  --color-ok: #2EA36A;               --color-ok-text: #5FCB8F;   /* verified */

  --color-viz-rain: #6DA7EC;         /* rain bars, top chart */
  --color-viz-flood: #3987E5;        /* flood index line */
  --color-viz-landslide: #199E70;    /* landslide index line */
  --color-viz-saturation: #8A97A6;   /* saturation context line + 10% wash */
  --color-viz-grid: #243040;
  --color-viz-axis: #3A4858;
}
```

- **Visual principles** (from the frontend-design pass; apply in every UI task):
  1. The map is the hero. Every other panel is an instrument: quiet, dense, hairline-bordered, square corners on panels, 3 px radius on chips and buttons, no shadows, no gradients.
  2. Only the four band colours and the `ok` green carry meaning. Everything else is ink on slate. Chart series use the `viz` tokens only; band colours never colour a series.
  3. Text is sentence case everywhere, including chips (`Warning`, not `WARNING`). No all-caps eyebrows, no middle-dot separators, no arrows appended to buttons. Numbers, IDs and sim times use `tabular-nums`; stat values use proportional figures in the condensed width (`font-stretch: 80%`).
  4. Words tell people what to do: buttons name the outcome ("Approve 3 actions", "Reject plan"), empty states name what will appear, errors say what failed and offer retry.
  5. Motion only for change: critical zones pulse, new feed rows fade in, crews en route move. Respect `prefers-reduced-motion` (disable all three).
  6. Body 12–13 px, meta 11 px, panel titles 13 px condensed medium, stat values 24–28 px condensed. Line length under 80 characters in prose blocks.
  7. Every glyph has a text label or `aria-label`; colour is never the only carrier of state; all interactive elements are keyboard reachable with a visible focus ring (`outline: 2px solid var(--color-accent)`).

## Review Focus

Inputs the spec implies but no panel test covers by default; each has a pinned test in the owning task:

1. A `state.snapshot` arriving **after** live events (reconnect) must replace, not merge, and must clear stale pending approvals → Task 6.
2. `agent.node.finished` for a run the store has never seen (missed `agent.run.started`) must still render the step, not crash → Task 6.
3. A `zone.state` event for a zone missing from the city payload (backend seeded a zone the mock does not know) must not throw and must not appear on the map → Task 6 and Task 10.
4. An `approval.requested` whose `proposed_actions` reference an unknown tool name must render with the raw tool name, never blank → Task 14.
5. WebSocket closes mid-run: the feed and panels keep their last data, the connection dot turns to `reconnecting`, and no panel flips to its empty state → Task 8 and Task 9.

---

## Shared vocabulary (used by every task)

Generated types are imported as `import type { Zone, Event, ... } from '@/api/types'` (alias `@` → `src`). Task 3 produces them; the names below are fixed:

`Health, LlmStatus, City, ViewBox, XY, Zone, ZoneState, Band, Hazard, Road, Channel, Project, Sensor, Crew, Shelter, PumpDepot, PumpUnit, Hospital, MapFeature, Bands, Scenario, IncidentSummary, Incident, AgentRun, AgentStep, NodeName, StepOutput, CitySnapshot, RetrievedChunks, ThreatAssessment, RiskPrediction, CascadeAnalysis, ActionPlan, ProposedAction, ApprovalGateResult, ExecuteResult, VerificationResult, ReplanResult, Claim, Citation, Chunk, Document, Approval, ApprovalStatus, ApprovalDecision, Action, ActionStatus, StateChange, ActionVerification, Alert, SimStatus, InjectEvent, StateSnapshot, Event, EventType`.

`Event` is a discriminated union on `type`; `Extract<Event, { type: 'zone.state' }>['payload']` is how a task names one payload.

Parallelism: Tasks 1→2→3→4→5→6→7→8→9 are sequential (each consumes the previous interface). Tasks 10, 11, 12, 13, 14, 15 are independent of each other and may run in parallel after Task 9; each owns one directory under `src/components/`. Task 16 integrates.

---

### Task 1: Scaffold, tooling and design tokens

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/eslint.config.js`, `frontend/index.html`, `frontend/.env.development`, `frontend/.env.mock`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/tokens.css`, `frontend/src/test/setup.ts`, `frontend/src/vite-env.d.ts`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: `npm run dev`, `npm run dev:mock`, `npm run build`, `npm test`, `npm run typecheck`, `npm run lint`, `npm run gen:api` (gen:api is wired in Task 3 but the script entry exists now); path alias `@/*` → `src/*`; `import.meta.env.VITE_API_MODE: 'http' | 'mock'`.

- [ ] **Step 1: Scaffold with Vite**

Run from repo root:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install @tanstack/react-query zustand recharts @fontsource-variable/archivo
npm install -D typescript@~5.9.3 tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @types/node openapi-typescript eslint typescript-eslint eslint-plugin-react-hooks eslint-plugin-react-refresh globals @vitejs/plugin-react
```
Delete the template's `src/App.css`, `src/index.css`, `src/assets/`, `public/vite.svg`. Confirm `npx tsc --version` prints `5.9.x`.

- [ ] **Step 2: package.json scripts**

Replace the `scripts` block with:
```json
"scripts": {
  "dev": "vite",
  "dev:mock": "vite --mode mock",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "test": "vitest run",
  "test:watch": "vitest",
  "typecheck": "tsc -b --noEmit",
  "lint": "eslint .",
  "gen:api": "openapi-typescript openapi.yaml -o src/api/schema.d.ts"
}
```
Set `"private": true`, `"name": "gridline-frontend"`, `"type": "module"`.

- [ ] **Step 3: Vite, Vitest and TS config**

`vite.config.ts`:
```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
});
```

`vitest.config.ts`:
```ts
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      globals: false,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }),
);
```

`tsconfig.app.json` compilerOptions must include: `"strict": true, "noUncheckedIndexedAccess": true, "noImplicitOverride": true, "noFallthroughCasesInSwitch": true, "noUnusedLocals": true, "noUnusedParameters": true, "exactOptionalPropertyTypes": false, "jsx": "react-jsx", "moduleResolution": "bundler", "baseUrl": ".", "paths": { "@/*": ["src/*"] }, "types": ["vite/client", "vitest/globals", "@testing-library/jest-dom"]` and `"include": ["src"]`. Keep the template's `tsconfig.json` references to app and node configs.

`src/test/setup.ts`:
```ts
import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());

// Recharts ResponsiveContainer and the map use ResizeObserver; jsdom lacks it.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverStub);
```

`src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_MODE?: 'http' | 'mock';
}
```

`.env.development` contains `VITE_API_MODE=http`. `.env.mock` contains `VITE_API_MODE=mock`.

- [ ] **Step 4: ESLint flat config**

`eslint.config.js`:
```js
import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'src/api/schema.d.ts'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked, ...tseslint.configs.stylisticTypeChecked],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: { project: ['./tsconfig.app.json', './tsconfig.node.json'], tsconfigRootDir: import.meta.dirname },
    },
    plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
    },
  },
);
```
If `@eslint/js` is not installed, `npm install -D @eslint/js`.

- [ ] **Step 5: Tokens and shell**

Create `src/styles/tokens.css` with exactly the `@theme` block from Global Constraints, then append:
```css
:root { color-scheme: dark; }
html, body, #root { height: 100%; }
body { margin: 0; background: var(--color-page); color: var(--color-ink); font-family: var(--font-sans); font-size: 13px; line-height: 1.45; -webkit-font-smoothing: antialiased; }
.tnum { font-variant-numeric: tabular-nums; }
.condensed { font-stretch: 80%; }
:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 1px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
```
If `@fontsource-variable/archivo/wdth.css` does not resolve, import `@fontsource-variable/archivo` instead and note it.

`index.html`: title `GridLine AI`, `<div id="root">`, `<script type="module" src="/src/main.tsx">`; add `<meta name="color-scheme" content="dark">`.

`src/main.tsx`:
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@/styles/tokens.css';
import App from '@/App';

const el = document.getElementById('root');
if (!el) throw new Error('#root missing');
createRoot(el).render(<StrictMode><App /></StrictMode>);
```

`src/App.tsx` (temporary; Task 9 replaces it):
```tsx
export default function App() {
  return <main className="h-full bg-page text-ink p-4"><h1 className="condensed text-lg">GridLine AI</h1></main>;
}
```

- [ ] **Step 6: Write the smoke test**

`src/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '@/App';

describe('App', () => {
  it('renders the product name', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'GridLine AI' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run everything**

Run: `npm test` → 1 passed. `npm run typecheck` → no output. `npm run lint` → no errors. `npm run build` → `dist/` produced. `npm run dev` starts on 5173 (stop it after confirming). Fix anything that fails before finishing.

---

### Task 2: UI primitives

**Files:**
- Create: `src/components/ui/Panel.tsx`, `SeverityChip.tsx`, `StatusDot.tsx`, `Button.tsx`, `EmptyState.tsx`, `LoadingState.tsx`, `ErrorState.tsx`, `KeyValue.tsx`, `Drawer.tsx`, `icons.tsx`, `bandLabel.ts`
- Test: `src/components/ui/ui.test.tsx`

**Interfaces:**
- Produces:
```ts
// Panel.tsx
export function Panel(props: { title: string; count?: number; actions?: ReactNode; children: ReactNode; className?: string; testId?: string }): JSX.Element;
// body is `overflow-auto min-h-0`, header is 32px, panel is `flex flex-col h-full bg-panel border border-line`.

// bandLabel.ts
export type BandName = 'normal' | 'watch' | 'warning' | 'critical';
export const BAND_ORDER: readonly BandName[] = ['normal', 'watch', 'warning', 'critical'];
export function bandLabel(b: BandName): string;               // 'Normal' | 'Watch' | 'Warning' | 'Critical'
export function bandRank(b: BandName): number;                // 0..3
export function maxBand(bands: readonly BandName[]): BandName; // 'normal' for empty

// SeverityChip.tsx
export function SeverityChip(props: { band: BandName; size?: 'sm' | 'md' }): JSX.Element;
// fill bg-band-<b>, ink text on watch/warning, white text on critical/normal; text = bandLabel(b); data-band attr.

// StatusDot.tsx
export type DotStatus = 'running' | 'finished' | 'ungrounded' | 'failed' | 'pending' | 'open' | 'reconnecting' | 'closed';
export function StatusDot(props: { status: DotStatus; label: string }): JSX.Element; // dot + visible label, role="status"

// Button.tsx
export function Button(props: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger'; size?: 'sm' | 'md' }): JSX.Element;

// EmptyState.tsx
export function EmptyState(props: { title: string; body?: string }): JSX.Element; // role="note"
// LoadingState.tsx
export function LoadingState(props: { rows?: number; label?: string }): JSX.Element; // aria-busy, skeleton rows
// ErrorState.tsx
export function ErrorState(props: { message: string; onRetry?: () => void }): JSX.Element; // role="alert", "Try again" button
// KeyValue.tsx
export function KeyValue(props: { items: { label: string; value: ReactNode; muted?: boolean }[]; columns?: 1 | 2 | 3 }): JSX.Element; // <dl>
// Drawer.tsx
export function Drawer(props: { open: boolean; title: string; onClose: () => void; children: ReactNode; width?: number }): JSX.Element | null;
// role="dialog" aria-modal, Escape closes, close button labelled "Close", renders nothing when !open

// icons.tsx — 16px inline SVG components, each accepts { className?: string; title?: string }:
export function IconCheck, IconWarning, IconReplan, IconPending, IconClose, IconZoomIn, IconZoomOut, IconFit, IconPlay, IconPause, IconReset, IconChevron, IconHospital, IconShelter, IconCrew, IconConstruction, IconSensor, IconDrop, IconSlope
```

- [ ] **Step 1: Write failing tests**

`src/components/ui/ui.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Panel } from './Panel';
import { SeverityChip } from './SeverityChip';
import { maxBand, bandLabel } from './bandLabel';
import { Drawer } from './Drawer';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { StatusDot } from './StatusDot';

describe('ui primitives', () => {
  it('Panel shows title and count', () => {
    render(<Panel title="Live events" count={12}><p>body</p></Panel>);
    expect(screen.getByRole('heading', { name: /Live events/ })).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });
  it('SeverityChip renders sentence-case label and data-band', () => {
    render(<SeverityChip band="warning" />);
    const chip = screen.getByText('Warning');
    expect(chip).toHaveAttribute('data-band', 'warning');
  });
  it('bandLabel and maxBand', () => {
    expect(bandLabel('critical')).toBe('Critical');
    expect(maxBand(['normal', 'critical', 'watch'])).toBe('critical');
    expect(maxBand([])).toBe('normal');
  });
  it('Drawer renders when open, closes on Escape and button', () => {
    const onClose = vi.fn();
    const { rerender } = render(<Drawer open={false} title="Why" onClose={onClose}>x</Drawer>);
    expect(screen.queryByRole('dialog')).toBeNull();
    rerender(<Drawer open title="Why" onClose={onClose}>x</Drawer>);
    expect(screen.getByRole('dialog', { name: 'Why' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
  it('EmptyState, ErrorState, StatusDot expose roles and labels', () => {
    const retry = vi.fn();
    render(<><EmptyState title="No incidents" body="Threats appear here." /><ErrorState message="City failed to load" onRetry={retry} /><StatusDot status="running" label="Running" /></>);
    expect(screen.getByRole('note')).toHaveTextContent('No incidents');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(retry).toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent('Running');
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- src/components/ui` → fails, modules not found.

- [ ] **Step 3: Implement**

Implement each file per the interfaces. Styling notes: `Panel` header `flex items-center justify-between h-8 px-3 border-b border-line`, title `condensed text-[13px] font-medium`, count `tnum text-ink-2`; body `flex-1 min-h-0 overflow-auto`. `SeverityChip` classes by band: `bg-band-normal text-white`, `bg-band-watch text-page`, `bg-band-warning text-page`, `bg-band-critical text-white`; `rounded-[3px] px-1.5 text-[11px] font-medium leading-5`. `StatusDot` colours: running `accent` + `animate-pulse`, finished `ok`, ungrounded `band-warning`, failed `band-critical`, pending `ink-3`, open `ok`, reconnecting `band-watch`, closed `band-critical`. `Button` primary `bg-accent text-page hover:bg-accent-strong`, ghost `border border-line hover:bg-raised`, danger `border border-band-critical text-band-critical-text hover:bg-band-critical/10`; `disabled:opacity-50`. `Drawer` fixed right, `bg-raised border-l border-line`, width default 480, registers a `keydown` listener on `document` while open. `LoadingState` renders `rows` divs `h-3 bg-raised animate-pulse`.

- [ ] **Step 4: Run tests, typecheck, lint** → all pass.

---

### Task 3: Interim OpenAPI contract, generated types and fixtures

**Files:**
- Create: `frontend/openapi.yaml`, `src/api/schema.d.ts` (generated), `src/api/types.ts`
- Create: `src/test/fixtures/city.ts`, `src/test/fixtures/incident.ts`, `src/test/fixtures/approval.ts`, `src/test/fixtures/action.ts`, `src/test/fixtures/events.ts`
- Test: `src/api/types.test.ts`

**Interfaces:**
- Produces: every type in "Shared vocabulary" from `@/api/types`; fixtures `cityFixture: City`, `incidentFixture: Incident` (one run with all ten steps finished, `assess` with two claims, `recommend` with three proposed actions), `pendingApprovalFixture: Approval` (three proposed actions, status pending), `executedActionFixture: Action` (dispatch_crew with `state_changes` and verification `verified`), `failedActionFixture: Action` (verification failed with one failure), `eventsFixture` object with one sample of each event type, `snapshotEventFixture`.

- [ ] **Step 1: Write the contract**

`openapi.yaml` (OpenAPI 3.1). Paths, exactly:

| Method path | operationId | response |
|---|---|---|
| GET /api/health | getHealth | Health |
| GET /api/llm/status | getLlmStatus | LlmStatus |
| GET /api/city | getCity | City |
| GET /api/events?since&type&limit | listEvents | Event[] |
| GET /api/incidents | listIncidents | IncidentSummary[] |
| GET /api/incidents/{incident_id} | getIncident | Incident |
| GET /api/approvals?status | listApprovals | Approval[] |
| POST /api/approvals/{approval_id}/decide (body ApprovalDecision) | decideApproval | Approval |
| GET /api/actions | listActions | Action[] |
| GET /api/actions/{action_id} | getAction | Action |
| GET /api/documents/{doc_id} | getDocument | Document |
| GET /api/chunks/{chunk_id} | getChunk | Chunk |
| POST /api/simulation/start (body {scenario, speed, seed?}) | startSimulation | SimStatus |
| POST /api/simulation/pause, /resume, /reset | pause/resume/resetSimulation | SimStatus |
| POST /api/simulation/speed (body {speed}) | setSimulationSpeed | SimStatus |
| POST /api/simulation/inject (body InjectEvent) | injectScenarioEvent | SimStatus |

`components.schemas` (all required unless marked `?`; enums as listed):

```
Health { status: 'ok'; version: string }
LlmStatus { provider: 'anthropic'|'mock'|'none'; model: string|null }
XY { x: number; y: number }
ViewBox { x: number; y: number; width: number; height: number }
Band enum normal|watch|warning|critical ; Hazard enum landslide|flood
ZoneState { saturation: number; rain_24h_mm: number; rain_intensity_mm_h: number; landslide_index: number; flood_index: number; band: Band; updated_sim_time: string }
Zone { id; name; slope_deg: number; soil_type: string; population: integer; drains_to_channel_id?: string|null; svg_path: string; label_xy: XY; state: ZoneState }
Road { id; name; zone_ids: string[]; status: 'open'|'closed'; is_evacuation_route: boolean; is_bridge: boolean; svg_path: string }
Channel { id; name; design_capacity_m3s: number; current_capacity_m3s: number; blocked_fraction: number; downstream_zone_id?: string|null; svg_path: string }
Project { id; name; zone_id; status: 'active'|'halted'; excavation_depth_m: number; planned_depth_m: number; permit_doc_id: string; xy: XY }
Sensor { id; kind: 'rain'|'soil'|'channel'; zone_id; unit: string; xy: XY; last_value?: number|null; last_sim_time?: string|null }
Crew { id; name; status: 'available'|'dispatched'|'en_route'|'on_site'|'blocked'; location_zone_id: string; target_zone_id?: string|null; task?: string|null; xy: XY }
Shelter { id; name; status: 'open'|'closed'; capacity: integer; occupancy: integer; zone_id; xy: XY }
PumpUnit { id; status: 'at_depot'|'deployed'; channel_id?: string|null }
PumpDepot { zone_id; xy: XY; units: PumpUnit[] }
Hospital { id; name; zone_id; beds: integer; xy: XY }
MapFeature { id; kind: 'river'|'hill_contour'|'lake'|'label'; svg_path: string; label?: string|null }
BandThresholds { watch: number; warning: number; critical: number }
Bands { landslide: BandThresholds; flood: BandThresholds }
Injection { id; label }
Scenario { id; name; injections: Injection[] }
City { view_box: ViewBox; zones: Zone[]; roads: Road[]; channels: Channel[]; projects: Project[]; sensors: Sensor[]; crews: Crew[]; shelters: Shelter[]; pump_depot: PumpDepot; hospitals: Hospital[]; map_features: MapFeature[]; bands: Bands; scenarios: Scenario[] }

Citation { id; kind: 'chunk'|'sensor'|'state'|'event'; label: string }
Claim { text: string; citation_ids: string[] }
ContributingFactor { factor: string; value: string; citation_ids: string[] }
CitySnapshotReadings { rain_intensity_mm_h; rain_24h_mm; saturation; landslide_index; flood_index; band: Band }
CitySnapshot { node: 'observe'; zone_id; sim_time; readings: CitySnapshotReadings; project?: { id; name; status; excavation_depth_m; planned_depth_m }|null; channel?: { id; name; current_capacity_m3s; design_capacity_m3s; blocked_fraction }|null; crews: { id; name; status; location_zone_id }[]; open_roads: string[]; closed_roads: string[]; downstream_zone_ids: string[] }
RetrievedChunk { id; doc_id; doc_title; section; kind; score: number }
RetrievedChunks { node: 'retrieve'; chunks: RetrievedChunk[] }
ThreatAssessment { node: 'assess'; hazard: Hazard; summary: string; contributing_factors: ContributingFactor[]; confidence: number; claims: Claim[] }
RiskPrediction { node: 'predict'; probability_band: 'low'|'moderate'|'high'|'very_high'; time_horizon: string; onset_sim_time?: string|null; what_would_change_it: string[]; claims: Claim[] }
CascadeLink { cause; effect; affected_asset_ids: string[]; citation_ids: string[] }
CascadeAnalysis { node: 'cascade'; chain: CascadeLink[]; affected_zone_ids: string[]; claims: Claim[] }
ProposedAction { action_id; tool: string; input: object (additionalProperties true); rationale; expected_effect; citation_ids: string[]; requires_approval: boolean }
ActionPlan { node: 'recommend'; actions: ProposedAction[] }
ApprovalGateResult { node: 'approval_gate'; approval_id?: string|null; auto_approved_action_ids: string[]; pending_action_ids: string[] }
ExecuteResult { node: 'execute'; action_ids: string[] }
PerActionVerification { action_id; status: 'verified'|'partially_verified'|'failed'|'pending'; expected: string; observed: string; failures: string[] }
VerificationResult { node: 'verify'; status: 'verified'|'partially_verified'|'failed'; per_action: PerActionVerification[] }
ReplanResult { node: 'replan'; reason: string }
StepOutput oneOf [CitySnapshot, RetrievedChunks, ThreatAssessment, RiskPrediction, CascadeAnalysis, ActionPlan, ApprovalGateResult, ExecuteResult, VerificationResult, ReplanResult] discriminator propertyName node
NodeName enum observe|retrieve|assess|predict|cascade|recommend|approval_gate|execute|verify|replan
AgentStep { id; run_id; node: NodeName; status: 'running'|'finished'|'ungrounded'|'failed'; started_at; finished_at?: string|null; duration_ms?: number|null; output: StepOutput|null; citations: Citation[] }
AgentRun { id; incident_id; thread_id; trigger: string; replan_reason?: string|null; status: 'running'|'waiting_approval'|'finished'|'failed'; started_at; finished_at?: string|null; steps: AgentStep[] }
ApprovalStatus enum pending|approved|rejected|partial
Approval { id; run_id; incident_id; proposed_actions: ProposedAction[]; status: ApprovalStatus; requested_at; decided_at?: string|null; decided_by?: string|null; note?: string|null; approved_action_ids: string[]; synthetic: boolean }
ApprovalDecision { decision: 'approve'|'reject'|'partial'; approved_action_ids: string[]; note?: string|null }
StateChange { entity_type: 'crew'|'shelter'|'road'|'project'|'channel'|'pump_unit'|'alert'; entity_id; entity_name; field; from: string; to: string }
ActionVerification { status: 'verified'|'partially_verified'|'failed'|'pending'; expected: string; observed: string; failures: string[]; checked_sim_time?: string|null }
ActionStatus enum pending|executing|executed|failed
Action { id; run_id; incident_id; tool: string; input: object; status: ActionStatus; executed_at?: string|null; executed_sim_time?: string|null; state_changes: StateChange[]; verification?: ActionVerification|null }
Alert { id; zone_id; level: 'advisory'|'warning'|'evacuate'; message; issued_at; issued_sim_time }
IncidentSummary { id; zone_id; hazard: Hazard; band: Band; status: 'open'|'closed'; opened_at; opened_sim_time; closed_at?: string|null; run_count: integer; pending_approval_count: integer }
Incident { id; zone_id; hazard; band; status; opened_at; opened_sim_time; closed_at?: string|null; runs: AgentRun[]; approvals: Approval[]; actions: Action[] }
Chunk { id; doc_id; doc_title; section; kind; text; metadata: object }
DocumentSection { id; heading; text }
Document { id; title; kind; sections: DocumentSection[] }
SimStatus { scenario: string|null; running: boolean; speed: number; sim_time: string|null; tick: integer }
InjectEvent { id: string }
StateSnapshot { city: City; sim: SimStatus; llm: LlmStatus; incidents: Incident[]; approvals: Approval[]; actions: Action[]; alerts: Alert[] }

EventBase { id; ts; sim_time: string|null; incident_id?: string|null }
Event oneOf (each = allOf [EventBase, { type: const; payload }]) with discriminator type:
  StateSnapshotEvent  type 'state.snapshot'   payload StateSnapshot
  SimTickEvent        'sim.tick'              { sim_time; tick: integer; running: boolean; speed: number }
  SensorReadingEvent  'sensor.reading'        { sensor_id; kind: 'rain'|'soil'|'channel'; zone_id; value: number; unit }
  ZoneStateEvent      'zone.state'            ZoneState & { zone_id; prev_band?: Band|null }
  ThreatDetectedEvent 'threat.detected'       { incident_id; zone_id; hazard; band; prev_band?: Band|null; index: number }
  ThreatEscalatedEvent 'threat.escalated'     same payload as threat.detected
  IncidentOpenedEvent 'incident.opened'       Incident
  IncidentClosedEvent 'incident.closed'       Incident
  AgentRunStartedEvent 'agent.run.started'    AgentRun
  AgentRunFinishedEvent 'agent.run.finished'  AgentRun
  AgentNodeStartedEvent 'agent.node.started'  { run_id; incident_id; node: NodeName; step_id }
  AgentNodeFinishedEvent 'agent.node.finished' AgentStep
  ApprovalRequestedEvent 'approval.requested' Approval
  ApprovalDecidedEvent 'approval.decided'     Approval
  ActionExecutedEvent 'action.executed'       Action
  ActionVerifiedEvent 'action.verified'       { action_id; verification: ActionVerification }
  ReplanTriggeredEvent 'replan.triggered'     { incident_id; run_id; reason }
  AlertIssuedEvent    'alert.issued'          Alert
  ScenarioEvent       'scenario.event'        { name; description }
EventType enum of the 19 type strings above
```
Use `type: string, enum: ['sim.tick']` for the `type` const on each event variant (openapi-typescript emits a literal type).

- [ ] **Step 2: Generate and re-export**

Run `npm run gen:api`. Then `src/api/types.ts`:
```ts
import type { components, paths } from './schema';

type S = components['schemas'];
export type Health = S['Health'];
export type LlmStatus = S['LlmStatus'];
// ... one line per name in Shared vocabulary, e.g.
export type Event = S['Event'];
export type EventType = S['EventType'];
export type StepOutput = S['StepOutput'];
export type Paths = paths;
export type EventOf<T extends Event['type']> = Extract<Event, { type: T }>;
```
Verify with `npx tsc -p tsconfig.app.json --noEmit` that `Event` is a union (hover or add a temporary `const x: EventOf<'zone.state'>['payload']['zone_id'] = ''`).

- [ ] **Step 3: Write the type test and fixtures (they are the test)**

`src/api/types.test.ts`:
```ts
import { describe, expect, it } from 'vitest';
import type { Event, EventOf } from './types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { cityFixture } from '@/test/fixtures/city';
import { incidentFixture } from '@/test/fixtures/incident';

describe('generated contract', () => {
  it('event union discriminates on type', () => {
    const e: Event = eventsFixture['zone.state'];
    if (e.type === 'zone.state') {
      const p: EventOf<'zone.state'>['payload'] = e.payload;
      expect(p.zone_id).toBe('hillview');
    } else { throw new Error('wrong type'); }
  });
  it('fixtures carry every event type', () => {
    expect(Object.keys(eventsFixture).sort()).toEqual([
      'action.executed','action.verified','agent.node.finished','agent.node.started','agent.run.finished','agent.run.started',
      'alert.issued','approval.decided','approval.requested','incident.closed','incident.opened','replan.triggered',
      'scenario.event','sensor.reading','sim.tick','state.snapshot','threat.detected','threat.escalated','zone.state'].sort());
    expect(snapshotEventFixture.type).toBe('state.snapshot');
  });
  it('city fixture has six zones and a run with ten steps', () => {
    expect(cityFixture.zones.map(z => z.id)).toEqual(['hillview','riverside','old_town','market_ward','station_road','lakeside']);
    expect(incidentFixture.runs[0]?.steps).toHaveLength(10);
  });
});
```

Fixtures. `city.ts` exports `cityFixture: City` with six zones (ids above; Hillview slope 32, population 4200; Riverside 18500; Old Town 26000; Market Ward 22400; Station Road 15800; Lakeside 9600), channels `d7` ("D-7 Kalinadi drain", downstream riverside, blocked_fraction 0), `d3`, `d11`; roads `hill_road` (zone_ids [riverside, hillview]), `riverside_bypass` (evacuation), `b04` ("Kalinadi Bridge B-04", is_bridge); project `ht_phase2` ("Hillview Terrace Phase 2", permit `permit-ht-2026-014`, planned 6, depth 3.5); sensors `RG-01..04`, `SM-01..03`, `CL-D7`, `CL-D3`; crews `c1` "Rescue Team 01" (old_town), `c2` "Rescue Team 02" (station_road), `c3` "Rescue Team 03" (market_ward), all `available`; shelters `s1` "Market Ward School" cap 400 closed, `s2` "Station Road Hall" cap 600 closed; pump depot station_road with `p1..p4` at_depot; hospitals `h1` "Nandipur General", `h2` "Riverside Clinic"; map_features river `kalinadi`, lake, three hill contours; bands landslide {0.35,0.55,0.75} flood {0.3,0.5,0.7}; scenarios `hillside_landslide` (injections `crew_route_blocked`, `culvert_blocked`), `flash_flood`. Geometry may be simple placeholders here (`M0 0L10 0L10 10Z`); Task 5 owns the real geometry. `view_box {0,0,1000,700}`. All zone states `normal` with saturation 0.4, indices 0.15/0.1.

`incident.ts` exports `incidentFixture: Incident` id `inc_1`, zone hillview, hazard landslide, band warning, one run `run_1` finished with steps in node order, each `status: 'finished'`, `output` per node. All free text must be visibly synthetic, e.g. `summary: 'fixture: assessment summary'`, claims `text: 'fixture: claim one'` with `citation_ids: ['dmp-2024#s4.2']` and `['sensor:RG-02@2026-07-14T10:30:00']`; `contributing_factors` two entries; `confidence: 0.72`; predict `time_horizon: 'fixture: 6 to 12 hours'`, `onset_sim_time: '2026-07-14T18:00:00'`; cascade chain one link hillview→d7→riverside; recommend actions `act_1` `halt_construction` {project_id: ht_phase2} requires_approval true, `act_2` `dispatch_crew` {crew_id: c3, zone_id: hillview, task: 'fixture: slope watch'} true, `act_3` `schedule_inspection` {asset_id: d7, priority: 'high'} false; approval_gate `{approval_id: 'appr_1', auto_approved_action_ids: ['act_3'], pending_action_ids: ['act_1','act_2']}`; execute `{action_ids: ['act_3']}`; verify status verified; replan reason 'fixture: none'. `citations` on assess step: the two citation objects `{id:'dmp-2024#s4.2', kind:'chunk', label:'Disaster Management Policy §4.2'}` and `{id:'sensor:RG-02@2026-07-14T10:30:00', kind:'sensor', label:'RG-02 rain gauge'}`. Also export `runFixture = incidentFixture.runs[0]!` and `assessStepFixture`.

`approval.ts`: `pendingApprovalFixture: Approval` id `appr_1`, run_1, inc_1, the two pending proposed actions from above plus a third `act_4` `open_shelter` {shelter_id: s1}, status pending, `approved_action_ids: []`, `synthetic: false`; `decidedApprovalFixture` = partial with approved `['act_1']`, note 'fixture: note'.

`action.ts`: `executedActionFixture: Action` id `act_2`, tool dispatch_crew, status executed, `state_changes: [{entity_type:'crew', entity_id:'c3', entity_name:'Rescue Team 03', field:'status', from:'available', to:'dispatched'}]`, verification verified expected 'fixture: crew at hillview' observed 'fixture: crew at hillview'. `failedActionFixture` id `act_5` tool close_road, executed, state_changes road b04 open→closed, verification failed with failures `['fixture: crew C-2 route blocked']`. `pendingActionFixture` verification `{status:'pending', ...}`.

`events.ts`: `eventsFixture: { [K in Event['type']]: EventOf<K> }` with one instance each, ids `evt_<type>`, `ts: '2026-09-26T10:31:04Z'`, `sim_time: '2026-07-14T10:31:04'`; `zone.state` for hillview with `prev_band: 'watch'`, band `warning`, landslide 0.61; `sensor.reading` RG-02 value 84 unit 'mm/h'; `state.snapshot` built from the fixtures (`incidents: [incidentFixture]`, `approvals: [pendingApprovalFixture]`, `actions: [executedActionFixture]`). Export `snapshotEventFixture = eventsFixture['state.snapshot']`.

- [ ] **Step 4: Run** `npm test -- src/api` → pass; `npm run typecheck` → pass. If `oneOf` generated a non-discriminating union, add `discriminator` mapping in the YAML and regenerate.

---

### Task 4: ApiClient interface, HTTP client, provider and query hooks

**Files:**
- Create: `src/api/client.ts`, `src/api/http.ts`, `src/api/ApiClientProvider.tsx`, `src/api/queries.ts`
- Test: `src/api/http.test.ts`, `src/api/queries.test.tsx`

**Interfaces:**
- Consumes: `@/api/types`.
- Produces:
```ts
// client.ts
export type SocketHandlers = { onOpen: () => void; onEvent: (e: Event) => void; onClose: (reason: string) => void; onError: (err: unknown) => void };
export type SocketHandle = { close: () => void };
export type ApiMode = 'http' | 'mock';
export interface ApiClient {
  readonly mode: ApiMode;
  health(): Promise<Health>;
  llmStatus(): Promise<LlmStatus>;
  city(): Promise<City>;
  events(q?: { since?: string; type?: EventType; limit?: number }): Promise<Event[]>;
  incidents(): Promise<IncidentSummary[]>;
  incident(id: string): Promise<Incident>;
  approvals(status?: ApprovalStatus): Promise<Approval[]>;
  decide(id: string, body: ApprovalDecision): Promise<Approval>;
  actions(): Promise<Action[]>;
  action(id: string): Promise<Action>;
  document(docId: string): Promise<Document>;
  chunk(chunkId: string): Promise<Chunk>;
  simulation: {
    start(body: { scenario: string; speed: number; seed?: number }): Promise<SimStatus>;
    pause(): Promise<SimStatus>; resume(): Promise<SimStatus>; reset(): Promise<SimStatus>;
    setSpeed(speed: number): Promise<SimStatus>;
    inject(body: InjectEvent): Promise<SimStatus>;
  };
  openSocket(handlers: SocketHandlers): SocketHandle;
}
export class ApiError extends Error { constructor(public readonly status: number, public readonly body: unknown, message?: string) }
export function readApiMode(env: { VITE_API_MODE?: string } = import.meta.env): ApiMode; // 'mock' only if exactly 'mock'

// http.ts
export class HttpApiClient implements ApiClient {
  constructor(opts?: { baseUrl?: string; fetchImpl?: typeof fetch; wsUrl?: string; WebSocketImpl?: typeof WebSocket });
}
// default baseUrl '/api', default wsUrl derived from location: (https→wss) + host + '/ws'

// ApiClientProvider.tsx
export function ApiClientProvider(props: { client: ApiClient; children: ReactNode }): JSX.Element;
export function useApiClient(): ApiClient; // throws if no provider

// queries.ts (all use useApiClient())
export const queryKeys = { city: ['city'] as const, llm: ['llm'] as const, incidents: ['incidents'] as const, incident: (id: string) => ['incident', id] as const, approvals: (s?: ApprovalStatus) => ['approvals', s ?? 'all'] as const, actions: ['actions'] as const, chunk: (id: string) => ['chunk', id] as const, document: (id: string) => ['document', id] as const };
export function useCity(): UseQueryResult<City>;
export function useLlmStatus(): UseQueryResult<LlmStatus>;   // refetchInterval 15000
export function useIncident(id: string | null): UseQueryResult<Incident>; // enabled: !!id
export function useApprovals(status?: ApprovalStatus): UseQueryResult<Approval[]>;
export function useActions(): UseQueryResult<Action[]>;
export function useChunk(id: string | null): UseQueryResult<Chunk>;
export function useDecideApproval(): UseMutationResult<Approval, ApiError, { id: string; body: ApprovalDecision }>; // invalidates approvals + incident
export function useSimulationControls(): { start: UseMutationResult<SimStatus, ApiError, { scenario: string; speed: number }>; pause; resume; reset; setSpeed; inject }; // each a mutation
```

- [ ] **Step 1: Failing tests**

`src/api/http.test.ts`:
```ts
import { describe, expect, it, vi } from 'vitest';
import { HttpApiClient } from './http';
import { ApiError } from './client';

function fakeFetch(status: number, body: unknown) {
  return vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) =>
    new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }));
}

describe('HttpApiClient', () => {
  it('GETs city from /api/city', async () => {
    const f = fakeFetch(200, { zones: [] });
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.city();
    expect(f.mock.calls[0]?.[0]).toBe('/api/city');
  });
  it('builds event query string', async () => {
    const f = fakeFetch(200, []);
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.events({ since: 'evt_9', type: 'zone.state', limit: 50 });
    expect(f.mock.calls[0]?.[0]).toBe('/api/events?since=evt_9&type=zone.state&limit=50');
  });
  it('POSTs decision body as JSON', async () => {
    const f = fakeFetch(200, { id: 'appr_1' });
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.decide('appr_1', { decision: 'partial', approved_action_ids: ['act_1'], note: 'ok' });
    const [url, init] = f.mock.calls[0] ?? [];
    expect(url).toBe('/api/approvals/appr_1/decide');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ decision: 'partial', approved_action_ids: ['act_1'], note: 'ok' });
  });
  it('throws ApiError with status and body on non-2xx', async () => {
    const c = new HttpApiClient({ fetchImpl: fakeFetch(500, { detail: 'boom' }) as unknown as typeof fetch });
    await expect(c.city()).rejects.toMatchObject<Partial<ApiError>>({ status: 500, body: { detail: 'boom' } });
  });
  it('setSpeed posts to /api/simulation/speed', async () => {
    const f = fakeFetch(200, { running: true });
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.simulation.setSpeed(4);
    expect(f.mock.calls[0]?.[0]).toBe('/api/simulation/speed');
  });
});
```

`src/api/queries.test.tsx`:
```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { ApiClientProvider } from './ApiClientProvider';
import { useCity, useDecideApproval } from './queries';
import type { ApiClient } from './client';
import { cityFixture } from '@/test/fixtures/city';
import { decidedApprovalFixture } from '@/test/fixtures/approval';

export function fakeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const rejectMock = () => Promise.reject(new Error('not implemented'));
  return {
    mode: 'mock', health: rejectMock, llmStatus: rejectMock, city: () => Promise.resolve(cityFixture), events: rejectMock,
    incidents: rejectMock, incident: rejectMock, approvals: () => Promise.resolve([]), decide: rejectMock, actions: rejectMock,
    action: rejectMock, document: rejectMock, chunk: rejectMock,
    simulation: { start: rejectMock, pause: rejectMock, resume: rejectMock, reset: rejectMock, setSpeed: rejectMock, inject: rejectMock },
    openSocket: () => ({ close: () => undefined }),
    ...overrides,
  };
}
function wrapper(client: ApiClient) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}><ApiClientProvider client={client}>{children}</ApiClientProvider></QueryClientProvider>);
}
describe('queries', () => {
  it('useCity loads through the provided client', async () => {
    const { result } = renderHook(() => useCity(), { wrapper: wrapper(fakeClient()) });
    await waitFor(() => expect(result.current.data?.zones).toHaveLength(6));
  });
  it('useDecideApproval calls decide with id and body', async () => {
    const decide = vi.fn(() => Promise.resolve(decidedApprovalFixture));
    const { result } = renderHook(() => useDecideApproval(), { wrapper: wrapper(fakeClient({ decide })) });
    result.current.mutate({ id: 'appr_1', body: { decision: 'approve', approved_action_ids: ['act_1', 'act_2'] } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(decide).toHaveBeenCalledWith('appr_1', { decision: 'approve', approved_action_ids: ['act_1', 'act_2'] });
  });
});
```
Move `fakeClient` into `src/test/fakeClient.ts` and import it from there (tests in later tasks reuse it).

- [ ] **Step 2: Run to verify failure** → modules missing.

- [ ] **Step 3: Implement**

`http.ts` core:
```ts
async function request<T>(fetchImpl: typeof fetch, url: string, init?: RequestInit): Promise<T> {
  const res = await fetchImpl(url, { ...init, headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) } });
  const text = await res.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, body, `${init?.method ?? 'GET'} ${url} failed with ${res.status}`);
  return body as T;
}
```
Query string built with `URLSearchParams`, only defined keys, in the order since, type, limit. `openSocket` creates `new WebSocketImpl(wsUrl)`, wires `onopen→onOpen`, `onmessage→ parse JSON; if parsed.type === 'heartbeat' ignore; else onEvent(parsed as Event)`, `onclose→onClose(String(ev.code))`, `onerror→onError`, returns `{ close: () => ws.close() }`. No reconnect here (Task 8 owns it).

- [ ] **Step 4: Run tests, typecheck, lint** → pass.

---

### Task 5: Nandipur city fixture, replay script and MockApiClient

**Files:**
- Create: `src/mock/fixtures/nandipur.city.json`, `src/mock/replay.ts`, `src/mock/MockApiClient.ts`, `src/mock/MockSocket.ts`
- Test: `src/mock/MockApiClient.test.ts`, `src/mock/replay.test.ts`

**Interfaces:**
- Consumes: `ApiClient`, `SocketHandlers`, `SocketHandle`, `ApiError` from `@/api/client`; types.
- Produces:
```ts
// replay.ts
export type ReplayStep = { tick: number; events: Event[] }; // events for that tick, in order
export function buildReplay(city: City): ReplayStep[];  // deterministic, 72 ticks, primary scenario
export const REPLAY_START_SIM_TIME = '2026-07-14T06:00:00';
export function simTimeAt(tick: number): string; // start + tick*5 minutes, ISO without zone

// MockApiClient.ts
export class MockApiClient implements ApiClient { readonly mode = 'mock'; constructor(opts?: { city?: City; tickMs?: number; now?: () => string }) }
// MockSocket.ts
export class MockSocket implements SocketHandle { ... } // internal; drives setInterval replay
```

- [ ] **Step 1: Author the city geometry**

`nandipur.city.json` is a `City` with `view_box {x:0,y:0,width:1000,height:700}`. Layout (SVG coordinates, y grows downward):

- Zones (closed polygon `svg_path`, `label_xy` near centroid):
  - `hillview` "Hillview": `M620 40 L980 40 L980 300 L700 320 L600 240 Z`, label (800,150), slope_deg 32, soil "colluvium over weathered schist", population 4200, drains_to d7.
  - `riverside` "Riverside": `M560 300 L700 320 L980 300 L980 470 L560 470 Z`, label (770,390), slope 4, soil "alluvial silt", population 18500, drains_to d7.
  - `old_town` "Old Town": `M330 200 L600 240 L560 300 L560 470 L330 450 Z`, label (450,330), slope 6, soil "silty clay", population 26000, drains_to d3.
  - `market_ward` "Market Ward": `M80 180 L330 200 L330 450 L80 420 Z`, label (200,310), slope 5, soil "clay loam", population 22400, drains_to null.
  - `station_road` "Station Road": `M300 470 L980 470 L980 660 L300 660 Z`, label (640,570), slope 3, soil "compacted fill", population 15800, drains_to null.
  - `lakeside` "Lakeside": `M40 420 L300 450 L300 660 L40 660 Z`, label (170,500), slope 2, soil "lacustrine clay", population 9600, drains_to d11.
- Map features: river `kalinadi` kind river `M960 60 C900 200 800 280 700 330 S560 420 460 470 S300 520 230 555`; lake `M60 560 A90 55 0 1 0 240 560 A90 55 0 1 0 60 560 Z` kind lake, label "Nandi Lake"; hill contours kind hill_contour: `M660 90 Q820 20 960 110`, `M690 150 Q820 80 940 170`, `M720 210 Q820 150 920 230`.
- Channels: `d7` "D-7 Kalinadi drain" `M770 235 L725 300 L700 340`, design 12, current 8.5 (narrowed culvert), blocked 0, downstream riverside; `d3` "D-3 Old Town drain" `M420 260 L450 400 L480 450`, 9/9, downstream riverside; `d11` "D-11 Lakeside drain" `M260 470 L225 530`, 6/6, downstream lakeside.
- Roads: `hill_road` "Hill Road" `M640 380 L700 300 L780 200` zone_ids [riverside, hillview], not evac, not bridge; `riverside_bypass` "Riverside Bypass" `M560 460 L700 475 L900 445 L980 405` evac; `b04` "Kalinadi Bridge B-04" `M540 400 L600 380` bridge, zone_ids [old_town, riverside]; `central_avenue` `M100 300 L560 300`; `old_town_ring` `M340 220 L550 220 L550 440 L340 440 Z`; `market_street` `M90 200 L320 400`; `station_road` "Station Road" `M300 560 L760 560`; `lake_drive` `M60 450 L290 640`. All `open`.
- Project `ht_phase2` "Hillview Terrace Phase 2" xy (780,190), active, depth 3.5, planned 6, permit `permit-ht-2026-014`.
- Sensors: RG-01 rain hillview (850,120) mm/h; RG-02 rain hillview (740,250); RG-03 rain old_town (400,250); RG-04 rain lakeside (120,480); SM-01 soil hillview (800,230) unit "%"; SM-02 soil hillview (720,180); SM-03 soil riverside (760,420); CL-D7 channel riverside (705,335) unit "m"; CL-D3 channel old_town (475,445).
- Crews: c1 "Rescue Team 01" old_town (400,380); c2 "Rescue Team 02" station_road (600,600); c3 "Rescue Team 03" market_ward (150,250). Shelters s1 "Market Ward School" (200,330) cap 400; s2 "Station Road Hall" (520,600) cap 600. Pump depot station_road (700,600) units p1..p4. Hospitals h1 "Nandipur General" old_town (470,320) beds 320; h2 "Riverside Clinic" riverside (800,400) beds 60.
- Bands landslide {0.35, 0.55, 0.75}, flood {0.30, 0.50, 0.70}. Scenarios as in Task 3 fixture. Initial zone states: all normal; hillview saturation 0.42 landslide 0.18 flood 0.05 rain_intensity 12 rain_24h 38; riverside saturation 0.38 landslide 0.02 flood 0.08; others saturation 0.35, indices 0.02/0.05, rain 12.

Import JSON with `import cityJson from './fixtures/nandipur.city.json'` and assert it as `City` through one typed constant `export const nandipurCity: City = cityJson as City;` (add `"resolveJsonModule": true` to tsconfig.app.json).

- [ ] **Step 2: Failing replay test**

`src/mock/replay.test.ts`:
```ts
import { describe, expect, it } from 'vitest';
import { buildReplay, simTimeAt } from './replay';
import { nandipurCity } from './MockApiClient';

describe('replay', () => {
  const steps = buildReplay(nandipurCity);
  it('has 72 ticks starting at tick 1 with a sim.tick first in each', () => {
    expect(steps).toHaveLength(72);
    expect(steps[0]?.tick).toBe(1);
    expect(steps.every(s => s.events[0]?.type === 'sim.tick')).toBe(true);
  });
  it('is deterministic', () => { expect(JSON.stringify(buildReplay(nandipurCity))).toBe(JSON.stringify(steps)); });
  it('opens one incident when hillview enters watch and escalates through warning to critical', () => {
    const all = steps.flatMap(s => s.events);
    const opened = all.filter(e => e.type === 'incident.opened');
    expect(opened).toHaveLength(1);
    const bands = all.filter(e => e.type === 'threat.escalated').map(e => (e.type === 'threat.escalated' ? e.payload.band : null));
    expect(bands).toEqual(['warning', 'critical']);
  });
  it('never emits agent, approval, action or verification events', () => {
    const all = steps.flatMap(s => s.events).map(e => e.type);
    expect(all.some(t => t.startsWith('agent.') || t.startsWith('approval.') || t.startsWith('action.') || t === 'replan.triggered')).toBe(false);
  });
  it('simTimeAt adds five minutes per tick', () => { expect(simTimeAt(12)).toBe('2026-07-14T07:00:00'); });
});
```

- [ ] **Step 3: Implement replay**

Deterministic formulas over `t = 1..72` (6 sim-hours):
- `rain(t) = round(12 + 72 * smoothstep((t-6)/60))` mm/h, clamp t≤66 → 84 max; `smoothstep(x)=x<=0?0:x>=1?1:x*x*(3-2x)`.
- Hillview: `sat = 0.42 + 0.40*((t)/72)^1.2` clamp ≤0.82; `landslide = 0.18 + 0.60*((t)/72)^1.1` (crosses 0.35 at t≈20, 0.55 at t≈44, 0.75 at t≈68); `flood = 0.05`.
- Riverside: `sat = 0.38 + 0.25*(t/72)`, `flood = 0.08 + 0.34*smoothstep((t-30)/40)` (crosses 0.30 at t≈55 → riverside band watch), `landslide = 0.02`.
- Other zones: constant.
- Per tick emit: `sim.tick` {sim_time, tick, running true, speed}, `sensor.reading` RG-02 (rain), SM-01 (sat*100, unit %), CL-D7 (0.6 + 1.4*flood, unit m) every tick; `zone.state` for hillview and riverside every tick with `prev_band` when it differs from the previous tick; `threat.detected` + `incident.opened` (incident `inc_mock_1`, hazard landslide, zone hillview, `runs: [], approvals: [], actions: []`) on the tick hillview first reaches watch; `threat.escalated` on warning and critical entries; `threat.detected` for riverside flood watch entry opens a second incident? **No**: emit only `threat.detected` for riverside (no second incident) to keep the mock story single-threaded — document this in a comment. `scenario.event` at t=30 {name:'excavation_depth', description:'Excavation at Hillview Terrace reaches 4.5 m'} and at t=50 {name:'culvert_check', description:'D-7 culvert running at 70% capacity'}.
- Event ids `evt_m_<tick>_<n>`, `ts` from `now()`; sim_time from `simTimeAt(tick)`.
Band from index via city.bands thresholds (`indexBand(hazard, value)` helper exported for reuse).

- [ ] **Step 4: Failing MockApiClient test**

`src/mock/MockApiClient.test.ts`:
```ts
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { MockApiClient } from './MockApiClient';
import type { Event } from '@/api/types';
import { ApiError } from '@/api/client';

describe('MockApiClient', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  function open(c: MockApiClient) {
    const events: Event[] = [];
    const h = c.openSocket({ onOpen: vi.fn(), onEvent: e => events.push(e), onClose: vi.fn(), onError: vi.fn() });
    return { events, h };
  }
  it('sends state.snapshot first and nothing else until started', () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    vi.advanceTimersByTime(5000);
    expect(events.map(e => e.type)).toEqual(['state.snapshot']);
  });
  it('replays ticks at tickMs/speed after start and pauses', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 2 });
    vi.advanceTimersByTime(1500); // 3 ticks at 500ms
    expect(events.filter(e => e.type === 'sim.tick')).toHaveLength(3);
    await c.simulation.pause();
    vi.advanceTimersByTime(3000);
    expect(events.filter(e => e.type === 'sim.tick')).toHaveLength(3);
  });
  it('reset re-sends a fresh snapshot with tick 0', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 1 });
    vi.advanceTimersByTime(2000);
    await c.simulation.reset();
    const snaps = events.filter(e => e.type === 'state.snapshot');
    expect(snaps).toHaveLength(2);
    const last = snaps[1];
    expect(last?.type === 'state.snapshot' && last.payload.sim.tick).toBe(0);
  });
  it('AI-only endpoints reject with 501 and llmStatus reports none', async () => {
    const c = new MockApiClient();
    await expect(c.decide('x', { decision: 'approve', approved_action_ids: [] })).rejects.toBeInstanceOf(ApiError);
    await expect(c.chunk('x')).rejects.toMatchObject({ status: 501 });
    expect(await c.llmStatus()).toEqual({ provider: 'none', model: null });
    expect(await c.approvals()).toEqual([]);
  });
  it('incidents() reflects the opened incident after replay reaches it', async () => {
    const c = new MockApiClient({ tickMs: 10 });
    open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 1 });
    vi.advanceTimersByTime(10 * 72);
    const list = await c.incidents();
    expect(list).toHaveLength(1);
    expect(list[0]?.hazard).toBe('landslide');
  });
});
```

- [ ] **Step 5: Implement MockApiClient and MockSocket**

`MockApiClient` holds `city` (deep copy of JSON), `replay = buildReplay(city)`, `tick = 0`, `running=false`, `speed=1`, `sockets: Set<MockSocket>`, `incidents: Incident[]`, `feed: Event[]`. `openSocket` → creates `MockSocket(handlers)`, calls `handlers.onOpen()` then `handlers.onEvent(snapshotEvent())` synchronously, adds to set. `snapshotEvent()` builds `state.snapshot` from current city state (zone states updated as replay is applied), sim `{scenario, running, speed, sim_time: simTimeAt(tick) or null at 0, tick}`, `llm {provider:'none', model:null}`, `incidents`, `approvals: []`, `actions: []`, `alerts: []`. `start` sets running, `setInterval(tickOnce, tickMs/speed)`; `tickOnce` advances `tick`, applies the step's `zone.state` payloads onto `city.zones[].state` and `incident.opened` onto `incidents` (so REST reflects them), pushes events into `feed`, and emits each to every socket. At tick 72 stops (running=false, emits a final `sim.tick` with running false). `pause` clears the interval; `resume` restarts; `setSpeed` restarts the interval with the new period; `reset` clears, `tick=0`, restores city from JSON, clears incidents, emits a fresh snapshot to every socket; `inject` returns status unchanged (mock has no injections: reject with 501 too). `events(q)` returns `feed` filtered by type and sliced to limit. `incident(id)` finds or rejects 404 `ApiError`. `document`, `chunk`, `decide`, `action`, `actions` → `actions()` resolves `[]`; `action(id)` rejects 404; `decide`, `document`, `chunk`, `inject` reject `new ApiError(501, { detail: 'Not available in mock mode' })`. `health` → `{status:'ok', version:'mock'}`.

- [ ] **Step 6: Run** `npm test -- src/mock` → pass; typecheck; lint.

---

### Task 6: Live state reducer and store

**Files:**
- Create: `src/live/types.ts`, `src/live/applyEvent.ts`, `src/live/liveStore.ts`
- Test: `src/live/applyEvent.test.ts`

**Interfaces:**
- Consumes: `@/api/types`, `BandName` from `@/components/ui/bandLabel`.
- Produces:
```ts
// live/types.ts
export type ConnectionStatus = 'connecting' | 'open' | 'reconnecting' | 'closed';
export type TelemetryPoint = { simTime: string; tick: number; rain: number; saturation: number; landslide: number; flood: number; band: Band };
export type MilestoneKind = 'band' | 'incident' | 'approval' | 'action' | 'verified' | 'replan' | 'alert' | 'scenario';
export type Milestone = { id: string; kind: MilestoneKind; simTime: string | null; ts: string; label: string; zoneId?: string; incidentId?: string; band?: Band };
export interface LiveState {
  connection: ConnectionStatus; mode: ApiMode; hasSnapshot: boolean;
  sim: { simTime: string | null; tick: number; running: boolean; speed: number; scenario: string | null };
  llm: LlmStatus | null;
  city: City | null;                                  // static part; zone.state kept in zoneState
  zoneState: Record<string, ZoneState>;
  incidents: Record<string, Incident>;
  approvals: Record<string, Approval>;
  actions: Record<string, Action>;
  alerts: Alert[];
  assets: { crews: Record<string, Crew>; shelters: Record<string, Shelter>; roads: Record<string, Road>; channels: Record<string, Channel>; projects: Record<string, Project>; pumpUnits: PumpUnit[]; sensors: Record<string, Sensor> };
  feed: Event[];                                      // capped FEED_CAP = 500, newest last
  telemetry: Record<string, TelemetryPoint[]>;        // per zone, capped TELEMETRY_CAP = 720
  milestones: Milestone[];
}
export const FEED_CAP = 500; export const TELEMETRY_CAP = 720;
export function initialLiveState(mode: ApiMode): LiveState;

// applyEvent.ts
export function applyEvent(state: LiveState, event: Event): LiveState; // pure; returns same reference only if nothing changed (never for known events)

// liveStore.ts
export const useLiveStore: UseBoundStore<StoreApi<LiveState & { dispatch: (e: Event) => void; setConnection: (c: ConnectionStatus) => void; setMode: (m: ApiMode) => void; resetLive: () => void }>>;
```

- [ ] **Step 1: Failing tests**

`src/live/applyEvent.test.ts`:
```ts
import { describe, expect, it } from 'vitest';
import { applyEvent } from './applyEvent';
import { initialLiveState, FEED_CAP } from './types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import type { Event } from '@/api/types';

const base = () => applyEvent(initialLiveState('mock'), snapshotEventFixture);

describe('applyEvent', () => {
  it('snapshot replaces everything and sets hasSnapshot', () => {
    const s = base();
    expect(s.hasSnapshot).toBe(true);
    expect(Object.keys(s.zoneState)).toHaveLength(6);
    expect(Object.keys(s.incidents)).toEqual(['inc_1']);
    expect(Object.keys(s.approvals)).toEqual(['appr_1']);
    expect(s.assets.crews['c3']?.status).toBe('available');
  });
  it('a later snapshot replaces, not merges (reconnect)', () => {
    let s = base();
    s = applyEvent(s, eventsFixture['approval.requested']);
    const snap: Event = { ...snapshotEventFixture, payload: { ...snapshotEventFixture.payload, approvals: [] } };
    s = applyEvent(s, snap);
    expect(Object.keys(s.approvals)).toEqual([]);
    expect(s.feed.at(-1)?.type).toBe('state.snapshot');
  });
  it('zone.state updates band and appends telemetry; band change adds a milestone', () => {
    const s = applyEvent(base(), eventsFixture['zone.state']);
    expect(s.zoneState['hillview']?.band).toBe('warning');
    expect(s.telemetry['hillview']?.at(-1)?.landslide).toBeCloseTo(0.61);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'band', zoneId: 'hillview', band: 'warning' });
  });
  it('zone.state for an unknown zone is stored but does not throw', () => {
    const e: Event = { ...eventsFixture['zone.state'], payload: { ...eventsFixture['zone.state'].payload, zone_id: 'ghost' } };
    expect(() => applyEvent(base(), e)).not.toThrow();
  });
  it('agent.node.started then finished adds then replaces a step', () => {
    let s = applyEvent(base(), eventsFixture['agent.run.started']);
    s = applyEvent(s, eventsFixture['agent.node.started']);
    const run = () => s.incidents['inc_1']?.runs.find(r => r.id === eventsFixture['agent.node.started'].payload.run_id);
    expect(run()?.steps.at(-1)?.status).toBe('running');
    s = applyEvent(s, eventsFixture['agent.node.finished']);
    const finished = eventsFixture['agent.node.finished'].payload;
    expect(run()?.steps.filter(st => st.id === finished.id)).toHaveLength(1);
    expect(run()?.steps.find(st => st.id === finished.id)?.status).toBe('finished');
  });
  it('agent.node.finished for an unknown run creates a stub run', () => {
    const e: Event = { ...eventsFixture['agent.node.finished'], payload: { ...eventsFixture['agent.node.finished'].payload, run_id: 'run_ghost' } };
    const s = applyEvent(base(), e);
    expect(s.incidents['inc_1']?.runs.some(r => r.id === 'run_ghost')).toBe(true);
  });
  it('approval.requested and decided update both maps', () => {
    let s = applyEvent(base(), eventsFixture['approval.requested']);
    const id = eventsFixture['approval.requested'].payload.id;
    expect(s.approvals[id]?.status).toBe('pending');
    s = applyEvent(s, eventsFixture['approval.decided']);
    expect(s.approvals[id]?.status).toBe(eventsFixture['approval.decided'].payload.status);
    expect(s.incidents['inc_1']?.approvals.find(a => a.id === id)?.status).toBe(eventsFixture['approval.decided'].payload.status);
  });
  it('action.executed applies state_changes to assets and adds a milestone', () => {
    const s = applyEvent(base(), eventsFixture['action.executed']);
    expect(s.assets.crews['c3']?.status).toBe('dispatched');
    expect(s.milestones.at(-1)?.kind).toBe('action');
  });
  it('action.verified attaches verification', () => {
    let s = applyEvent(base(), eventsFixture['action.executed']);
    s = applyEvent(s, eventsFixture['action.verified']);
    const id = eventsFixture['action.verified'].payload.action_id;
    expect(s.actions[id]?.verification?.status).toBe(eventsFixture['action.verified'].payload.verification.status);
  });
  it('feed is capped', () => {
    let s = base();
    for (let i = 0; i < FEED_CAP + 20; i++) s = applyEvent(s, { ...eventsFixture['sim.tick'], id: `t${i}` });
    expect(s.feed).toHaveLength(FEED_CAP);
    expect(s.feed.at(-1)?.id).toBe(`t${FEED_CAP + 19}`);
  });
  it('unknown event type is appended to the feed and otherwise ignored', () => {
    const weird = { ...eventsFixture['sim.tick'], type: 'future.thing' } as unknown as Event;
    const before = base();
    const s = applyEvent(before, weird);
    expect(s.feed.at(-1)?.type).toBe('future.thing');
    expect(s.zoneState).toBe(before.zoneState);
  });
});
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

`applyEvent` structure:
```ts
export function applyEvent(state: LiveState, event: Event): LiveState {
  const withFeed = { ...state, feed: pushCapped(state.feed, event, FEED_CAP) };
  switch (event.type) {
    case 'state.snapshot': return applySnapshot(withFeed, event.payload, event);
    case 'sim.tick': return { ...withFeed, sim: { ...withFeed.sim, simTime: event.payload.sim_time, tick: event.payload.tick, running: event.payload.running, speed: event.payload.speed } };
    case 'sensor.reading': return updateSensor(withFeed, event.payload);
    case 'zone.state': return applyZoneState(withFeed, event);
    case 'threat.detected': case 'threat.escalated': return addMilestone(withFeed, { kind: 'band', label: ..., zoneId, incidentId, band });
    case 'incident.opened': case 'incident.closed': return { ...withFeed, incidents: { ...withFeed.incidents, [p.id]: p }, milestones: ... };
    case 'agent.run.started': case 'agent.run.finished': return upsertRun(withFeed, p);   // keep existing steps if the payload has none
    case 'agent.node.started': return upsertStep(withFeed, p.incident_id, p.run_id, { id: p.step_id, run_id: p.run_id, node: p.node, status: 'running', started_at: event.ts, output: null, citations: [] });
    case 'agent.node.finished': return upsertStep(withFeed, p.incident_id ?? event.incident_id, p.run_id, p);
    case 'approval.requested': case 'approval.decided': return upsertApproval(withFeed, p, event);
    case 'action.executed': return applyAction(withFeed, p, event);
    case 'action.verified': return attachVerification(withFeed, p, event);
    case 'replan.triggered': return addMilestone(...kind 'replan');
    case 'alert.issued': return { ...withFeed, alerts: [...withFeed.alerts, p], milestones: ... };
    case 'scenario.event': return addMilestone(...kind 'scenario');
    default: return withFeed;
  }
}
```
`agent.node.finished` payload (`AgentStep`) has no `incident_id`; use `event.incident_id`, else find the incident whose runs contain `run_id`, else the single open incident. `upsertStep` creates a stub run `{ id: run_id, incident_id, thread_id: incident_id, trigger: 'unknown', status: 'running', started_at: event.ts, steps: [] }` when missing. Zone state is stored by `zone_id` even for unknown zones (the map filters by city). `applySnapshot` builds `zoneState` from `city.zones[].state`, `assets` maps from the city, resets `feed` to `[event]`? **No** — keep the feed (append), but reset `telemetry` from nothing (backend will resend), and reset `milestones` to those derivable from incidents (`incident` kind per open incident). `applyAction`: for each `state_change`, set `assets[<entity_type>s][entity_id][field] = to` when the entity exists and field is `status` (only status is applied; other fields ignored), pump_unit changes update `pumpUnits[]`. Milestone labels: band `'<Zone name or id>: <Band>'`, incident `'Incident opened: <hazard> in <zone>'`, approval `'Approval requested'` / `'Approval <status>'`, action `'<tool> executed'`, verified `'<tool> <status>'`, replan `'Re-plan: <reason>'`, alert `'Alert (<level>): <zone>'`, scenario `description`.

`liveStore.ts`:
```ts
export const useLiveStore = create<LiveStore>()((set) => ({
  ...initialLiveState(readApiMode()),
  dispatch: (e) => set((s) => applyEvent(s, e)),
  setConnection: (connection) => set({ connection }),
  setMode: (mode) => set({ mode }),
  resetLive: () => set((s) => ({ ...initialLiveState(s.mode), dispatch: s.dispatch, setConnection: s.setConnection, setMode: s.setMode, resetLive: s.resetLive })),
}));
```

- [ ] **Step 4: Run tests, typecheck, lint** → pass.

---

### Task 7: describeEvent and derive selectors

**Files:**
- Create: `src/live/describeEvent.ts`, `src/live/derive.ts`, `src/live/format.ts`
- Test: `src/live/describeEvent.test.ts`, `src/live/derive.test.ts`

**Interfaces:**
- Produces:
```ts
// format.ts
export function fmtSimTime(iso: string | null): string;      // 'HH:mm' from ISO sim time, '—' for null
export function fmtSimTimeSec(iso: string | null): string;   // 'HH:mm:ss'
export function fmtWall(iso: string): string;                // 'HH:mm:ss' local
export function fmtPct(x: number): string;                   // 0.82 → '82%'
export function fmtIndex(x: number): string;                 // '0.71'
export function fmtNumber(n: number): string;                // 18500 → '18,500'
export function toolVerb(tool: string): string;              // halt_construction→'Halt construction', close_road→'Close road', deploy_pumps→'Deploy pumps', dispatch_crew→'Dispatch crew', open_shelter→'Open shelter', issue_alert→'Issue alert', schedule_inspection→'Schedule inspection', else the raw tool string
export function statusLabel(s: string): string;              // 'en_route' → 'En route' (sentence case, underscores → spaces)

// describeEvent.ts
export type EventGroup = 'simulation' | 'threat' | 'agent' | 'approval' | 'action' | 'alert';
export function eventGroup(type: string): EventGroup;        // sim.tick/sensor.reading/zone.state/scenario.event/state.snapshot → simulation; threat.*, incident.* → threat; agent.*, replan.triggered → agent; approval.* → approval; action.* → action; alert.issued → alert; unknown → simulation
export function describeEvent(e: Event, city: City | null): string; // one line, deterministic, no trailing period

// derive.ts
export type CityStatus = { band: Band; label: string };      // label bandLabel(band)
export function cityStatus(zoneState: Record<string, ZoneState>): CityStatus;
export function activeThreats(incidents: Record<string, Incident>): { hazard: Hazard; count: number; maxBand: Band }[];
export function riskZones(zoneState: Record<string, ZoneState>, city: City | null): { zone: Zone; state: ZoneState }[]; // band ≥ watch, sorted by rank desc
export function preventiveActions(actions: Record<string, Action>, approvals: Record<string, Approval>): { pending: number; executed: number; verified: number; failed: number };
export function resources(assets: LiveState['assets']): { crewsAvailable: number; crewsTotal: number; sheltersOpen: number; shelterCapacityOpen: number; pumpsAtDepot: number; pumpsTotal: number; roadsClosed: number };
export function defaultIncidentId(incidents: Record<string, Incident>): string | null; // open incident with highest band, then earliest opened
export function latestRun(incident: Incident | undefined): AgentRun | undefined;
export function stepOutput<N extends NodeName>(run: AgentRun | undefined, node: N): Extract<StepOutput, { node: N }> | null; // latest finished step for node
export type WhatChanged = { trigger: string; replanReason: string | null; bandTransitions: string[]; readingDeltas: { label: string; from: string; to: string }[] };
export function whatChanged(incident: Incident, run: AgentRun, telemetry: TelemetryPoint[], city: City | null): WhatChanged;
export function zoneName(city: City | null, zoneId: string): string;  // falls back to id
export function entityName(assets: LiveState['assets'], entityType: StateChange['entity_type'], id: string): string;
export function findOpenIncidentForZone(incidents: Record<string, Incident>, zoneId: string): string | null; // highest band open incident for the zone, else null
```

- [ ] **Step 1: Failing tests**

`describeEvent.test.ts` asserts, using `eventsFixture` and `cityFixture`:
```ts
it('describes every fixture event type in one non-empty line', () => {
  for (const e of Object.values(eventsFixture)) {
    const line = describeEvent(e, cityFixture);
    expect(line.length).toBeGreaterThan(3);
    expect(line.includes('\n')).toBe(false);
  }
});
it('specific lines', () => {
  expect(describeEvent(eventsFixture['sensor.reading'], cityFixture)).toBe('Rainfall RG-02 (Hillview) 84 mm/h');
  expect(describeEvent(eventsFixture['zone.state'], cityFixture)).toBe('Hillview: landslide index 0.61, Watch → Warning');
  expect(describeEvent(eventsFixture['action.executed'], cityFixture)).toBe('Dispatch crew executed: Rescue Team 03 Available → Dispatched');
  expect(describeEvent(eventsFixture['incident.opened'], cityFixture)).toBe('Incident opened: landslide risk in Hillview (Warning)');
  expect(describeEvent(eventsFixture['approval.requested'], cityFixture)).toBe('Approval requested for 3 actions');
  expect(eventGroup('agent.node.finished')).toBe('agent');
});
```
`derive.test.ts`: `cityStatus` returns max band; `resources` on snapshot state counts 3/3 crews available, 0 shelters open, 4/4 pumps; `defaultIncidentId` picks the critical open one over a watch one; `stepOutput(run,'assess')?.confidence` is 0.72; `whatChanged` with telemetry points [{landslide 0.4, band watch}, {landslide 0.61, band warning}] returns `bandTransitions: ['Watch → Warning']` and a reading delta for `Landslide index` `'0.40' → '0.61'`; `toolVerb('unknown_tool')` returns `'unknown_tool'`; `statusLabel('en_route')` is `'En route'`.

Lines by type for `describeEvent` (use `zoneName`, `toolVerb`, `statusLabel`, `bandLabel`):
- `state.snapshot` → `'Connected: city state received'`
- `sim.tick` → `'Tick <tick> at <HH:mm>'`
- `sensor.reading` → rain: `'Rainfall <sensor_id> (<zone>) <value> mm/h'`; soil: `'Soil moisture <sensor_id> (<zone>) <value>%'`; channel: `'Channel level <sensor_id> (<zone>) <value> m'`
- `zone.state` → `'<Zone>: landslide index <x>, flood index <y>'`, or with prev_band ≠ band: `'<Zone>: <hazard-with-higher-index> index <x>, <Prev> → <Band>'`
- `threat.detected` → `'Threat detected: <hazard> risk in <Zone> (<Band>)'`; `threat.escalated` → `'Threat escalated: <hazard> in <Zone>, <Prev> → <Band>'`
- `incident.opened` → `'Incident opened: <hazard> risk in <Zone> (<Band>)'`; closed → `'Incident closed: <hazard> in <Zone>'`
- `agent.run.started` → `'Agent run started (<trigger>)'` + `', re-plan: <reason>'` if replan_reason; finished → `'Agent run <status>'`
- `agent.node.started` → `'<Node label> started'`; finished → `'<Node label> finished'` (+ `' (ungrounded)'`). Node labels: observe 'Observe', retrieve 'Retrieve evidence', assess 'Assess threat', predict 'Predict', cascade 'Analyse cascade', recommend 'Recommend actions', approval_gate 'Approval gate', execute 'Execute', verify 'Verify', replan 'Re-plan'.
- `approval.requested` → `'Approval requested for <n> action(s)'`; decided → `'Approval <status>'` + ` by <decided_by>` if present, + ' (auto)' if synthetic
- `action.executed` → `'<Verb> executed'` + for the first state change `': <entity_name> <From> → <To>'`
- `action.verified` → `'Action <action_id> <status label>'` (verified/partially verified/failed)
- `replan.triggered` → `'Re-planning: <reason>'`
- `alert.issued` → `'Alert (<level>) for <Zone>: <message>'`
- `scenario.event` → `description`
- unknown → `type`

- [ ] **Step 2: Run failing; Step 3: Implement; Step 4: pass, typecheck, lint.**

---

### Task 8: LiveSocket with reconnect, useLive hook, uiStore

**Files:**
- Create: `src/live/socket.ts`, `src/live/useLive.ts`, `src/ui/uiStore.ts`, `src/test/FakeSocket.ts`
- Test: `src/live/socket.test.ts`, `src/ui/uiStore.test.ts`

**Interfaces:**
- Produces:
```ts
// socket.ts
export type LiveSocketOptions = { client: ApiClient; onEvent: (e: Event) => void; onStatus: (s: ConnectionStatus) => void; backoffMs?: number[]; setTimeoutImpl?: typeof setTimeout; clearTimeoutImpl?: typeof clearTimeout };
export class LiveSocket { constructor(opts: LiveSocketOptions); start(): void; stop(): void; }
// backoff default [1000, 2000, 4000, 8000, 16000, 30000]; after stop() no further opens; status sequence connecting→open, on close → reconnecting (schedule) …, stop() → closed.

// useLive.ts
export function useLive(client: ApiClient): void; // one LiveSocket per client for the component lifetime; dispatches to useLiveStore, sets connection, sets mode = client.mode

// ui/uiStore.ts
export type LayerId = 'hills' | 'water' | 'zones' | 'drainage' | 'roads' | 'construction' | 'hospitals' | 'shelters' | 'crews' | 'sensors' | 'threats';
export const ALL_LAYERS: readonly LayerId[];
export type EntityRef = { kind: 'zone' | 'road' | 'channel' | 'project' | 'crew' | 'shelter' | 'hospital' | 'sensor' | 'pump_depot'; id: string };
export type WhyTarget = { kind: 'action'; actionId: string; incidentId: string } | { kind: 'step'; stepId: string; runId: string; incidentId: string };
export interface UiState {
  selectedEntity: EntityRef | null; selectedIncidentId: string | null; activeLayers: ReadonlySet<LayerId>;
  whyTarget: WhyTarget | null; sourceCitationId: string | null; feedFilter: EventGroup | 'all'; timelineZoneId: string | null;
  selectEntity: (ref: EntityRef | null) => void; selectIncident: (id: string | null) => void; toggleLayer: (l: LayerId) => void;
  openWhy: (t: WhyTarget) => void; closeWhy: () => void; openSource: (citationId: string) => void; closeSource: () => void;
  setFeedFilter: (f: EventGroup | 'all') => void; setTimelineZone: (id: string | null) => void;
}
export const useUiStore: UseBoundStore<StoreApi<UiState>>;
```

- [ ] **Step 1: Failing tests**

`src/test/FakeSocket.ts`:
```ts
import type { ApiClient, SocketHandlers, SocketHandle } from '@/api/client';
export class FakeSocketFactory {
  handlers: SocketHandlers[] = [];
  closed = 0;
  openSocket = (h: SocketHandlers): SocketHandle => { this.handlers.push(h); return { close: () => { this.closed++; } }; };
  last(): SocketHandlers { const h = this.handlers.at(-1); if (!h) throw new Error('no socket'); return h; }
  attach(client: ApiClient): ApiClient { return { ...client, openSocket: this.openSocket }; }
}
```
`socket.test.ts` (fake timers): start → status `connecting`, one openSocket call; `last().onOpen()` → `open`; `last().onEvent(e)` forwarded; `last().onClose('1006')` → `reconnecting` and a second openSocket after 1000 ms, third after another 2000 ms; `stop()` → `closed`, no more opens after advancing 60 s; heartbeat is not a concern here (http.ts filtered it). `uiStore.test.ts`: `toggleLayer` removes then adds; `selectEntity({kind:'zone',id:'hillview'})` sets selectedEntity; `openWhy`/`closeWhy`.

- [ ] **Step 2: Run failing; Step 3: Implement**

`LiveSocket.start()`: `attempt = 0; connect()`. `connect()`: `onStatus(attempt === 0 ? 'connecting' : 'reconnecting'); handle = client.openSocket({ onOpen: () => { attempt = 0; onStatus('open'); }, onEvent, onClose: () => scheduleReconnect(), onError: () => {/* onClose follows */} })`. `scheduleReconnect()`: if stopped return; `onStatus('reconnecting'); const delay = backoff[Math.min(attempt, backoff.length - 1)]; attempt++; timer = setTimeoutImpl(connect, delay)`. `stop()`: `stopped = true; clearTimeout(timer); handle?.close(); onStatus('closed')`.

`useLive`: `useEffect(() => { const s = new LiveSocket({ client, onEvent: dispatch, onStatus: setConnection }); setMode(client.mode); s.start(); return () => s.stop(); }, [client])` with `dispatch`, `setConnection`, `setMode` read from `useLiveStore.getState()` inside the effect (stable).

`uiStore`: `selectEntity` also sets `selectedIncidentId` when kind is zone and an open incident exists for that zone — the store cannot see `liveStore`, so `selectEntity` accepts an optional second argument `incidentIdForZone?: string | null`; components pass `findIncidentForZone(...)`. Provide `export function findOpenIncidentForZone(incidents: Record<string, Incident>, zoneId: string): string | null` in `derive.ts` (Task 7 owner adds it; if missing, add it here with its test).

- [ ] **Step 4: Run tests, typecheck, lint** → pass.

---

### Task 9: App shell, overview strip, scenario bar and mode banner

**Files:**
- Create: `src/components/scenario/ScenarioBar.tsx`, `ProviderBadge.tsx`, `ModeBanner.tsx`, `ConnectionDot.tsx`
- Create: `src/components/overview/OverviewStrip.tsx`, `StatTile.tsx`
- Create: `src/components/layout/Dashboard.tsx`, `src/components/layout/PanelSlot.tsx`
- Create: `src/hooks/useSelectedIncident.ts`
- Modify: `src/App.tsx`, `src/main.tsx`
- Test: `src/components/overview/OverviewStrip.test.tsx`, `src/components/scenario/ScenarioBar.test.tsx`, `src/App.test.tsx`

**Interfaces:**
- Consumes: everything above.
- Produces:
```ts
// hooks/useSelectedIncident.ts
export function useSelectedIncident(): { incident: Incident | undefined; incidentId: string | null; run: AgentRun | undefined; zoneId: string | null };
// selectedIncidentId from uiStore, else defaultIncidentId(liveStore.incidents)

// layout/Dashboard.tsx
export function Dashboard(props: { map: ReactNode; timeline: ReactNode; feed: ReactNode; incident: ReactNode; approvals: ReactNode; actions: ReactNode }): JSX.Element;
// CSS grid: grid-template-columns 58fr 42fr; rows: overview 64px, banner auto, then 3 rows 55fr 22fr 23fr, scenario bar 44px; height 100vh; overflow hidden; each cell min-h-0

// overview/StatTile.tsx
export function StatTile(props: { label: string; value: string; detail?: string; band?: BandName; onClick?: () => void; testId?: string }): JSX.Element;
// scenario/ScenarioBar.tsx
export function ScenarioBar(): JSX.Element; // uses useLiveStore sim, useUiStore, useSimulationControls, useCity for scenarios, useLlmStatus
export function ProviderBadge(props: { llm: LlmStatus | null }): JSX.Element; // 'Anthropic <model>' | 'Mock reasoner' | 'No backend'
export function ModeBanner(props: { mode: ApiMode; connection: ConnectionStatus }): JSX.Element | null; // mock → 'Mock data. Backend not connected.'; http & not open → 'Connection lost. Reconnecting…' / 'Connecting…'
export function ConnectionDot(props: { connection: ConnectionStatus }): JSX.Element;
```

- [ ] **Step 1: Failing tests**

`OverviewStrip.test.tsx`: render with a `useLiveStore` seeded via `useLiveStore.setState(applyEvent(initialLiveState('mock'), snapshotEventFixture))` in `beforeEach`; expect tiles labelled `City status` (value `Warning`, since incident fixture band warning; the tile's band derives from zone bands — set fixture zone hillview band to warning in the snapshot city or dispatch `eventsFixture['zone.state']` first), `Active threats` (`1`), `Risk zones`, `Preventive actions`, `Active incidents` (`1`), `Emergency resources` (`3 of 3 crews available`); clicking `Active incidents` calls `useUiStore.getState().selectedIncidentId === 'inc_1'`. Also a test: with `initialLiveState` (no snapshot) tiles render `—` and `aria-busy`.

`ScenarioBar.test.tsx`: with `fakeClient` whose `simulation.start` is a `vi.fn` resolving `{running:true,...}`; clicking `Start` calls it with `{ scenario: 'hillside_landslide', speed: 1 }`; when `sim.running` is true the button reads `Pause`; `ProviderBadge` renders `No backend` for `{provider:'none', model:null}` and `Anthropic claude-opus-5` for anthropic; `ModeBanner` mock renders the banner text and `http` + `open` renders nothing; `ModeBanner` with `mode: 'http'` and `connection: 'reconnecting'` renders `Connection lost. Reconnecting…`, and with the store seeded from the snapshot and `setConnection('reconnecting')` the `OverviewStrip` still shows `Active incidents` = `1` (panels keep their last data while reconnecting).

`App.test.tsx` (replace): render `<App client={new MockApiClient({ tickMs: 100000 })} />`, expect the six panel titles (`City map`, `Risk timeline`, `Live events`, `Incident`, `Approvals`, `Actions`) and the mock banner; App accepts an optional `client` prop for tests and otherwise builds one from `readApiMode()`.

- [ ] **Step 2: Run failing; Step 3: Implement**

`App.tsx`:
```tsx
export default function App(props: { client?: ApiClient }) {
  const client = useMemo(() => props.client ?? createApiClient(readApiMode()), [props.client]);
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } }));
  return (
    <QueryClientProvider client={qc}><ApiClientProvider client={client}><Shell /></ApiClientProvider></QueryClientProvider>);
}
function Shell() { const client = useApiClient(); useLive(client); return <Dashboard map={<PanelSlot title="City map" />} ... />; }
```
`createApiClient(mode)` in `src/api/client.ts` (add now): returns `new MockApiClient()` (dynamic import is unnecessary; static import is fine) or `new HttpApiClient()`. `PanelSlot` is a `Panel` with an `EmptyState` "Coming in a later task" placeholder — Task 16 replaces slots with the real panels. The `OverviewStrip` sits in the Dashboard's first row and the `ScenarioBar` in the last (Dashboard renders them itself). Stat tiles: `condensed` values 26px, label 11px `text-ink-2`, band tile `border-l-2 border-band-<band>` and value in `text-band-<band>-text`. `ScenarioBar`: scenario `<select aria-label="Scenario">` from `city.scenarios`, `Start`/`Pause`/`Resume` button (one button whose label follows state), `Reset`, speed `<select aria-label="Speed">` 0.25/0.5/1/2/4/10, `Inject` `<select>` disabled when no injections or mode mock, sim clock `tnum` (`fmtSimTimeSec`), `ConnectionDot`, `ProviderBadge`. Mutations show inline error text (`role="alert"`) on failure.

- [ ] **Step 4: Run tests, typecheck, lint, then `npm run dev:mock`**, open http://localhost:5173, press Start, confirm the sim clock advances and the city status tile changes to Watch then Warning within ~45 s. Stop the dev server.

---

### Task 10: City map

**Files:**
- Create: `src/components/map/CityMap.tsx`, `useViewBox.ts`, `MapControls.tsx`, `LayerLegend.tsx`, `EntityPopover.tsx`, `mapStyles.ts`, `layers/HillsLayer.tsx`, `layers/WaterLayer.tsx`, `layers/ZonesLayer.tsx`, `layers/DrainageLayer.tsx`, `layers/RoadsLayer.tsx`, `layers/AssetsLayer.tsx` (construction, hospitals, shelters, crews, sensors, pump depot), `layers/ThreatLayer.tsx`
- Test: `src/components/map/CityMap.test.tsx`, `src/components/map/useViewBox.test.ts`

**Interfaces:**
- Consumes: `useCity`, `useLiveStore` (zoneState, assets, incidents, alerts), `useUiStore`, `BandName`, `SeverityChip`, `KeyValue`, icons.
- Produces:
```ts
export function CityMap(): JSX.Element; // Panel titled 'City map' with LayerLegend as panel action; loading/error from useCity
export function useViewBox(initial: ViewBox): { viewBox: ViewBox; viewBoxAttr: string; zoomAt: (factor: number, cx: number, cy: number) => void; panBy: (dx: number, dy: number) => void; fit: () => void; }
export function zoomViewBox(vb: ViewBox, factor: number, cx: number, cy: number, initial: ViewBox): ViewBox; // pure; factor>1 zooms in; clamps scale to [0.5x, 8x] of initial
export const LAYER_LABELS: Record<LayerId, string>; // 'Hills', 'Rivers and lakes', 'Zones', 'Drainage', 'Roads', 'Construction', 'Hospitals', 'Shelters', 'Emergency teams', 'Sensors', 'Threat overlay'
```

- [ ] **Step 1: Failing tests**

`useViewBox.test.ts`: `zoomViewBox({0,0,1000,700}, 2, 500, 350, init)` → `{250,175,500,350}`; zooming out past 0.5x clamps; `panBy(10, 20)` shifts x,y.

`CityMap.test.tsx` (seed `useLiveStore` with the snapshot fixture; provide `QueryClientProvider` + `ApiClientProvider` with `fakeClient()` so `useCity` resolves `cityFixture`; wait for the svg):
```tsx
it('renders one element per zone, road and channel with data attributes', async () => {
  renderMap();
  const svg = await screen.findByRole('img', { name: 'Map of Nandipur' });
  expect(svg.querySelectorAll('[data-layer="zones"] [data-zone-id]')).toHaveLength(6);
  expect(svg.querySelectorAll('[data-layer="roads"] [data-road-id]')).toHaveLength(cityFixture.roads.length);
  expect(svg.querySelectorAll('[data-layer="drainage"] [data-channel-id]')).toHaveLength(3);
});
it('zone fill follows band and click selects the zone and its incident', async () => {
  useLiveStore.getState().dispatch(eventsFixture['zone.state']); // hillview → warning
  renderMap();
  const hill = await screen.findByTestId('zone-hillview');
  expect(hill).toHaveAttribute('data-band', 'warning');
  fireEvent.click(hill);
  expect(useUiStore.getState().selectedEntity).toEqual({ kind: 'zone', id: 'hillview' });
  expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
});
it('layer toggle hides the group', async () => {
  renderMap();
  await screen.findByRole('img', { name: 'Map of Nandipur' });
  fireEvent.click(screen.getByRole('checkbox', { name: 'Roads' }));
  expect(document.querySelector('[data-layer="roads"]')).toBeNull();
});
it('wheel zooms the viewBox', async () => {
  renderMap();
  const svg = await screen.findByRole('img', { name: 'Map of Nandipur' });
  const before = svg.getAttribute('viewBox');
  fireEvent.wheel(svg, { deltaY: -100, clientX: 0, clientY: 0 });
  expect(svg.getAttribute('viewBox')).not.toBe(before);
});
it('ignores zone.state for zones not in the city', async () => {
  useLiveStore.getState().dispatch({ ...eventsFixture['zone.state'], payload: { ...eventsFixture['zone.state'].payload, zone_id: 'ghost' } });
  renderMap();
  const svg = await screen.findByRole('img', { name: 'Map of Nandipur' });
  expect(svg.querySelectorAll('[data-zone-id="ghost"]')).toHaveLength(0);
});
it('shows a popover with entity fields when a crew is selected', async () => {
  renderMap();
  fireEvent.click(await screen.findByTestId('crew-c3'));
  expect(screen.getByRole('dialog', { name: 'Rescue Team 03' })).toHaveTextContent('Available');
});
```

- [ ] **Step 2: Run failing; Step 3: Implement**

Rendering rules (see spec §6.2). `<svg role="img" aria-label="Map of Nandipur" viewBox=...>` fills the panel; `preserveAspectRatio="xMidYMid meet"`; background `bg-page`. Layer order bottom→top: hills, water, zones, drainage, roads, construction+assets, threats, labels. Zones: `<path data-zone-id data-band data-testid="zone-<id>" tabIndex=0 role="button" aria-label="<name>, <Band>">`, fill `var(--color-band-<band>)` at `fill-opacity` 0.12 (normal) / 0.28 (watch) / 0.36 (warning) / 0.42 (critical), stroke `var(--color-line-strong)` 1, selected → stroke `var(--color-accent)` 2. Zone labels: name in `text-ink` 13px and a tiny band chip drawn as `<text>` below in `text-ink-2`. Drainage: `stroke var(--color-viz-flood)`, dasharray `6 4`, width `1 + 3 * current/design`, `stroke var(--color-band-critical)` when `blocked_fraction > 0.3`. Roads: `stroke var(--color-ink-3)` 3, evacuation 5 with `stroke var(--color-accent)` at 60% opacity; closed → `stroke var(--color-band-critical)` dasharray `8 6` and an `×` glyph at the path midpoint (`getPointAtLength` guarded with `typeof path.getTotalLength === 'function'`, else skip). Bridge: double stroke (ink-3 wide + page narrow). Hills: `stroke var(--color-line-strong)` 1 fill none. River: `stroke var(--color-viz-flood)` 6 at 45% opacity; lake filled `viz-flood` 20%. Construction: hatched pattern square 14×14 with `IconConstruction`, grey when halted. Hospitals: `+` in ink on a `raised` circle r 9. Shelters: house glyph, fill `ok` when open else `raised`. Crews: chevron with the crew number, fill by status (available `ok`, dispatched/en_route `accent`, on_site `band-watch`, blocked `band-critical`), `data-testid="crew-<id>"`; en_route → `animation: crewMove 3s ease-in-out infinite alternate` translating toward `target_zone_id` label_xy (CSS `@keyframes` in the component's style tag with `--dx/--dy` custom props). Sensors: r 3 dots `ink-3`, `<title>` with `id last_value unit`. Threat layer: for zones with band critical, a second path with `class="animate-pulse"` stroke `band-critical` 3; for `alerts` with level evacuate, a hatched ring around that zone's path (`stroke-dasharray 2 6`, width 8, 35% opacity); for each open incident whose latest `cascade` output has `chain`, an arrow `<line marker-end>` from the source zone label to each `affected_zone_ids` label, `stroke band-warning`. All entities call `selectEntity({kind, id}, findOpenIncidentForZone(...))`. `EntityPopover`: an absolutely positioned `role="dialog" aria-label=<name>` inside the panel with `KeyValue` of the entity's relevant fields (zone: band, population, slope, saturation, indices; crew: status, location, task; shelter: status, capacity/occupancy; road: status, evacuation route; channel: capacity current/design, blocked; project: status, depth/planned, permit; sensor: last value; hospital: beds) and a Close button. `MapControls`: buttons `Zoom in`, `Zoom out`, `Fit` (aria-labels) bottom-right. Wheel: `zoomAt(e.deltaY < 0 ? 1.2 : 1/1.2, cx, cy)` with cx,cy computed from `clientX/Y` relative to `getBoundingClientRect()` mapped into viewBox space (rect width 0 in jsdom → treat as centre). Drag: pointerdown/move/up with `setPointerCapture`; pan in viewBox units.

- [ ] **Step 4: Run tests, typecheck, lint.** Then wire `CityMap` into `App` in place of the map `PanelSlot`, run `npm run dev:mock`, start the sim, and confirm Hillview turns amber then orange then red with the pulse; toggle layers; zoom. Stop the server.

---

### Task 11: Event feed

**Files:**
- Create: `src/components/events/EventFeed.tsx`, `EventRow.tsx`, `FeedFilters.tsx`
- Test: `src/components/events/EventFeed.test.tsx`

**Interfaces:**
- Consumes: `useLiveStore` (feed, city), `useUiStore` (feedFilter), `describeEvent`, `eventGroup`, `fmtWall`, `fmtSimTimeSec`.
- Produces: `export function EventFeed(): JSX.Element;` (Panel 'Live events', count = visible rows); `export function EventRow(props: { event: Event; city: City | null; onSelectIncident: (id: string) => void }): JSX.Element;`

- [ ] **Step 1: Failing tests**

Seed the store with the snapshot then dispatch `sensor.reading`, `zone.state`, `approval.requested`. Tests: rows render in dispatch order with the `describeEvent` text and sim time `10:31:04`; the `Approvals` filter chip leaves one row; filter `All` restores; the panel count equals visible rows; when the store has no snapshot, the empty state reads `Events appear here as the city runs.`; rows with `incident_id` show an `Incident` tag that, when clicked, selects that incident in `uiStore`; the pill `New events` appears when `scrollTop` is not at the bottom and new events arrive (simulate by setting `scrollTop = 0` on the list element with a large `scrollHeight` via `Object.defineProperty`, then dispatching an event) and disappears on click.

- [ ] **Step 2: Run failing; Step 3: Implement**

`EventFeed`: `<ul role="log" aria-live="polite">` inside the panel body; each `EventRow` is `<li>` with `grid-cols-[56px_56px_1fr_auto]`: wall time (`text-ink-3 tnum`), sim time (`text-ink-2 tnum`), text (`text-ink`), incident tag (`Button ghost size sm`). Left border 2 px tinted by group: simulation `line-strong`, threat `band-watch`, agent `accent`, approval `band-warning`, action `ok`, alert `band-critical`. New rows get `animate-[fadeIn_300ms]`. Auto-scroll: `useEffect` on `feed.length` scrolls to bottom if `atBottom` (tracked via `onScroll`: `scrollHeight - scrollTop - clientHeight < 8`); otherwise set `pendingCount++` and show the pill `New events (n)`. `FeedFilters`: chips `All, Simulation, Threats, Agent, Approvals, Actions, Alerts` (`role="radiogroup"`, each `role="radio" aria-checked`). Hide `sim.tick` rows when the filter is `All`? **No** — show them; they are the heartbeat of the demo, but render them in `text-ink-3`.

- [ ] **Step 4: Run tests, typecheck, lint.**

---

### Task 12: Risk timeline

**Files:**
- Create: `src/components/timeline/RiskTimeline.tsx`, `RainChart.tsx`, `IndexChart.tsx`, `TimelineTooltip.tsx`, `timelineData.ts`
- Test: `src/components/timeline/RiskTimeline.test.tsx`, `src/components/timeline/timelineData.test.ts`

**Interfaces:**
- Consumes: `useLiveStore` (telemetry, milestones, city), `useUiStore` (timelineZoneId), `useSelectedIncident`, `fmtSimTime`, band tokens.
- Produces:
```ts
export function RiskTimeline(props: { size?: { width: number; height: number } }): JSX.Element; // Panel 'Risk timeline' with zone <select aria-label="Zone">; size only for tests
export type TimelineRow = { simTime: string; label: string; rain: number; saturation: number; landslide: number; flood: number };
export function buildRows(points: TelemetryPoint[]): TimelineRow[];             // label = fmtSimTime
export function milestoneMarkers(milestones: Milestone[], zoneId: string, rows: TimelineRow[]): { simTime: string; label: string; kind: MilestoneKind }[]; // only milestones for this zone or its incidents whose simTime exists in rows
```

- [ ] **Step 1: Failing tests**

`timelineData.test.ts`: `buildRows` maps fields and labels `HH:mm`; `milestoneMarkers` keeps zone-matching milestones with matching simTime only.

`RiskTimeline.test.tsx` (seed store with snapshot + three `zone.state` events for hillview with rising landslide 0.30, 0.40, 0.61 and sim times 10:00, 10:05, 10:10; render with `size={{width: 800, height: 400}}`): expect a `Rain intensity (mm/h)` heading and an `Indices` heading; expect the legend items `Landslide index`, `Flood index`, `Saturation`; expect threshold labels `Watch 0.35`, `Warning 0.55`, `Critical 0.75` (landslide bands) in the document; the zone select defaults to `hillview` (selected incident zone); switching to `riverside` (no telemetry) shows the empty state `No readings yet for Riverside.`; with an empty store the panel shows `Readings appear here once the simulation runs.`

- [ ] **Step 2: Run failing; Step 3: Implement**

Recharts 3. Two `ComposedChart`s in a `flex-col`; the top one gets 30% height, the bottom 70%; both share `XAxis dataKey="simTime" tickFormatter=fmtSimTime` with the same domain, `syncId="risk"`. Rain: `<Bar dataKey="rain" fill="var(--color-viz-rain)" radius={[4,4,0,0]} maxBarSize={24} />`, `YAxis` unit ` mm/h` width 44. Indices: `<Area dataKey="saturation" stroke="var(--color-viz-saturation)" fill="var(--color-viz-saturation)" fillOpacity={0.1} strokeWidth={2} dot={false} name="Saturation" />`, `<Line dataKey="landslide" stroke="var(--color-viz-landslide)" strokeWidth={2} dot={false} name="Landslide index" />`, `<Line dataKey="flood" stroke="var(--color-viz-flood)" strokeWidth={2} dot={false} name="Flood index" />`, `YAxis domain={[0,1]} ticks={[0,0.25,0.5,0.75,1]}`. `CartesianGrid stroke="var(--color-viz-grid)" vertical={false}` (solid, no dash). Threshold `ReferenceLine y=<t> stroke="var(--color-ink-3)" strokeDasharray="4 4"` — dashed is allowed here because it *is* a threshold, with `label={{ value: 'Watch 0.35', position: 'right', fill: 'var(--color-band-watch-text)', fontSize: 10 }}` (which hazard's bands: the selected incident's hazard, default landslide). Milestone `ReferenceDot` at `(simTime, 0.98)` r 4 `fill var(--color-ink)` with a `<title>` and tooltip. `Legend` bottom, `iconType="plainline"`. `Tooltip content={<TimelineTooltip/>}` listing every series with a short line key and `tnum` values, cursor as a hairline. When `size` is given render charts with explicit `width/height`; otherwise `ResponsiveContainer`. `RiskTimeline` panel body: filter row (zone select) above the charts, left aligned. Reduced motion: `isAnimationActive={false}` always (live data; animation is noise).

- [ ] **Step 4: Run tests, typecheck, lint.**

---

### Task 13: Incident panel — threat card, reasoning trace, citations, source drawer

**Files:**
- Create: `src/components/incident/IncidentPanel.tsx`, `ThreatCard.tsx`, `ReasoningTrace.tsx`, `NodeRail.tsx`, `ClaimList.tsx`, `CitationChip.tsx`, `SourceDrawer.tsx`, `RunAccordion.tsx`, `nodeLabels.ts`
- Test: `src/components/incident/ThreatCard.test.tsx`, `ReasoningTrace.test.tsx`, `SourceDrawer.test.tsx`

**Interfaces:**
- Consumes: `useSelectedIncident`, `useLiveStore`, `useUiStore` (openWhy, openSource, sourceCitationId, closeSource), `useChunk`, `stepOutput`, `whatChanged`, `latestRun`, `zoneName`, `fmtPct`, `fmtIndex`, `fmtNumber`, ui primitives.
- Produces:
```ts
export function IncidentPanel(): JSX.Element; // Panel 'Incident' (count = open incidents); incident switcher <select aria-label="Incident"> when >1 open; ThreatCard + ReasoningTrace; SourceDrawer mounted here
export function ThreatCard(props: { incident: Incident; run: AgentRun | undefined; zone: Zone | undefined; zoneState: ZoneState | undefined; cascadeZones: Zone[] }): JSX.Element;
export function ReasoningTrace(props: { incident: Incident; telemetry: TelemetryPoint[]; city: City | null }): JSX.Element;
export function NodeRail(props: { run: AgentRun | undefined }): JSX.Element; // 9 or 10 nodes, status dots, aria-label per node
export function ClaimList(props: { claims: Claim[]; citations: Citation[] }): JSX.Element;
export function CitationChip(props: { citation: Citation | { id: string } }): JSX.Element; // button, label or id, kind glyph; onClick → openSource(id)
export function SourceDrawer(): JSX.Element | null; // reads sourceCitationId; chunk kind → useChunk; sensor/state/event kinds → shows the id and the matching live value if available
export const NODE_LABELS: Record<NodeName, string>; // same labels as Task 7's describeEvent
export const NODE_ORDER: readonly NodeName[];
```

- [ ] **Step 1: Failing tests**

`ThreatCard.test.tsx`: with `incidentFixture` and its run: shows `Landslide`, `Hillview`, `Warning` chip, `Confidence 72%`, `Population 4,200` (plus cascade zone riverside → `Population 22,700` when `cascadeZones=[riverside]`), `Estimated onset` value containing `fixture: 6 to 12 hours`, factor chips for each contributing factor with a `CitationChip`. With `run: undefined`: confidence shows `Awaiting assessment`, onset `Awaiting prediction`, factors `Awaiting assessment`.

`ReasoningTrace.test.tsx`: node rail has 10 dots with `aria-label` like `Assess threat: finished`; sections `Why this threat?`, `What changed?`, `What evidence supports it?` present; `Why this threat?` shows `fixture: assessment summary` and two claims each with citation chips; `What evidence supports it?` lists retrieved chunk titles; clicking chip `Disaster Management Policy §4.2` sets `useUiStore.getState().sourceCitationId === 'dmp-2024#s4.2'`; with an incident with `runs: []` shows `No agent run yet for this incident. Reasoning appears here as each node finishes.`; a step with `status: 'ungrounded'` renders the dot label `Assess threat: ungrounded` and a warning line `Grounding check failed; confidence lowered.`; each step row has a `Why?` button which calls `openWhy({kind:'step', ...})`.

`SourceDrawer.test.tsx`: with `sourceCitationId='dmp-2024#s4.2'` and a `fakeClient` whose `chunk` resolves `{ id, doc_id:'dmp-2024', doc_title:'Disaster Management Policy', section:'s4.2', kind:'policy', text:'fixture: chunk text', metadata:{} }`, the dialog shows the title, section and text; with a rejecting `chunk` shows `Source could not be loaded.` and a `Try again` button; with `sourceCitationId='sensor:RG-02@2026-07-14T10:30:00'` shows `Live reading` and the sensor id without calling `chunk`.

- [ ] **Step 2: Run failing; Step 3: Implement**

`ThreatCard`: header row: hazard glyph (`IconSlope` for landslide, `IconDrop` for flood) + `Landslide risk` / `Flood risk` condensed 15px + zone name + `SeverityChip`. `KeyValue columns=3`: `Confidence`, `Population at risk`, `Estimated onset`, `Landslide index` (`zoneState`), `Saturation`, `Rain intensity`. Factors as a wrapping row of chips: `factor: value` + `CitationChip` per id. `ReasoningTrace`: `RunAccordion` per run (latest open; header `Run <n> · trigger` → write it as `Run 2, triggered by band change` with no dot separators), containing `NodeRail` then the three sections as `<section aria-labelledby>` with `<h3>`. "What changed?" uses `whatChanged(incident, run, telemetry, city)` bullets plus cascade chain rendered as `<ol>` of `cause → effect` rows (arrow as `IconChevron`). Evidence section: retrieved chunks table (title, section, kind, score `tnum`) and all citations deduped. Each step row: `StatusDot`, `NODE_LABELS[node]`, duration `tnum` ms, `Why?` ghost button. `CitationChip`: `Button ghost size sm` with glyph by kind (chunk `§`, sensor `IconSensor`, state `IconDrop`, event `IconPending`) and `label ?? id`, `title={id}`. `SourceDrawer` uses `Drawer` titled `Source`.

- [ ] **Step 4: Run tests, typecheck, lint.**

---

### Task 14: Approvals inbox

**Files:**
- Create: `src/components/approvals/ApprovalsInbox.tsx`, `ApprovalCard.tsx`, `ProposedActionCard.tsx`, `DecisionBar.tsx`, `actionTarget.ts`
- Test: `src/components/approvals/ApprovalsInbox.test.tsx`, `src/components/approvals/actionTarget.test.ts`

**Interfaces:**
- Consumes: `useLiveStore` (approvals, actions, assets, city), `useSelectedIncident`, `useDecideApproval`, `useUiStore.openWhy`, `toolVerb`, `entityName`, `CitationChip`, ui primitives.
- Produces:
```ts
export function ApprovalsInbox(): JSX.Element; // Panel 'Approvals' (count = pending for all incidents); pending first (all incidents, selected incident's first), decided collapsed under 'Decided'
export function ApprovalCard(props: { approval: Approval; actions: Record<string, Action>; onDecide: (body: ApprovalDecision) => void; deciding: boolean; error: string | null }): JSX.Element;
export function ProposedActionCard(props: { action: ProposedAction; state: ProposedActionState; selectable: boolean; selected: boolean; onToggle: () => void; onWhy: () => void; targetName: string }): JSX.Element;
export type ProposedActionState = 'proposed' | 'auto_approved' | 'approved' | 'rejected' | 'executing' | 'executed' | 'verified' | 'failed';
export function proposedActionState(a: ProposedAction, approval: Approval, executed: Action | undefined): ProposedActionState;
export function DecisionBar(props: { total: number; selected: number; onApproveAll: () => void; onApproveSelected: () => void; onReject: () => void; note: string; onNote: (s: string) => void; disabled: boolean }): JSX.Element;
// actionTarget.ts
export function actionTargetName(tool: string, input: Record<string, unknown>, assets: LiveState['assets'], city: City | null): string; // project/road/crew/shelter/channel/zone/asset name from input ids; falls back to the first string value in input; '' if none
```

- [ ] **Step 1: Failing tests**

`actionTarget.test.ts`: `halt_construction {project_id:'ht_phase2'}` → `Hillview Terrace Phase 2`; `dispatch_crew {crew_id:'c3', zone_id:'hillview'}` → `Rescue Team 03 to Hillview`; `deploy_pumps {channel_id:'d7', units:2}` → `D-7 Kalinadi drain, 2 units`; unknown tool `{foo:'bar'}` → `bar`.

`ApprovalsInbox.test.tsx` (seed snapshot which includes `pendingApprovalFixture`; provide `fakeClient({ decide })`):
```
- lists three proposed action cards with verbs 'Halt construction', 'Dispatch crew', 'Open shelter', rationale and expected effect text, evidence chips, and state chip 'Proposed'
- 'Approve 3 actions' calls decide('appr_1', { decision: 'approve', approved_action_ids: ['act_1','act_2','act_4'], note: null })
- unchecking one card changes the primary button to 'Approve 2 actions' and posts decision 'partial' with the two ids
- 'Reject plan' with a typed note posts { decision: 'reject', approved_action_ids: [], note: 'fixture: too early' }
- buttons are disabled while the mutation is pending (decide returns a never-resolving promise) and the card shows 'Sending decision…'
- when decide rejects with ApiError(500,...), an alert 'Decision failed (500). Try again.' appears and buttons re-enable
- an approval whose action has tool 'do_something_new' renders the raw tool name 'do_something_new' as the verb
- a decided approval (dispatch approval.decided) moves under 'Decided' with chip 'Partial' and the synthetic flag renders 'Auto-approved (demo)' when synthetic
- empty: 'No approvals waiting. Proposed actions appear here when the agent asks for a decision.'
```

- [ ] **Step 2: Run failing; Step 3: Implement**

`ApprovalCard` keeps `selected: Set<string>` initialised to all `proposed_actions` ids that `requires_approval`; auto-approved (not requires_approval) cards are shown with chip `Auto-approved` and no checkbox. `DecisionBar` primary `Approve N actions` (N = selected; when N equals total → decision `approve`, else `partial`; disabled when N = 0), `Reject plan` (danger), `<textarea aria-label="Note">` placeholder `Note for the record (optional)`. Card layout: checkbox, verb + target (`condensed` 14px), `SeverityChip`-style state chip using ink tokens (proposed `raised`, approved `accent`, rejected `band-critical`, executed `ok`, verified `ok`, failed `band-critical`), rationale paragraph, `Expected effect` line, evidence chips, `Why?` ghost button → `openWhy({ kind:'action', actionId, incidentId })`. Mutation via `useDecideApproval`; `error` from `ApiError.status`.

- [ ] **Step 4: Run tests, typecheck, lint.**

---

### Task 15: Actions log with state transitions and verification

**Files:**
- Create: `src/components/actions/ActionsLog.tsx`, `ActionRow.tsx`, `StateTransition.tsx`, `VerificationBadge.tsx`
- Test: `src/components/actions/ActionsLog.test.tsx`

**Interfaces:**
- Consumes: `useLiveStore` (actions, incidents, milestones, assets, sim), `useUiStore.openWhy`, `toolVerb`, `statusLabel`, `fmtSimTime`, icons.
- Produces:
```ts
export function ActionsLog(): JSX.Element; // Panel 'Actions' (count = actions), newest first, all incidents
export function ActionRow(props: { action: Action; replanning: boolean; onWhy: () => void }): JSX.Element;
export function StateTransition(props: { change: StateChange }): JSX.Element; // "<entity_name>  <From> → <To>" with aria-label "<entity_name> changed from <from> to <to>"
export type VerificationState = 'verified' | 'partially_verified' | 'failed' | 'pending' | 'replanning';
export function VerificationBadge(props: { state: VerificationState; failures?: string[]; ticksWaited?: number }): JSX.Element; // ✓ Verified / ⚠ Partially verified / ⚠ Failed / ◌ Verifying… / ↻ Re-planning ; icon + text always
export function verificationState(action: Action, replanRunIds: ReadonlySet<string>): VerificationState;
```

- [ ] **Step 1: Failing tests**

Seed snapshot (contains `executedActionFixture`), then: row shows `Dispatch crew`, `Rescue Team 03`, transition text `Available → Dispatched` (arrow as text, `aria-label` present), badge `Verified` with `IconCheck`; expected vs observed columns show both strings; dispatch `failedActionFixture` via `action.executed` → badge `Failed` and the failure line `fixture: crew C-2 route blocked`; dispatch `replan.triggered` with `run_id === failedActionFixture.run_id` → badge `Re-planning`; an action with `verification: {status:'pending'}` shows `Verifying…`; `Why?` calls `openWhy({ kind:'action', actionId, incidentId })`; empty: `No actions yet. Approved actions appear here as they execute.`

- [ ] **Step 2: Run failing; Step 3: Implement**

`ActionRow`: header line verb + target (from `state_changes[0]?.entity_name` or `actionTargetName`), sim time `tnum`, `VerificationBadge`; body: `StateTransition` list (`<ul>`), then a two-column `Expected` / `Observed` block (`KeyValue columns=2`), failures in `text-band-critical-text`. `StateTransition`: `entity_name` in `text-ink`, `From` chip muted, `→` in `text-ink-3`, `To` chip in `ok` when the change is to open/dispatched/deployed/halted/closed for roads… keep it simple: `To` chip uses `accent` always. Badge colours: verified `ok-text`, partially/failed `band-critical-text`, pending `ink-2` with `IconPending` spinning (`animate-spin`), replanning `band-watch-text` with `IconReplan`.

- [ ] **Step 4: Run tests, typecheck, lint.**

---

### Task 16: Why drawer, final integration and quality pass

**Files:**
- Create: `src/components/why/WhyDrawer.tsx`, `src/components/why/whyContent.ts`
- Modify: `src/App.tsx` (replace all `PanelSlot`s), `src/components/layout/Dashboard.tsx` (mount `WhyDrawer`), delete `src/components/layout/PanelSlot.tsx`
- Test: `src/components/why/WhyDrawer.test.tsx`, update `src/App.test.tsx`

**Interfaces:**
- Consumes: `useUiStore` (whyTarget, closeWhy), `useLiveStore`, `stepOutput`, `CitationChip`, `KeyValue`, `Drawer`.
- Produces:
```ts
export function WhyDrawer(): JSX.Element | null;
export type WhyContent = { title: string; summary: string | null; expectedEffect: string | null; evidence: RetrievedChunk[]; citations: Citation[]; cityState: CitySnapshot | null; missing: string[] }; // missing = node labels not finished yet
export function buildWhyContent(target: WhyTarget, incidents: Record<string, Incident>): WhyContent;
```

- [ ] **Step 1: Failing tests**

`WhyDrawer.test.tsx`: seed snapshot; `openWhy({kind:'action', actionId:'act_1', incidentId:'inc_1'})` → dialog `Why: Halt construction` with sections `Reasoning summary` (rationale + expected effect), `Retrieved evidence` (chunk titles from the run's retrieve step), `Citations` (chips), `Relevant city state` (`KeyValue` with saturation, indices, project depth, channel capacity, crews); clicking a citation chip opens the source (`sourceCitationId` set); `openWhy({kind:'step', stepId: assess step id, runId:'run_1', incidentId:'inc_1'})` → title `Why: Assess threat`, summary is the assessment summary; for an incident whose run lacks `observe` and `retrieve` steps the sections read `Observe has not finished yet.` / `Retrieve evidence has not finished yet.`; Escape closes.

`App.test.tsx`: render with `MockApiClient({tickMs: 100000})`; all six real panel titles present, mode banner present, `document.body` has no vertical scroll (`getComputedStyle(document.documentElement).overflow` is not asserted in jsdom — instead assert the dashboard root has class `overflow-hidden h-screen`).

- [ ] **Step 2: Run failing; Step 3: Implement**, replace slots in `App`/`Dashboard` with `CityMap`, `RiskTimeline`, `EventFeed`, `IncidentPanel`, `ApprovalsInbox`, `ActionsLog`, mount `WhyDrawer` in `Dashboard`.

- [ ] **Step 4: Full verification**

Run, in order, and paste the outputs into your report:
```
npm test
npm run typecheck
npm run lint
npm run build
```
Then `npm run dev:mock`, open the app, press Start, and confirm: overview tiles move; map zones change band with pulse at critical; feed streams with filters; timeline draws three series, thresholds and markers; incident panel shows the detector fields and `Awaiting assessment`; approvals and actions show their empty states; no console errors; no horizontal or vertical page scroll at 1920×1080 and at 1280×800. Take a screenshot if the environment allows. Stop the server.

- [ ] **Step 5: Quality pass** (frontend-design critique): remove one thing that is decoration rather than information; check every panel's empty-state copy is one sentence in sentence case; check no all-caps strings remain (`grep -rn "uppercase" src/` must return nothing outside tests); check `prefers-reduced-motion` disables pulse/move/fade.

---

## Self-review

**Spec coverage.** §2.1 areas 1→T9, 2→T10, 3→T11, 4/5→T13, 6/7→T14, 8/9→T15, 10→T12, 11→T16. §4.3 data layer→T3/T4, §4.4 live layer→T6/T8, §4.5 ui state→T8, §5 contract→T3, §6 layout→T9, §7 visuals→Global Constraints, §8 mock→T5, §10 tests→every task. §9 backend obligations are encoded in `openapi.yaml` (T3) which the backend plan will consume.

**Type consistency.** `SocketHandlers.onClose(reason: string)` used in T4, T5, T8. `LiveState.assets` shape identical in T6, T7, T14. `WhyTarget` defined in T8, used in T13/T14/T15/T16. `ProposedActionState` only in T14. `findOpenIncidentForZone` lives in `derive.ts` (T7) and is consumed by T8 and T10; T7 must export it — added to T7's Produces list here: `export function findOpenIncidentForZone(incidents: Record<string, Incident>, zoneId: string): string | null;`.

**Review Focus coverage.** 1→T6 test "a later snapshot replaces"; 2→T6 "unknown run creates a stub run"; 3→T6 "unknown zone" + T10 "ignores zone.state for zones not in the city"; 4→T14 "raw tool name"; 5→T8 socket reconnect test + T9 `ModeBanner` http/reconnecting test (add: with `connection:'reconnecting'` and a populated store, OverviewStrip still shows values and the banner reads `Connection lost. Reconnecting…`).
