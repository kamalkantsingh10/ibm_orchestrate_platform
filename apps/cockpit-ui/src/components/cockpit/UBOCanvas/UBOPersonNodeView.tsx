// Custom react-flow node renderer for UBO person nodes — Story 5.4 / AC #3.

import { User } from 'lucide-react';
import { Handle, Position } from 'reactflow';
import type { NodeProps } from 'reactflow';
import type { UBOPersonNode } from './adapter';

interface UBOPersonNodeViewProps extends NodeProps {
  data: UBOPersonNode;
}

export function UBOPersonNodeView({ data }: UBOPersonNodeViewProps) {
  return (
    <div
      // Story 5.4 AC9 — nodes are explicitly tab-focusable for keyboard
      // navigation; the screen-reader-friendly companion is UBOEdgeList.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      role="group"
      aria-label={`Person ${data.name}`}
      data-testid={`ubo-node-person-${data.id}`}
      data-node-kind="person"
      data-node-id={data.id}
      className="flex flex-col items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 rounded-full"
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-zinc-400 bg-white shadow-sm">
        <User aria-hidden="true" className="h-5 w-5 text-zinc-600" />
      </div>
      <div
        className="mt-1 max-w-[120px] text-center text-xs text-zinc-900 truncate"
        title={data.name}
      >
        {data.name}
      </div>
      {data.din ? <div className="text-[10px] font-mono text-zinc-500">DIN {data.din}</div> : null}
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
}
