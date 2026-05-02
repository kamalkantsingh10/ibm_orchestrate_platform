// DocumentsPanel — Story 3.6 AC #3.
//
// Renders Document Intelligence agent extractions grouped by document_ref.
// Every value row carries a ProvenanceIndicator (NFR-T4 100% coverage —
// asserted in DocumentsPanel.test.tsx).

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
}

export function DocumentsPanel({
  output,
  isPending,
  isError,
  onProvenanceClick,
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
    return (
      <div className="rounded-md border border-zinc-200 bg-white px-4 py-3.5">
        <Header subtitle="No intake data yet" />
        <hr className="my-3 border-zinc-200" />
        <p className="text-sm text-zinc-500">
          {output === null || output === undefined
            ? 'Intake has not yet run for this case. Run intake via POST /v1/cases/{id}/intake or wait for the supervisor.'
            : 'No fields were extracted from this case. Documents may not match a known taxonomy.'}
        </p>
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
            <h4 className="text-xs font-medium text-zinc-700 font-mono mb-2">{docRef}</h4>
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
  return (
    <div className="flex items-center gap-3">
      <div className="w-[140px] flex-shrink-0 text-xs text-zinc-600">
        {humanizeFieldName(field.field_name)}
      </div>
      <div className="flex-1 text-sm text-zinc-900 break-words min-w-0">
        {formatValue(field.value.value)}
      </div>
      <div className="flex-shrink-0">
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
