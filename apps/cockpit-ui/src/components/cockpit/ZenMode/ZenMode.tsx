// ZenMode — Stories 8.2 and 8.5.
//
// Visual half of Zen mode (Story 8.1 wired the keystroke + mode store +
// `expand` transition). Replaces the case canvas with a calm, focused
// writing surface: warm near-black background, centered editor at
// 720px max-width, and a 320px right-edge evidence dock.
//
// Composition note: ZenMode renders the editor through `children` so
// it can be unit-tested without DecisionZone's fetch graph. The
// `evidenceDock` slot follows the same pattern — Story 8.5 supplies
// `<EvidenceShelfDock caseId={...} />`; if no slot is supplied,
// ZenMode renders the Story 8.2 placeholder.

import type { ReactNode } from 'react';
import { useMode } from '@/stores/modeStore';

export interface ZenModeProps {
  caseId: string;
  caseName?: string | null;
  /** The Tiptap-driven editor surface. Story 7.1 DecisionZone in prod;
   *  a stub in unit tests. */
  children: ReactNode;
  /** Story 8.5 — the evidence dock slot. Defaults to the Story 8.2
   *  placeholder when omitted (kept for the 8.2 unit test path). */
  evidenceDock?: ReactNode;
  /** Optional override; defaults to switching the mode store back. */
  onExit?: () => void;
}

export function ZenMode({
  caseId,
  caseName,
  children,
  evidenceDock,
  onExit,
}: ZenModeProps): JSX.Element {
  const setMode = useMode((s) => s.setMode);

  const handleExit = () => {
    if (onExit) {
      onExit();
      return;
    }
    setMode('investigation');
  };

  return (
    <div
      data-testid="zen-mode-root"
      data-mode="zen"
      data-case-id={caseId}
      className="zen-canvas flex min-h-[100dvh] flex-col"
    >
      <header
        data-testid="zen-mode-header"
        className="flex items-center justify-between border-b border-[#2A2622] px-6 py-3 text-[#F1ECE3]"
      >
        <div className="flex items-center gap-3">
          {caseName ? (
            <span className="text-xs opacity-70" data-testid="zen-case-name">
              {caseName}
            </span>
          ) : null}
          <span
            data-testid="zen-mode-indicator"
            className="rounded-full border border-[#2A2622] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
          >
            Memo
          </span>
        </div>
        <button
          type="button"
          onClick={handleExit}
          data-testid="zen-back-to-investigation"
          className="rounded text-xs text-[#F1ECE3]/70 hover:text-[#F1ECE3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F1ECE3]/40"
        >
          Back to Investigation (⌘1)
        </button>
      </header>

      <div className="flex flex-1 min-h-0">
        <main className="flex-1 overflow-y-auto px-6 py-10">
          <div
            data-testid="zen-editor-frame"
            style={{ maxWidth: '720px', minHeight: '75vh' }}
            className="zen-editor-frame mx-auto w-full font-serif"
          >
            {children}
          </div>
        </main>

        {evidenceDock ? (
          <div data-testid="zen-evidence-dock" className="hidden md:flex">
            {evidenceDock}
          </div>
        ) : (
          <aside
            data-testid="zen-evidence-dock"
            className="hidden w-[320px] flex-col border-l border-[#2A2622] bg-[#1f1c19] px-4 py-6 text-[#F1ECE3] md:flex"
          >
            <h2 className="text-sm font-semibold tracking-tight">Evidence</h2>
            <p data-testid="zen-evidence-dock-placeholder" className="mt-1 text-xs opacity-60">
              Evidence shelf — ships in Story 8.5
            </p>
            <ul className="mt-4 space-y-2 text-xs opacity-70">
              <li className="rounded border border-[#2A2622] px-3 py-2">
                Placeholder document row
              </li>
            </ul>
          </aside>
        )}
      </div>
    </div>
  );
}
