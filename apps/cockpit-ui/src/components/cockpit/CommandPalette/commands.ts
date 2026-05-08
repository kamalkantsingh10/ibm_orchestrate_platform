// Command palette registry — Story 4.8 AC #4.
//
// Each command has a label, optional keywords, and a `run` callback that
// receives the live context (router, store setters, …). The registry is a
// finite, in-component constant array; new commands are added by editing
// this file.

import type { useNavigate } from '@tanstack/react-router';
import type { toast as toastFn } from 'sonner';
import type { Mode } from '@/stores/modeStore';
import type { Case } from '@/lib/types/case';

export type PaletteMode = 'commands' | 'cases';

export interface CommandContext {
  navigate: ReturnType<typeof useNavigate>;
  setMode: (mode: Mode) => void;
  setPaletteMode: (mode: PaletteMode) => void;
  closePalette: () => void;
  toast: typeof toastFn;
  signOut: () => void;
  cases: Case[];
}

export interface PaletteCommand {
  id: string;
  label: string;
  keywords?: string[];
  run: (ctx: CommandContext) => void;
}

export const COMMANDS: PaletteCommand[] = [
  {
    id: 'open-case',
    label: 'Open case…',
    keywords: ['case', 'open', 'navigate'],
    run: (ctx) => {
      ctx.setPaletteMode('cases');
    },
  },
  {
    id: 'switch-investigation',
    label: 'Switch to Investigation mode',
    keywords: ['mode', 'investigation', 'switch'],
    run: (ctx) => {
      ctx.setMode('investigation');
      ctx.closePalette();
    },
  },
  {
    id: 'go-queue',
    label: 'Go to queue',
    keywords: ['navigate', 'queue', 'home'],
    run: (ctx) => {
      void ctx.navigate({ to: '/queue' });
      ctx.closePalette();
    },
  },
  {
    id: 'sign-out',
    label: 'Sign out',
    keywords: ['logout', 'leave'],
    run: (ctx) => {
      ctx.signOut();
      ctx.closePalette();
    },
  },
  {
    id: 'show-shortcuts',
    label: 'Show keyboard shortcuts',
    keywords: ['help', 'keyboard', 'shortcuts', '?'],
    run: (ctx) => {
      ctx.toast('Keyboard help overlay deferred to post-demo', {
        description: 'See README for the cockpit shortcut list.',
        duration: 3000,
      });
      ctx.closePalette();
    },
  },
];

// ───────────── fuzzy match ─────────────

interface ScoredCommand {
  cmd: PaletteCommand;
  score: number;
}

export function scoreCommand(cmd: PaletteCommand, query: string): number {
  if (!query) return 1; // empty query keeps registration order
  const haystack = [cmd.label, ...(cmd.keywords ?? [])].join(' ').toLowerCase();
  const needle = query.toLowerCase();
  const idx = haystack.indexOf(needle);
  if (idx === -1) return 0;
  if (idx === 0) return 1;
  return 0.5;
}

export function filterCommands(
  commands: PaletteCommand[],
  query: string,
  cap = 10,
): PaletteCommand[] {
  const scored: ScoredCommand[] = commands
    .map((cmd) => ({ cmd, score: scoreCommand(cmd, query) }))
    .filter((s) => s.score > 0);
  if (!query) return scored.map((s) => s.cmd).slice(0, cap);
  scored.sort((a, b) => b.score - a.score || a.cmd.label.localeCompare(b.cmd.label));
  return scored.map((s) => s.cmd).slice(0, cap);
}

// ───────────── case match ─────────────

export function matchCases(cases: Case[], query: string, cap = 10): Case[] {
  if (!query) return cases.slice(0, cap);
  const needle = query.toLowerCase();
  return cases
    .filter(
      (c) =>
        c.id.toLowerCase().includes(needle) ||
        c.customer_metadata.customer_name.toLowerCase().includes(needle),
    )
    .slice(0, cap);
}
