// Root layout — TopBar + Outlet + BottomRibbon placeholder (Story 1.4 AC #6).
// Story 4.2 mounts the keyboard live-region announcer here.
// Story 4.7 mounts the sonner Toaster + the mode badge.

import { Outlet, createRootRoute } from '@tanstack/react-router';
import { Toaster } from 'sonner';
import { UserSwitcher } from '@/components/cockpit/UserSwitcher';
import { KeyboardAnnouncer } from '@/components/cockpit/KeyboardAnnouncer';
import { CommandPalette } from '@/components/cockpit/CommandPalette';
import { useGlobalShortcuts } from '@/hooks/useGlobalShortcuts';
import { modeLabel, useMode } from '@/stores/modeStore';

function ModeBadge() {
  const mode = useMode((s) => s.mode);
  return (
    <span
      data-testid="mode-badge"
      className="inline-flex items-center rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[11px] font-medium text-zinc-700"
    >
      {modeLabel(mode)}
    </span>
  );
}

function RootLayout() {
  useGlobalShortcuts();
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-950">
      <header className="flex h-12 items-center justify-between border-b border-zinc-200 bg-white px-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-tight">Cockpit</span>
          <ModeBadge />
        </div>
        <UserSwitcher />
      </header>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      <footer
        data-testid="bottom-ribbon-placeholder"
        className="h-7 border-t border-zinc-200 bg-white"
        aria-hidden="true"
      />
      <KeyboardAnnouncer />
      <CommandPalette />
      <Toaster position="bottom-center" richColors closeButton={false} />
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout });
