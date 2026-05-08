// Agent slug → human-readable label map — Story 4.3 AC #5.
// Slugs match `apps/agents/src/agents/registry/<slug>/`.

export type AgentSlug =
  | 'case-supervisor'
  | 'document-intelligence'
  | 'entity-verification'
  | 'ubo-graph'
  | 'screening'
  | 'risk-scoring'
  | 'writing'
  | 'cockpit-chat';

export const AGENT_LABELS: Record<AgentSlug, string> = {
  'case-supervisor': 'Case Supervisor',
  'document-intelligence': 'Document Intelligence',
  'entity-verification': 'Entity Verification',
  'ubo-graph': 'UBO Graph',
  screening: 'Screening',
  'risk-scoring': 'Risk Scoring',
  writing: 'Writing',
  'cockpit-chat': 'Cockpit Chat',
};

/** Canonical render order for the Agent Copilot Pane (Story 4.5). */
export const AGENT_ORDER: AgentSlug[] = [
  'case-supervisor',
  'document-intelligence',
  'entity-verification',
  'ubo-graph',
  'screening',
  'risk-scoring',
  'writing',
  'cockpit-chat',
];
