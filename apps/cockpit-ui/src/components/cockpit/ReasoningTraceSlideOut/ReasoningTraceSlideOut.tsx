// ReasoningTraceSlideOut — Story 3.6 AC #5.
//
// Placeholder shell. Built on Radix Dialog with right-edge positioning.
// The full 4-section content + counterfactuals lands in Story 6-7.

import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { components } from '@/api-types';
import { ConfidencePill } from '@/components/cockpit/ConfidencePill';

type ExtractedField = components['schemas']['ExtractedField'];

export interface ReasoningTraceSlideOutProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  extractedField?: ExtractedField | null;
}

export function ReasoningTraceSlideOut({
  open,
  onOpenChange,
  extractedField,
}: ReasoningTraceSlideOutProps): JSX.Element {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/20 motion-reduce:transition-none" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed right-0 top-0 bottom-0 w-[480px] bg-white shadow-2xl border-l border-zinc-200 flex flex-col motion-reduce:animate-none"
        >
          <header className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
            <Dialog.Title className="text-sm font-semibold text-zinc-900">
              Reasoning trace
            </Dialog.Title>
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-500">Esc to close</span>
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="p-1 rounded hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
                  aria-label="Close reasoning trace"
                >
                  <X className="w-4 h-4 text-zinc-600" />
                </button>
              </Dialog.Close>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {extractedField ? (
              <>
                <Section title="What was searched">
                  <p className="text-sm text-zinc-700">
                    Document: <code className="font-mono">{extractedField.document_ref}</code>;
                    field: <code className="font-mono">{extractedField.field_name}</code>
                  </p>
                </Section>
                <Section title="What returned">
                  <p className="text-sm text-zinc-900 break-words">
                    {extractedField.value.value === null ? (
                      <span className="text-zinc-400">—</span>
                    ) : (
                      String(extractedField.value.value)
                    )}
                  </p>
                </Section>
                <Section title="Confidence">
                  <ConfidencePill
                    confidence={extractedField.value.provenance.confidence}
                    variant="panel-header"
                  />
                </Section>
                <Section title="What would change">
                  <p className="text-sm text-zinc-600">
                    Full reasoning trace + counterfactual lands in Epic 6 (Story 6.7).
                  </p>
                </Section>
              </>
            ) : (
              <p className="text-sm text-zinc-500">Click a provenance pill to inspect.</p>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 mb-1.5">
        {title}
      </h3>
      {children}
    </section>
  );
}
