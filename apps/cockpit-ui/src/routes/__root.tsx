// Root layout — TopBar + Outlet + BottomRibbon placeholder (Story 1.4 AC #6).
// Story 4.2 mounts the keyboard live-region announcer here.
// Story 4.7 mounts the sonner Toaster + the mode badge.
// Story 8.2 hangs `data-mode` on the shell, swaps the badge for a
// minimal `Memo` indicator + back-button in Zen, and hides the bottom
// ribbon while writing.

import { Outlet, createRootRoute } from '@tanstack/react-router';
import { Toaster } from 'sonner';
import { UserSwitcher } from '@/components/cockpit/UserSwitcher';
import { KeyboardAnnouncer } from '@/components/cockpit/KeyboardAnnouncer';
import { CommandPalette } from '@/components/cockpit/CommandPalette';
import { useGlobalShortcuts } from '@/hooks/useGlobalShortcuts';
import { modeLabel, useMode } from '@/stores/modeStore';

function ModeBadge() {
  const mode = useMode((s) => s.mode);
  const setMode = useMode((s) => s.setMode);

  // Story 8.2 AC #4 — Zen reduces the chrome to a `Memo` indicator
  // plus an explicit one-tap exit. Other modes keep the full label.
  if (mode === 'zen') {
    return (
      <span data-testid="mode-badge" className="inline-flex items-center gap-2">
        <span
          data-testid="zen-memo-indicator"
          className="inline-flex items-center rounded-full border border-[#2A2622] bg-[#1f1c19] px-2 py-0.5 text-[10.5px] font-medium uppercase tracking-[0.06em] text-[#F1ECE3]"
        >
          Memo
        </span>
        <button
          type="button"
          data-testid="zen-back-to-investigation-chrome"
          onClick={() => setMode('investigation')}
          className="rounded text-[11px] text-[#F1ECE3]/70 hover:text-[#F1ECE3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F1ECE3]/40"
        >
          Back to Investigation (⌘1)
        </button>
      </span>
    );
  }

  return (
    <span
      data-testid="mode-badge"
      className="inline-flex items-center rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-[10.5px] font-medium uppercase tracking-[0.06em] text-zinc-600"
    >
      {modeLabel(mode)}
    </span>
  );
}

function RootLayout() {
  useGlobalShortcuts();
  const mode = useMode((s) => s.mode);
  const isZen = mode === 'zen';

  return (
    <div
      data-mode={mode}
      className={
        isZen
          ? 'flex min-h-screen flex-col bg-[#1A1815] text-[#F1ECE3]'
          : 'flex min-h-screen flex-col bg-zinc-50 text-zinc-900'
      }
    >
      <header
        className={
          isZen
            ? 'flex h-12 items-center justify-between border-b border-[#2A2622] bg-[#1A1815] px-5'
            : 'flex h-12 items-center justify-between border-b border-zinc-200 bg-white px-5'
        }
      >
        <div className="flex items-center gap-3">
          <span
            className={
              isZen
                ? 'text-[13px] font-semibold uppercase tracking-[0.14em] text-[#F1ECE3]'
                : 'text-[13px] font-semibold uppercase tracking-[0.14em] text-zinc-900'
            }
          >
            Cockpit
          </span>
          <ModeBadge />
        </div>
        <span data-zen-chrome>
          <UserSwitcher />
        </span>
      </header>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      {isZen ? null : (
        <footer
          data-testid="bottom-ribbon-placeholder"
          className="h-7 border-t border-zinc-200 bg-white"
          aria-hidden="true"
        />
      )}
      <KeyboardAnnouncer />
      <CommandPalette />
      <Toaster position="bottom-center" richColors closeButton={false} />
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout });
