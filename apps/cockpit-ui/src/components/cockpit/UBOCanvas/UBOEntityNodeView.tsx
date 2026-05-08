// Custom react-flow node renderer for UBO entity nodes — Story 5.4 / AC #3.

import { Building2 } from 'lucide-react';
import { Handle, Position } from 'reactflow';
import type { NodeProps } from 'reactflow';
import type { UBOEntityNode } from './adapter';

interface UBOEntityNodeViewProps extends NodeProps {
  data: UBOEntityNode;
}

export function UBOEntityNodeView({ data }: UBOEntityNodeViewProps) {
  const isRoot = data.cin !== null && data.cin !== undefined;
  const country = data.country ?? null;

  return (
    <div
      // Story 5.4 AC9 — nodes are explicitly tab-focusable for keyboard
      // navigation. role="button" is intentional even though the click target
      // is the broader canvas (Story 5.5 wires drag-correct).
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      role="group"
      aria-label={`Entity ${data.name}`}
      data-testid={`ubo-node-entity-${data.id}`}
      data-node-kind="entity"
      data-node-id={data.id}
      className="rounded-md border border-zinc-300 bg-white px-3 py-2 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 max-w-[180px]"
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <div className="flex items-start gap-2">
        <Building2 aria-hidden="true" className="h-4 w-4 flex-shrink-0 text-zinc-500" />
        <div className="min-w-0">
          <div className="text-xs font-medium text-zinc-900 truncate" title={data.name}>
            {data.name}
            {country && country !== 'IN' ? (
              <span className="ml-1 text-[10px] font-mono text-amber-700">[{country}]</span>
            ) : null}
          </div>
          {isRoot && data.cin ? (
            <div className="text-[10px] font-mono text-zinc-500 truncate">{data.cin}</div>
          ) : null}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
}
