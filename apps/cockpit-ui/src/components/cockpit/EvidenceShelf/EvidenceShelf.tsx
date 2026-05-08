// EvidenceShelf — Story 7.8 / AC #1.
//
// Read-only right-side drawer that lists the case's documents +
// top-3 extracted fields per document by confidence. Reuses Story
// 3.4's `useDocumentIntelligence` hook (no new fetch). Toggled by
// the Decision Zone's Evidence button.
//
// No upload, no edit, no SHA-256 (Epic 8 / Story 8.5 surfaces those).

import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useDocumentIntelligence } from '@/hooks/useDocumentIntelligence';
import { ConfidencePill } from '@/components/cockpit/ConfidencePill';
import { groupByDocument, topByConfidence } from './groupFields';

export interface EvidenceShelfProps {
  caseId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const _DOCS_TO_SHOW_PER_FIELD = 3;

export function EvidenceShelf({ caseId, open, onOpenChange }: EvidenceShelfProps) {
  const { data: docIntel, isPending } = useDocumentIntelligence(caseId);

  const fields = docIntel?.extracted_fields ?? [];
  const grouped = groupByDocument(fields);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          data-testid="evidence-shelf-overlay"
          className="fixed inset-0 z-40 bg-black/20 motion-reduce:transition-none"
        />
        <Dialog.Content
          data-testid="evidence-shelf"
          className="fixed inset-y-0 right-0 z-50 flex h-full w-[320px] flex-col bg-white shadow-2xl ring-1 ring-zinc-200 motion-reduce:transition-none"
          aria-label="Evidence shelf"
        >
          <header className="flex items-center justify-between px-4 py-3 border-b border-zinc-200">
            <Dialog.Title className="text-base font-semibold text-zinc-900">Evidence</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close evidence shelf"
                className="rounded p-1 text-zinc-500 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
            {isPending ? (
              <div data-testid="evidence-shelf-skeleton" className="space-y-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="animate-pulse rounded bg-zinc-100 px-3 py-3">
                    <div className="h-3 w-1/2 rounded bg-zinc-200" />
                    <div className="mt-2 h-2 w-3/4 rounded bg-zinc-200" />
                  </div>
                ))}
              </div>
            ) : grouped.size === 0 ? (
              <p className="text-sm text-zinc-500">No documents on this case.</p>
            ) : (
              [...grouped.entries()].map(([documentRef, docFields]) => (
                <section
                  key={documentRef}
                  data-testid="evidence-shelf-doc-section"
                  className="rounded border border-zinc-200 bg-zinc-50 px-3 py-3"
                >
                  <div className="text-sm font-medium text-zinc-900">{documentRef}</div>
                  <div className="text-xs text-zinc-500">
                    {docFields.length} field{docFields.length === 1 ? '' : 's'} extracted
                  </div>
                  <dl className="mt-2 space-y-1.5">
                    {topByConfidence(docFields, _DOCS_TO_SHOW_PER_FIELD).map((field, idx) => (
                      <div
                        key={`${documentRef}-${field.field_name}-${idx}`}
                        className="flex items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <dt className="text-[10px] uppercase tracking-wide text-zinc-500">
                            {field.field_name}
                          </dt>
                          <dd className="truncate font-mono text-xs text-zinc-900">
                            {String(field.value.value ?? '—')}
                          </dd>
                        </div>
                        <ConfidencePill
                          confidence={field.value.provenance.confidence}
                          variant="inline-small"
                        />
                      </div>
                    ))}
                  </dl>
                </section>
              ))
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
