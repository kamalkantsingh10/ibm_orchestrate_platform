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
import { useState } from 'react';
import { Route as RootRoute } from './__root';
import { useCase } from '@/hooks/useCase';
import { useDocumentIntelligence } from '@/hooks/useDocumentIntelligence';
import { useCases } from '@/hooks/useCases';
import { defaultRouteFor } from '@/lib/routeFor';
import { isValidCaseId } from '@/lib/caseId';
import { apiClient } from '@/lib/api';
import { useCurrentUser } from '@/stores/currentUser';
import { QueueRail } from '@/components/cockpit/QueueRail/QueueRail';
import { DocumentsPanel } from '@/components/cockpit/DocumentsPanel';
import { DocumentUploadZone } from '@/components/cockpit/DocumentUploadZone';
import { PanelStub } from '@/components/cockpit/PanelStub';
import { ReasoningTraceSlideOut } from '@/components/cockpit/ReasoningTraceSlideOut';
import type { components } from '@/api-types';

type ExtractedField = components['schemas']['ExtractedField'];

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
  const { data: caseEnv, isError: caseError } = useCase(caseId);
  const {
    data: intake,
    isPending: intakePending,
    isError: intakeError,
  } = useDocumentIntelligence(caseId);
  const { data: cases = [] } = useCases();
  const [openField, setOpenField] = useState<ExtractedField | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);

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

  return (
    <div className="flex h-full">
      <aside className="flex-shrink-0">
        <QueueRail
          cases={cases}
          activeCaseId={caseId}
          onSelect={(id) => navigate({ to: '/cases/$caseId', params: { caseId: id } })}
        />
      </aside>

      <main className="flex-1 overflow-y-auto p-6">
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

        <section className="mb-4 max-w-5xl space-y-2">
          <DocumentUploadZone caseId={caseId} onUploadComplete={handleUploadComplete} />
          <div className="flex items-center justify-end gap-3">
            {processError ? (
              <span role="alert" className="text-xs text-rose-600">
                {processError}
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => void handleProcess()}
              disabled={processing}
              className="text-xs px-3 py-1.5 rounded bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              {processing ? 'Processing…' : 'Process now'}
            </button>
          </div>
        </section>

        <div className="grid grid-cols-2 gap-4 max-w-5xl">
          <DocumentsPanel
            output={intake}
            isPending={intakePending}
            isError={intakeError}
            onProvenanceClick={(field) => setOpenField(field)}
          />
          <PanelStub title="Identity" epic="5" />
          <PanelStub title="UBO" epic="5" />
          <PanelStub title="Risk" epic="5" />
        </div>
      </main>

      <aside className="flex-shrink-0 w-[280px] border-l border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-zinc-900 mb-2">Agent copilot</h3>
        <p className="text-xs text-zinc-500">Live activity feed lands in Epic 4.</p>
      </aside>

      <ReasoningTraceSlideOut
        open={openField !== null}
        onOpenChange={(open) => {
          if (!open) setOpenField(null);
        }}
        extractedField={openField}
      />
    </div>
  );
}
