// Per-component decomposition rows for RiskPanel — Story 5.9 / AC #2.

import type { components } from '@/api-types';

export type RiskComponent = components['schemas']['RiskComponent'];

const LABEL: Record<RiskComponent['name'], string> = {
  country: 'Country',
  entity_type: 'Entity Type',
  ownership_clarity: 'Ownership Clarity',
  screening: 'Screening',
  adverse_media: 'Adverse Media',
};

export interface RiskDecompositionListProps {
  components: RiskComponent[];
}

export function RiskDecompositionList({ components }: RiskDecompositionListProps) {
  return (
    <ul aria-label="Risk decomposition" className="mt-3 space-y-2">
      {components.map((c) => (
        <li
          key={c.name}
          data-testid={`risk-decomposition-${c.name}`}
          className="rounded border border-zinc-100 bg-zinc-50 px-3 py-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-900">{LABEL[c.name]}</span>
            <span className="text-xs tabular-nums text-zinc-700">
              {c.contribution.toFixed(1)} ({c.value} × {c.weight})
            </span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-600">{c.rationale}</p>
        </li>
      ))}
    </ul>
  );
}
