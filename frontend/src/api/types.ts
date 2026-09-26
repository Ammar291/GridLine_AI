// Named re-exports of the generated contract (schema.d.ts). Never hand-write payload types: backend types come from its
// OpenAPI schema and pending ones from openapi.pending.yaml; run `npm run gen:api` after a contract change.
import type { components } from './schema';

type S = components['schemas'];

// ---- city: GET /api/city and the sim.snapshot frame (static; live state is in WorldSnapshot) ----
export type City = S['CityMap'];
export type ViewBox = S['ViewBox'];
export type XY = S['XY'];
export type Zone = S['MapZone'];
export type Road = S['MapRoad'];
export type Bridge = S['MapBridge'];
export type Channel = S['MapChannel'];
export type Slope = S['MapSlope'];
export type Project = S['MapProject'];
export type Sensor = S['MapSensor'];
export type Crew = S['MapCrew'];
export type Shelter = S['MapShelter'];
export type Hospital = S['MapHospital'];
export type PumpDepot = S['PumpDepot'];
export type PumpUnit = S['PumpUnit'];
export type MapFeature = S['MapFeature'];
export type Scenario = S['ScenarioInfo'];
export type InjectionPreset = S['InjectionPreset'];
export type TriggerInfo = S['TriggerInfo'];
export type TriggerName = S['TriggerName'];

// ---- live world: sim.snapshot, then kept current by events ----
export type WorldSnapshot = S['WorldSnapshot'];
export type ZoneConditions = S['ZoneConditions'];
export type RoadState = S['RoadState'];
export type BridgeState = S['BridgeState'];
export type ChannelState = S['ChannelState'];
export type ProjectState = S['ProjectState'];
export type CrewState = S['CrewState'];
export type ShelterState = S['ShelterState'];
export type HospitalState = S['HospitalState'];
export type SlopeState = S['SlopeState'];
export type FireState = S['FireState'];

// ---- simulation control and sources ----
export type Health = S['Health'];
export type SimulationStatus = S['SimulationStatus'];
export type SimulationStart = S['SimulationStart'];
export type InjectRequest = S['InjectRequest'];
export type TriggerRequest = S['TriggerRequest'];
export type Chunk = S['StoredChunk'];
export type Severity = S['Severity'];

// ---- data source: LIVE (Open-Meteo, Kalyan-Dombivli) or DEMO (Nandipur simulation) ----
export type SourceStatus = S['SourceStatus'];
export type DataMode = SourceStatus['mode'];
export type WeatherObservation = S['WeatherObservation'];
export type WeatherForecast = S['WeatherForecast'];
export type HourlyPrecipitation = S['HourlyPrecipitation'];

// ---- events: the backend's union plus the pending events of later milestones ----
export type Event = S['Event'];
/** The sim.status payload (runner state, scenario, speed, tick). */
export type SimStatus = S['SimStatus'];
export type EventType = Event['event_type'];
export type EventOf<T extends EventType> = Extract<Event, { event_type: T }>;

// ---- risk indices: zone.state and GET /api/detector/bands ----
export type Band = S['Band'];
export type Bands = S['Bands'];
export type BandThresholds = S['BandThresholds'];
/** A zone's indices as the dashboard keeps them: the zone.state payload without its key and previous band. */
export type ZoneState = Omit<S['ZoneStatePayload'], 'zone_id' | 'prev_band'>;

// ---- live agent workflow: agent.step events, sim.snapshot's agent_run, POST /api/agent/runs/{run_id}/approval ----
export type WorkflowRun = S['WorkflowRun'];
export type WorkflowStep = S['WorkflowStep'];
export type WorkflowNode = WorkflowStep['node'];
export type WorkflowStepStatus = WorkflowStep['status'];
export type WorkflowOutput = NonNullable<WorkflowStep['output']>;
export type WorkflowDecision = S['WorkflowDecision'];
export type WorkflowEntity = S['WorkflowEntity'];
export type WorkflowReceiveOutput = S['WorkflowReceiveOutput'];
export type WorkflowObserveOutput = S['WorkflowObserveOutput'];
export type WorkflowGraphOutput = S['WorkflowGraphOutput'];
export type WorkflowPath = S['WorkflowPath'];
export type WorkflowEvidenceOutput = S['WorkflowEvidenceOutput'];
export type WorkflowReasoningOutput = S['WorkflowReasoningOutput'];
export type WorkflowAssessmentOutput = S['WorkflowAssessmentOutput'];
export type WorkflowPlanOutput = S['WorkflowPlanOutput'];
export type WorkflowApprovalOutput = S['WorkflowApprovalOutput'];
export type WorkflowExecutionOutput = S['WorkflowExecutionOutput'];
export type WorkflowVerificationOutput = S['WorkflowVerificationOutput'];
export type WorkflowCompletionOutput = S['WorkflowCompletionOutput'];

// ---- PENDING (openapi.pending.yaml): threat detector, incidents and agent, approvals and actions, alerts, LLM ----
export type LlmStatus = S['LlmStatus'];
export type Hazard = S['Hazard'];
export type IncidentSummary = S['IncidentSummary'];
export type Incident = S['Incident'];
export type IncidentStatus = S['IncidentStatus'];
export type AgentRun = S['AgentRun'];
export type AgentStep = S['AgentStep'];
export type NodeName = S['NodeName'];
export type StepOutput = S['StepOutput'];
export type CitySnapshot = S['CitySnapshot'];
export type RetrievedChunk = S['RetrievedChunk'];
export type RetrievedChunks = S['RetrievedChunks'];
export type ThreatAssessment = S['ThreatAssessment'];
export type ContributingFactor = S['ContributingFactor'];
export type RiskPrediction = S['RiskPrediction'];
export type CascadeAnalysis = S['CascadeAnalysis'];
export type CascadeLink = S['CascadeLink'];
export type ActionPlan = S['ActionPlan'];
export type ProposedAction = S['ProposedAction'];
export type ApprovalGateResult = S['ApprovalGateResult'];
export type ExecuteResult = S['ExecuteResult'];
export type VerificationResult = S['VerificationResult'];
export type PerActionVerification = S['PerActionVerification'];
export type ReplanResult = S['ReplanResult'];
export type Claim = S['Claim'];
export type Citation = S['Citation'];
export type Document = S['Document'];
export type Approval = S['Approval'];
export type ApprovalStatus = S['ApprovalStatus'];
export type ApprovalDecision = S['ApprovalDecision'];
export type Action = S['Action'];
export type ActionStatus = S['ActionStatus'];
export type StateChange = S['StateChange'];
export type ActionVerification = S['ActionVerification'];
export type Alert = S['Alert'];
