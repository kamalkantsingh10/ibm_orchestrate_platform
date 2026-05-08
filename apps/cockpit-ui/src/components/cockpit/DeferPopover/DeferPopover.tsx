// DeferPopover — Story 4.2 AC #5.
//
// Anchored popover with three quick deferrals. Pure presentational +
// store-writing; the keyboard hook owns open/close. Backed by Radix Popover
// (already a project dep). No backend roundtrip.

import * as Popover from '@radix-ui/react-popover';
import { useDeferredFilter } from '@/stores/deferredFilterStore';
import { useAnnouncer } from '@/stores/announcerStore';

export interface DeferPopoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseId: string | null;
  caseName: string | null;
  /** Anchor element the popover positions against. */
  anchor: HTMLElement | null;
}

interface DeferOption {
  id: 'one_hour' | 'tomorrow_9am' | 'seven_days';
  label: string;
  resolve: (now: Date) => Date;
}

const _OPTIONS: DeferOption[] = [
  {
    id: 'one_hour',
    label: 'Defer 1 hour',
    resolve: (now) => new Date(now.getTime() + 60 * 60 * 1000),
  },
  {
    id: 'tomorrow_9am',
    label: 'Defer until tomorrow 9 am',
    resolve: (now) => {
      const d = new Date(now);
      d.setDate(d.getDate() + 1);
      d.setHours(9, 0, 0, 0);
      return d;
    },
  },
  {
    id: 'seven_days',
    label: 'Defer 7 days',
    resolve: (now) => new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000),
  },
];

export function DeferPopover({
  open,
  onOpenChange,
  caseId,
  caseName,
  anchor,
}: DeferPopoverProps): JSX.Element {
  const defer = useDeferredFilter((s) => s.defer);
  const announce = useAnnouncer((s) => s.announce);

  const handleSelect = (option: DeferOption) => {
    if (!caseId) return;
    const until = option.resolve(new Date());
    defer(caseId, until);
    announce(`Deferred ${caseName ?? caseId} (${option.label.toLowerCase()})`);
    onOpenChange(false);
  };

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Anchor virtualRef={anchor ? { current: anchor } : undefined} />
      <Popover.Portal>
        <Popover.Content
          side="right"
          align="start"
          sideOffset={6}
          aria-label="Defer case"
          className="z-50 w-[220px] rounded border border-zinc-200 bg-white shadow-lg p-2"
        >
          <h3 className="text-xs font-semibold text-zinc-600 px-2 py-1">
            Defer {caseName ?? caseId ?? 'case'}
          </h3>
          <ul className="flex flex-col" role="radiogroup" aria-label="Defer options">
            {_OPTIONS.map((opt) => (
              <li key={opt.id}>
                <button
                  type="button"
                  role="radio"
                  aria-checked="false"
                  onClick={() => handleSelect(opt)}
                  className="w-full text-left text-sm px-2 py-1.5 rounded hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  {opt.label}
                </button>
              </li>
            ))}
          </ul>
          <div className="border-t border-zinc-100 mt-1 pt-1">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="w-full text-left text-xs text-zinc-500 px-2 py-1.5 rounded hover:bg-zinc-100"
            >
              Cancel
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
