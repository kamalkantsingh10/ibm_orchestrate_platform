// Root layout — TopBar + Outlet + BottomRibbon placeholder (Story 1.4 AC #6).

import { Outlet, createRootRoute } from '@tanstack/react-router';
import { UserSwitcher } from '@/components/cockpit/UserSwitcher';

function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-950">
      <header className="flex h-12 items-center justify-between border-b border-zinc-200 bg-white px-4">
        <span className="text-sm font-semibold tracking-tight">Cockpit</span>
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
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout });
