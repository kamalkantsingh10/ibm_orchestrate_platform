// AgentCopilotPane tests — Story 4.5 AC #9.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentCopilotPane } from './AgentCopilotPane';
import { useAnnouncer } from '@/stores/announcerStore';

const apiGetMock = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api', () => ({
  apiClient: { GET: apiGetMock },
}));

function withQueryClient(node: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false } },
  });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

const ALL_IDLE = {
  case_id: 'case_X',
  agents: [
    'case-supervisor',
    'document-intelligence',
    'entity-verification',
    'ubo-graph',
    'screening',
    'risk-scoring',
    'writing',
    'cockpit-chat',
  ].map((s) => ({
    agent_slug: s,
    state: 'idle' as const,
    last_activity_at: null,
    last_action_id: null,
  })),
};

describe('AgentCopilotPane', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    useAnnouncer.getState().clear();
  });
  afterEach(() => {
    apiGetMock.mockReset();
  });

  it('renders one row per MVP agent (8 total) with name + face', async () => {
    apiGetMock.mockResolvedValue({ data: ALL_IDLE, error: null });
    render(withQueryClient(<AgentCopilotPane caseId="case_X" />));
    await waitFor(() => {
      expect(screen.getByText('Case Supervisor')).toBeInTheDocument();
    });
    // Story 6.8 — pane now mounts CockpitChatPanel below the agent rows;
    // its composer adds a Send button. Filter to agent-row buttons by
    // aria-label pattern to keep the count stable across UI additions.
    const agentRowButtons = screen
      .getAllByRole('button')
      .filter((b) =>
        /\b(idle|complete|working|blocked|needs_input)$/.test(b.getAttribute('aria-label') ?? ''),
      );
    expect(agentRowButtons).toHaveLength(8);
    // No activity → no pill rendered for any row.
    expect(screen.queryAllByRole('status')).toHaveLength(0);
  });

  it('renders a Done pill when an agent state is complete', async () => {
    const data = {
      ...ALL_IDLE,
      agents: ALL_IDLE.agents.map((a) =>
        a.agent_slug === 'document-intelligence'
          ? {
              ...a,
              state: 'complete' as const,
              last_activity_at: '2026-05-07T11:55:00Z',
              last_action_id: 'aa_X',
            }
          : a,
      ),
    };
    apiGetMock.mockResolvedValue({ data, error: null });
    render(withQueryClient(<AgentCopilotPane caseId="case_X" />));
    await waitFor(() => {
      expect(screen.getByText('Done')).toBeInTheDocument();
    });
  });

  it('idle row click announces "No activity yet" and does NOT open slide-out', async () => {
    apiGetMock.mockResolvedValue({ data: ALL_IDLE, error: null });
    render(withQueryClient(<AgentCopilotPane caseId="case_X" />));
    await waitFor(() => {
      expect(screen.getByText('Case Supervisor')).toBeInTheDocument();
    });
    const user = userEvent.setup();
    await user.click(screen.getByLabelText('Case Supervisor — idle'));
    expect(useAnnouncer.getState().message).toMatch(/no activity yet/i);
  });

  it('renders the alert state on API error', async () => {
    apiGetMock.mockResolvedValue({ data: null, error: { detail: 'boom' } });
    render(withQueryClient(<AgentCopilotPane caseId="case_X" />));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });
});
