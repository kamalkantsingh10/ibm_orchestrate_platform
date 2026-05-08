// /cases/$caseId — case detail route. Story 3.6 AC #6.
//
// Three-column layout:
//   left: 260px QueueRail (existing); center: 2×2 panel grid;
//   right: 280px AgentCopilotPane placeholder (Epic 4).
//
// The 2×2 grid contains the real DocumentsPanel (this story) plus three
// PanelStubs (Identity, UBO, Risk — Epic 5+).

import { useQueryClient } from '@tanstack/react-query';
import { createRoute, redirect, useNavigate } from '@tanstack/react-router';
import * as Tabs from '@radix-ui/react-tabs';
import { useEffect, useState } from 'react';
import { subscribeToCase } from '@/lib/sse';
import { Route as RootRoute } from './__root';
import { useCase } from '@/hooks/useCase';
import { useDocumentIntelligence } from '@/hooks/useDocumentIntelligence';
import { useCases } from '@/hooks/useCases';
import { useScreeningHits } from '@/hooks/useScreeningHits';
import { defaultRouteFor } from '@/lib/routeFor';
import { isValidCaseId } from '@/lib/caseId';
import { apiClient } from '@/lib/api';
import { useCurrentUser } from '@/stores/currentUser';
import { QueueRail } from '@/components/cockpit/QueueRail/QueueRail';
import { DocumentsPanel } from '@/components/cockpit/DocumentsPanel';
import { DocumentUploadZone } from '@/components/cockpit/DocumentUploadZone';
import { RiskPanel } from '@/components/cockpit/RiskPanel';
import { ScreeningPanel } from '@/components/cockpit/ScreeningPanel';
import { UBOPanel } from '@/components/cockpit/UBOPanel';
import { ReasoningTraceSlideOut } from '@/components/cockpit/ReasoningTraceSlideOut';
import { AgentCopilotPane } from '@/components/cockpit/AgentCopilotPane';
import { DecisionZone, useDecisionZoneFocus } from '@/components/cockpit/DecisionZone';
import { EvidenceShelf } from '@/components/cockpit/EvidenceShelf';
import { UndoPill } from '@/components/cockpit/UndoPill';
import { EvidenceShelfDock } from '@/components/cockpit/EvidenceShelf';
import { ZenMode } from '@/components/cockpit/ZenMode';
import { expand, expandVariants, focusDim, focusDimVariants } from '@/lib/motion';
import { AnimatePresence, motion } from 'framer-motion';
import { useMode } from '@/stores/modeStore';
import type { components } from '@/api-types';

type ExtractedField = components['schemas']['ExtractedField'];

type TraceTarget =
  | { mode: 'action'; actionId: string }
  | { mode: 'extracted'; field: ExtractedField };

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: '/cases/$caseId',
  parseParams: (params): { caseId: string } => {
    if (!isValidCaseId(params.caseId)) {
      throw new Error(`Invalid case_id format: ${params.caseId}`);
    }
    return { caseId: params.caseId };
  },
  beforeLoad: () => {
    const { user } = useCurrentUser.getState();
    if (user.role !== 'analyst') {
      throw redirect({ to: defaultRouteFor(user.role) });
    }
  },
  component: CaseDetailRoute,
});

