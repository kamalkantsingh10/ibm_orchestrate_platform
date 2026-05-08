// CommandPalette — Story 4.8.
//
// Centered modal opened by ⌘K. Two-state input: command list ↔ case
// search. Five-item command registry; arrow-key navigation; Enter runs the
// highlighted item; Esc closes (Radix Dialog handles natively).

import * as Dialog from '@radix-ui/react-dialog';
import { useMemo, useRef, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import { useCases } from '@/hooks/useCases';
import { useMode } from '@/stores/modeStore';
import { usePalette } from '@/stores/paletteStore';
import {
  COMMANDS,
  filterCommands,
  matchCases,
  type PaletteCommand,
  type PaletteMode,
} from './commands';

export function CommandPalette(): JSX.Element {
  const open = usePalette((s) => s.open);
  const setOpen = usePalette((s) => s.setOpen);
  const setMode = useMode((s) => s.setMode);
  const navigate = useNavigate();
  const { data: cases = [] } = useCases();

  const [paletteMode, setPaletteMode] = useState<PaletteMode>('commands');
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Resets per-open. Radix's `onOpenAutoFocus` fires once when the dialog
  // first becomes visible — the right place to clear state without
  // tripping eslint's "cascading renders in effect" lint.
  const resetForOpen = () => {
    setPaletteMode('commands');
    setQuery('');
    setHighlight(0);
  };

  // Highlight resets are folded into the change handlers (see below) so
  // there's no useEffect→setState cascade.

  const matchedCommands = useMemo(() => filterCommands(COMMANDS, query), [query]);
  const matchedCases = useMemo(() => matchCases(cases, query), [cases, query]);

  const items = paletteMode === 'cases' ? matchedCases : matchedCommands;
  const itemCount = items.length;

  const closePalette = () => setOpen(false);

  const signOut = () => {
    // Story 1.4 / 1.6 — user-switcher is local-state only. Reload returns
    // the analyst to the seeded default (or whatever is persisted).
    try {
      window.localStorage.removeItem('cockpit-current-user');
    } catch {
      /* ignore */
    }
    // We still need a definite "logged out" landing — reload back to root.
    window.location.assign('/');
  };

  const runCommandByIndex = (idx: number) => {
    if (paletteMode === 'commands') {
      const cmd = matchedCommands[idx];
      if (!cmd) return;
      cmd.run({
        navigate,
        setMode,
        setPaletteMode,
        closePalette,
        toast,
        signOut,
        cases,
      });
      // Reset query when the command remains-open path is taken (open-case).
      if (cmd.id === 'open-case') setQuery('');
    } else {
      const c = matchedCases[idx];
      if (!c) return;
      void navigate({ to: '/cases/$caseId', params: { caseId: c.id } });
      closePalette();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(itemCount - 1, h + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      runCommandByIndex(highlight);
    } else if (e.key === 'Backspace' && query === '' && paletteMode === 'cases') {
      e.preventDefault();
      setPaletteMode('commands');
    }
  };

  const placeholder = paletteMode === 'cases' ? 'Type case name or ID…' : 'Type a command…';

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30" />
        <Dialog.Content
          className="fixed left-1/2 top-[20%] -translate-x-1/2 w-[min(92vw,560px)] rounded-lg bg-white shadow-2xl border border-zinc-200 overflow-hidden"
          onOpenAutoFocus={(e) => {
            // Defer focus to our input so autoFocus survives Radix's reset,
            // and reset transient palette state on every open.
            e.preventDefault();
            resetForOpen();
            inputRef.current?.focus();
          }}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-controls="palette-results"
            placeholder={placeholder}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setHighlight(0);
            }}
            onKeyDown={onKeyDown}
            className="w-full px-4 py-3 text-sm border-b border-zinc-100 focus:outline-none"
          />
          <ul
            id="palette-results"
            role="listbox"
            aria-live="polite"
            className="flex flex-col py-1 max-h-72 overflow-y-auto"
          >
            {items.length === 0 ? (
              <li className="px-4 py-2 text-xs text-zinc-500">No matches</li>
            ) : null}
            {paletteMode === 'commands'
              ? matchedCommands.map((cmd: PaletteCommand, i) => (
                  <PaletteRow
                    key={cmd.id}
                    selected={i === highlight}
                    onSelect={() => runCommandByIndex(i)}
                    onHover={() => setHighlight(i)}
                    primary={cmd.label}
                    secondary={cmd.id}
                  />
                ))
              : matchedCases.map((c, i) => (
                  <PaletteRow
                    key={c.id}
                    selected={i === highlight}
                    onSelect={() => runCommandByIndex(i)}
                    onHover={() => setHighlight(i)}
                    primary={c.customer_metadata.customer_name}
                    secondary={c.id}
                  />
                ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

interface PaletteRowProps {
  selected: boolean;
  onSelect: () => void;
  onHover: () => void;
  primary: string;
  secondary: string;
}

function PaletteRow({
  selected,
  onSelect,
  onHover,
  primary,
  secondary,
}: PaletteRowProps): JSX.Element {
  return (
    <li
      role="option"
      aria-selected={selected}
      onMouseEnter={onHover}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`flex items-center justify-between px-4 py-1.5 text-sm cursor-pointer ${
        selected ? 'bg-zinc-100' : ''
      }`}
    >
      <span>{primary}</span>
      <span className="text-[10px] text-zinc-400 font-mono">{secondary}</span>
    </li>
  );
}
