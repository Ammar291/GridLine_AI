import type { WorkflowStep } from '@/api/types';
import { ApprovalBody } from './ApprovalBody';
import { EvidenceBody, GraphBody, ObserveBody, ReceiveBody } from './EvidenceBodies';
import { CompleteBody, ExecuteBody, VerifyBody } from './OutcomeBodies';
import { AssessBody, PlanBody, ReasonBody } from './ReasoningBodies';

/** The node's actual output, by its discriminator. A node still running has none yet. */
export function StepBody({ step }: { step: WorkflowStep }) {
  const out = step.output;
  if (out === null) return null;
  switch (out.node) {
    case 'receive': return <ReceiveBody out={out} />;
    case 'observe': return <ObserveBody out={out} />;
    case 'query_graph': return <GraphBody out={out} />;
    case 'retrieve': return <EvidenceBody out={out} />;
    case 'reason': return <ReasonBody out={out} />;
    case 'assess': return <AssessBody out={out} />;
    case 'recommend': return <PlanBody out={out} />;
    case 'approval_gate': return <ApprovalBody step={step} out={out} />;
    case 'execute': return <ExecuteBody out={out} />;
    case 'verify': return <VerifyBody out={out} />;
    case 'complete': return <CompleteBody out={out} />;
  }
}