function CaseDetailRoute() {
  const { caseId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const currentUser = useCurrentUser((s) => s.user);
  const isDzFocused = useDecisionZoneFocus();
  const mode = useMode((s) => s.mode);
  const { data: caseEnv, isError: caseError } = useCase(caseId);
  const {
    data: intake,
    isPending: intakePending,
    isError: intakeError,
  } = useDocumentIntelligence(caseId);
  const { data: cases = [] } = useCases();
  const [traceTarget, setTraceTarget] = useState<TraceTarget | null>(null);
  const { data: screeningOutput } = useScreeningHits(caseId);
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  // Story 4.6 — subscribe to the case's SSE stream while mounted.
  // EventSource auto-reconnects on transient drops; cleanup runs on unmount.
  useEffect(() => {
    const unsubscribe = subscribeToCase(caseId, currentUser.id, queryClient);
    return () => unsubscribe();
  }, [caseId, currentUser.id, queryClient]);

  // Story 7.1 — DecisionZone dispatches cockpit:open-trace when the
  // analyst clicks a citation token. Treat the ledgerId as the
  // action_id (agent action ledger entries have id === ledgerId).
  useEffect(() => {
    const handler = (ev: Event) => {
      const detail = (ev as CustomEvent<{ ledgerId: string; caseId?: string }>).detail;
      if (!detail?.ledgerId) return;
      if (detail.caseId && detail.caseId !== caseId) return;
      setTraceTarget({ mode: 'action', actionId: detail.ledgerId });
    };
    window.addEventListener('cockpit:open-trace', handler);
    return () => window.removeEventListener('cockpit:open-trace', handler);
  }, [caseId]);

  const handleUploadComplete = () => {
    void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
  };

  const handleProcess = async () => {
    setProcessing(true);
    setProcessError(null);
    try {
      const { error } = await apiClient.POST('/v1/cases/{case_id}/intake', {
        params: { path: { case_id: caseId } },
      });
      if (error) {
        const detail =
          typeof error === 'object' && error !== null && 'detail' in error
            ? String((error as { detail?: string }).detail)
            : 'Processing failed';
        setProcessError(detail);
      } else {
        void queryClient.invalidateQueries({
          queryKey: ['cases', caseId, 'intake', 'document_intelligence'],
        });
        void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      }
    } finally {
      setProcessing(false);
    }
  };

  if (caseError) {
    return (
      <div role="alert" className="p-8 text-sm text-rose-700">
        Could not load case <code>{caseId}</code>.
      </div>
    );
  }

  // Story 8.2 — Zen mode replaces the dense Investigation layout with
  // a calm writing canvas. Queue rail, agent rail, and the document/UBO
  // grid are intentionally hidden; only the editor + a placeholder
  // evidence dock are visible.
  if (mode === 'zen') {
    return (
      <ZenMode
        caseId={caseId}
        caseName={caseEnv?.customer_metadata?.customer_name ?? null}
        evidenceDock={<EvidenceShelfDock caseId={caseId} />}
      >
        <DecisionZone caseId={caseId} />
      </ZenMode>
    );
  }

  return (
    <div className="flex h-full">
      <aside className="flex-shrink-0">
        <QueueRail
          cases={cases}
          activeCaseId={caseId}
          onSelect={(id) => navigate({ to: '/cases/$caseId', params: { caseId: id } })}
        />
      </aside>

      <main className="flex-1 overflow-y-auto p-6 min-w-0">
        {/* Story 8.1 AC #3 — mode change runs the `expand` preset (250ms)
           into and out of Zen. The wrapper is keyed by mode so
           AnimatePresence treats each mode as a distinct subtree. */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            data-testid="case-canvas-mode-wrapper"
            data-mode={mode}
            variants={expandVariants}
            initial="hidden"
            animate="visible"
            exit="hidden"
            transition={expand}
          >
            <header className="mb-5">
              <h1 className="text-lg font-semibold text-zinc-900">
                {caseEnv?.customer_metadata?.customer_name ?? caseId}
              </h1>
              <p className="text-xs text-zinc-500 font-mono">{caseId}</p>
              {caseEnv?.state ? (
                <span className="inline-block mt-2 px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-700">
                  {caseEnv.state.replace(/_/g, ' ')}
                </span>
              ) : null}
            </header>

            {/* Tab restructure — Overview / UBO / Decision Zone / Upload.
           Only the mid area changes; QueueRail + AgentCopilotPane stay.
           Tabs.Root state lives here so a tab switch doesn't re-mount
           heavy panels. */}
            <Tabs.Root defaultValue="overview" className="flex flex-col gap-4">
              <Tabs.List
                data-testid="case-canvas-tabs"
                className="flex border-b border-zinc-200"
                aria-label="Case sections"
              >
                {[
                  { value: 'overview', label: 'Overview' },
                  { value: 'ubo', label: 'UBO' },
                  { value: 'decision', label: 'Decision Zone' },
                  { value: 'upload', label: 'Upload document' },
                ].map((t) => (
                  <Tabs.Trigger
                    key={t.value}
                    value={t.value}
                    data-testid={`tab-${t.value}`}
                    className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 border-b-2 border-transparent data-[state=active]:text-zinc-900 data-[state=active]:border-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 rounded-t"
                  >
                    {t.label}
                  </Tabs.Trigger>
                ))}
              </Tabs.List>

              <Tabs.Content value="overview" className="focus-visible:outline-none">
                <div className="flex items-center justify-end gap-3 mb-3">
                  {processError ? (
                    <span role="alert" className="text-xs text-rose-600">
                      {processError}
                    </span>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void handleProcess()}
                    disabled={processing}
                    data-testid="overview-process-now"
                    className="text-xs px-3 py-1.5 rounded bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                  >
                    {processing ? 'Processing…' : 'Process now'}
                  </button>
                </div>
                {/* Story 7.2 — focusDim preset dims the grid when DecisionZone
               focused. Tabs unmount-by-default; we keep the motion.div on
               this tab content. */}
                <motion.div
                  className="grid grid-cols-2 gap-4"
                  variants={focusDimVariants}
                  initial="focused"
                  animate={isDzFocused ? 'dimmed' : 'focused'}
                  transition={focusDim}
                  data-testid="case-canvas-grid"
                  data-dz-focused={isDzFocused ? 'true' : 'false'}
                >
                  <div className="col-span-2">
                    <DocumentsPanel
                      output={intake}
                      isPending={intakePending}
                      isError={intakeError}
                      onProvenanceClick={(field) => setTraceTarget({ mode: 'extracted', field })}
                      caseId={caseId}
                      pendingDocumentRefs={
                        (caseEnv?.customer_metadata?.extra?.document_refs as
                          | string[]
                          | undefined) ?? []
                      }
                    />
                  </div>
                  <ScreeningPanel
                    caseId={caseId}
                    onOpenReasoningTrace={(actionId) => {
                      if (!actionId) return;
                      setTraceTarget({ mode: 'action', actionId });
                    }}
                  />
                  <RiskPanel caseId={caseId} />
                </motion.div>
              </Tabs.Content>

              <Tabs.Content value="ubo" className="focus-visible:outline-none">
                {/* UBO gets the full canvas width on its own tab so the
               graph + relationship list have room to breathe. */}
                <UBOPanel caseId={caseId} />
              </Tabs.Content>

              <Tabs.Content value="decision" className="focus-visible:outline-none">
                <DecisionZone
                  caseId={caseId}
                  onToggleEvidence={() => setEvidenceOpen((v) => !v)}
                  evidenceOpen={evidenceOpen}
                />
              </Tabs.Content>

              <Tabs.Content value="upload" className="focus-visible:outline-none">
                <section className="space-y-3">
                  <DocumentUploadZone caseId={caseId} onUploadComplete={handleUploadComplete} />
                </section>
              </Tabs.Content>
            </Tabs.Root>
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Story 7.5 — UndoPill pins itself bottom-center while the
         case is in pending_seal. The component renders nothing
         otherwise. */}
      <UndoPill caseId={caseId} />

      {/* Story 7.8 — read-only evidence shelf; Radix Dialog handles
         portal + focus + Esc. Renders nothing while closed. */}
      <EvidenceShelf caseId={caseId} open={evidenceOpen} onOpenChange={setEvidenceOpen} />

      <AgentCopilotPane caseId={caseId} />

      <ReasoningTraceSlideOut
        open={traceTarget !== null}
        onOpenChange={(open) => {
          if (!open) setTraceTarget(null);
        }}
        caseId={traceTarget?.mode === 'action' ? caseId : null}
        actionId={traceTarget?.mode === 'action' ? traceTarget.actionId : null}
        agentSlug={traceTarget?.mode === 'action' ? 'screening' : null}
        screeningHits={traceTarget?.mode === 'action' ? (screeningOutput?.hits ?? null) : null}
        extractedField={traceTarget?.mode === 'extracted' ? traceTarget.field : null}
      />
    </div>
  );
}
