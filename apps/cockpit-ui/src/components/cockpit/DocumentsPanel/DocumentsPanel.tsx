// DocumentsPanel — Story 3.6 AC #3.
//
// Renders Document Intelligence agent extractions grouped by document_ref.
// Every value row carries a ProvenanceIndicator (NFR-T4 100% coverage —
// asserted in DocumentsPanel.test.tsx). Story 4 hardening: each document
// header is a link to GET /v1/cases/{case_id}/documents/{filename}/download
// so the analyst can preview the source PDF the agents have been reading.

import { Download } from 'lucide-react';
import type { components } from '@/api-types';
import { humanizeFieldName } from '@/lib/humanize';
import { ProvenanceIndicator } from '@/components/cockpit/ProvenanceIndicator';

type DocumentIntelligenceOutput = components['schemas']['DocumentIntelligenceOutput'];
type ExtractedField = components['schemas']['ExtractedField'];

export interface DocumentsPanelProps {
  output: DocumentIntelligenceOutput | null | undefined;
  isPending?: boolean;
  isError?: boolean;
  onProvenanceClick?: (extractedField: ExtractedField) => void;
  /** Story 4 hardening — case id used to build the download URL per doc. */
  caseId?: string;
  /**
   * Story 4 hardening — case-scoped document filenames already on disk
   * (from ``customer_metadata.extra.document_refs``). Rendered in the
   * empty state so the analyst can preview PDFs before clicking
   * "Process now".
   */
  pendingDocumentRefs?: readonly string[];
}

export function DocumentsPanel({
  output,
  isPending,
  isError,
  onProvenanceClick,
  caseId,
  pendingDocumentRefs,
}: DocumentsPanelProps): JSX.Element {
  // Loading state — only when there's no data yet.
  if (isPending && !output) {
    return (
      <div
        className="rounded-md border border-zinc-200 bg-white px-4 py-3.5"
        data-testid="documents-panel-skeleton"
      >
        <Header subtitle="" />
        <hr className="my-3 border-zinc-200" />
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-7 rounded bg-zinc-100 animate-pulse motion-reduce:animate-none"
            />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
      >
        Could not load intake data.
      </div>
    );
  }

  // Empty state — `null` (intake not run) or empty fields list.
  if (!output || output.extracted_fields.length === 0) {
    const hasPending = (pendingDocumentRefs?.length ?? 0) > 0;
    return (
      <div className="rounded-md border border-zinc-200 bg-white px-4 py-3.5">
        <Header
          subtitle={
            hasPending
              ? `${pendingDocumentRefs!.length} on file — not processed yet`
              : 'No intake data yet'
          }
        />
        <hr className="my-3 border-zinc-200" />
        {hasPending ? (
          <div className="space-y-2">
            <p className="text-sm text-zinc-500">
              Documents are on file but Document Intelligence hasn&apos;t run yet. Click{' '}
              <strong>Process now</strong> to extract fields, or click a filename to preview the
              PDF.
            </p>
            <ul className="space-y-1.5">
              {pendingDocumentRefs!.map((docRef) => (
                <li key={docRef}>
                  <DocumentHeader docRef={docRef} caseId={caseId} />
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">
            {output === null || output === undefined
              ? 'Intake has not yet run for this case. Run intake via POST /v1/cases/{id}/intake or wait for the supervisor.'
              : 'No fields were extracted from this case. Documents may not match a known taxonomy.'}
          </p>
        )}
      </div>
    );
  }

  // Group fields by document_ref preserving first-occurrence order.
  const grouped = new Map<string, ExtractedField[]>();
  for (const field of output.extracted_fields) {
    const list = grouped.get(field.document_ref) ?? [];
    list.push(field);
    grouped.set(field.document_ref, list);
  }
  const totalFields = output.extracted_fields.length;

  return (
    <div className="rounded-md border border-zinc-200 bg-white px-4 py-3.5">
      <Header subtitle={`${totalFields} field${totalFields === 1 ? '' : 's'} extracted`} />
      <hr className="my-3 border-zinc-200" />
      <div className="space-y-5">
        {Array.from(grouped.entries()).map(([docRef, fields]) => (
          <section key={docRef}>
            <DocumentHeader docRef={docRef} caseId={caseId} />
            <div className="space-y-1.5">
              {fields.map((field) => (
                <DocumentField
                  key={`${field.document_ref}:${field.field_name}`}
                  field={field}
                  onProvenanceClick={onProvenanceClick}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function DocumentHeader({ docRef, caseId }: { docRef: string; caseId?: string }): JSX.Element {
  if (!caseId) {
    // Backward-compat: no caseId means we render the filename plain (used
    // by the panel's older test fixtures and any future read-only views).
    return <h4 className="text-xs font-medium text-zinc-700 font-mono mb-2">{docRef}</h4>;
  }
  const href = `/v1/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docRef)}/download`;
  return (
    <h4 className="text-xs font-medium text-zinc-700 font-mono mb-2">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 hover:text-zinc-900 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
        title={`Open ${docRef} in a new tab`}
      >
        {docRef}
        <Download className="h-3 w-3 text-zinc-400" aria-hidden="true" />
      </a>
    </h4>
  );
}

function Header({ subtitle }: { subtitle: string }): JSX.Element {
  return (
    <div className="flex items-baseline justify-between">
      <h3 className="text-sm font-semibold text-zinc-900">Documents</h3>
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span>{subtitle}</span>
        {subtitle ? (
          <span className="px-1.5 py-0.5 rounded bg-zinc-100 font-medium">
            Document Intelligence
          </span>
        ) : null}
      </div>
    </div>
  );
}

function DocumentField({
  field,
  onProvenanceClick,
}: {
  field: ExtractedField;
  onProvenanceClick?: (f: ExtractedField) => void;
}): JSX.Element {
  // Story 4 hardening — explicit grid columns (label / value / provenance)
  // so the value cell can't collapse to ~1ch under flex-shrink + min-w-0
  // when the panel sits inside a narrower grid cell. `1fr` always wins
  // over `flex-1` for the long-string, narrow-container case.
  return (
    <div className="grid grid-cols-[140px_1fr_auto] items-start gap-x-3 gap-y-1">
      <div className="text-xs text-zinc-600 pt-0.5">{humanizeFieldName(field.field_name)}</div>
      <div className="text-sm text-zinc-900 break-words">{formatValue(field.value.value)}</div>
      <div>
        <ProvenanceIndicator
          provenance={field.value.provenance}
          onClick={onProvenanceClick ? () => onProvenanceClick(field) : undefined}
        />
      </div>
    </div>
  );
}

function formatValue(value: string | number | boolean | null): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-zinc-400">—</span>;
  }
  if (typeof value === 'number') {
    return new Intl.NumberFormat('en-IN').format(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  // Best-effort date detection for ISO 8601 prefixes.
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) {
      return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(d);
    }
  }
  return String(value);
}
