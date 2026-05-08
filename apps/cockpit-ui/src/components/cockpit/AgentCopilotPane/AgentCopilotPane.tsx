// AgentCopilotPane — Story 4.5.
//
// Right-rail of the case canvas. 8 rows (one per MVP agent) with face +
// name + status pill + relative timestamp. Row click opens the reasoning
// trace slide-out (full content lands in Epic 6).

import { useState } from 'react';
import {
  AgentFace,
  AGENT_LABELS,
  AGENT_ORDER,
  type AgentSlug,
} from '@/components/cockpit/AgentFace';
import { StatusPill, type StatusPillState } from '@/components/cockpit/StatusPill';
import { CockpitChatPanel } from '@/components/cockpit/CockpitChatPanel';
import { ReasoningTraceSlideOut } from '@/components/cockpit/ReasoningTraceSlideOut';
import { useAgentMeshState } from '@/hooks/useAgentMeshState';
import { useAnnouncer } from '@/stores/announcerStore';
import { formatRelative } from '@/lib/formatRelative';
import type { components } from '@/api-types';

type AgentMeshAgentState = components['schemas']['AgentMeshAgentState'];
type AgentMeshAgentEntry = components['schemas']['AgentMeshAgentEntry'];

export interface AgentCopilotPaneProps {
  caseId: string;
}

const _STATE_TO_PILL: Record<Exclude<AgentMeshAgentState, 'idle'>, StatusPillState> = {
  complete: 'done',
  working: 'in-progress',
  blocked: 'blocked',
  needs_input: 'needs-input',
};

const _STATE_TO_FACE: Record<
  AgentMeshAgentState,
  'idle' | 'working' | 'complete' | 'blocked' | 'needs_input'
> = {
  idle: 'idle',
  working: 'working',
  complete: 'complete',
  blocked: 'blocked',
  needs_input: 'needs_input',
};

export function AgentCopilotPane({ caseId }: AgentCopilotPaneProps): JSX.Element {
  const { data, isPending, isError } = useAgentMeshState(caseId);
  const announce = useAnnouncer((s) => s.announce);
  const [openTarget, setOpenTarget] = useState<{
    actionId: string;
    slug: AgentSlug;
  } | null>(null);

  const byAgentSlug = new Map<string, AgentMeshAgentEntry>(
    (data?.agents ?? []).map((a) => [String(a.agent_slug), a]),
  );

  const handleRowClick = (slug: AgentSlug) => {
    const entry = byAgentSlug.get(slug);
    if (!entry || !entry.last_action_id) {
      announce(`No activity yet for ${AGENT_LABELS[slug]}`);
      return;
    }
    setOpenTarget({ actionId: entry.last_action_id, slug });
  };

  return (
    <aside
      data-testid="agent-copilot-pane"
      className="flex h-full max-h-screen w-[280px] flex-shrink-0 flex-col border-l border-zinc-200 bg-white"
      aria-label="Agent copilot"
    >
      <div className="flex-shrink-0 overflow-y-auto p-4">
        <header className="mb-3">
          <h3 className="text-sm font-semibold text-zinc-900">Agent copilot</h3>
          {isError ? (
            <p role="alert" className="mt-1 text-xs text-rose-600">
              Could not load mesh state.
            </p>
          ) : null}
        </header>

        <ul className="flex flex-col gap-1.5">
          {AGENT_ORDER.map((slug) => {
            const entry = byAgentSlug.get(slug);
            const state = (entry?.state ?? 'idle') as AgentMeshAgentState;
            const pillState = state === 'idle' ? null : _STATE_TO_PILL[state];
            const lastAt = entry?.last_activity_at ?? null;
            return (
              <li key={slug}>
                <button
                  type="button"
                  onClick={() => handleRowClick(slug)}
                  className="w-full flex items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 transition-colors duration-100 ease-out"
                  aria-label={`${AGENT_LABELS[slug]} — ${state}`}
                >
                  <AgentFace agent={slug} state={_STATE_TO_FACE[state]} size={28} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-[13px] font-medium text-zinc-900">
                      {AGENT_LABELS[slug]}
                    </span>
                    <span className="truncate text-[11px] text-zinc-500">
                      {lastAt ? formatRelative(lastAt) : isPending ? '…' : 'No activity yet'}
                    </span>
                  </span>
                  {pillState ? <StatusPill state={pillState} /> : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Story 6.8 — Cockpit Chat panel below the agent rows.
          key={caseId} forces a clean remount on case-switch so the
          transcript resets per Story 6.8 / AC #7. Citation clicks open
          the reasoning trace slide-out via the same paired-state setter
          used by row clicks. */}
      <hr className="border-zinc-200" />
      <CockpitChatPanel
        key={caseId}
        caseId={caseId}
        onCitationClick={(ledgerId) => setOpenTarget({ actionId: ledgerId, slug: 'cockpit-chat' })}
      />

      <ReasoningTraceSlideOut
        open={openTarget !== null}
        onOpenChange={(open) => {
          if (!open) setOpenTarget(null);
        }}
        caseId={openTarget ? caseId : null}
        actionId={openTarget?.actionId ?? null}
        agentSlug={openTarget?.slug ?? null}
      />
    </aside>
  );
}
