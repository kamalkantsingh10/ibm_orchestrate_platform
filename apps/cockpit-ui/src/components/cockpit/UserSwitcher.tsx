// User-switcher dropdown in the TopBar (Story 1.4 AC #2, #10, #13).
//
// Built on Radix DropdownMenu. Selecting a user updates the Zustand store
// and navigates to the new role's default route (no page reload).
// aria-live announcer surfaces the switch to screen readers.

import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown } from 'lucide-react';

import { defaultRouteFor } from '@/lib/routeFor';
import { DEMO_USERS, type Role, type User } from '@/lib/demoUsers';
import { useCurrentUser } from '@/stores/currentUser';

const ROLE_LABEL: Record<Role, string> = {
  analyst: 'Analyst',
  team_lead: 'Team Lead',
  regulator: 'Regulator',
};

// TODO(story-4-3): swap zinc/amber/violet for the marble + spring-flowers
// palette tokens when Tailwind @theme tokens land in Epic 4.
const ROLE_BADGE: Record<Role, string> = {
  analyst: 'bg-zinc-100 text-zinc-700 ring-1 ring-zinc-200',
  team_lead: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
  regulator: 'bg-violet-50 text-violet-800 ring-1 ring-violet-200',
};

export function UserSwitcher() {
  const { user: current, setUser } = useCurrentUser();
  const navigate = useNavigate();
  const [announcement, setAnnouncement] = useState('');

  const handleSelect = (next: User) => {
    if (next.id === current.id) return;
    setUser(next);
    setAnnouncement(`Switched to ${next.name}, ${ROLE_LABEL[next.role]}`);
    void navigate({ to: defaultRouteFor(next.role) });
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="flex items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500"
          aria-label={`Switch user. Current: ${current.name}, ${ROLE_LABEL[current.role]}`}
        >
          <span
            className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-200 text-xs font-medium text-zinc-700"
            aria-hidden="true"
          >
            {current.initials}
          </span>
          <span className="flex flex-col items-start leading-tight">
            <span className="font-medium">{current.name}</span>
            <span className={`mt-0.5 rounded px-1.5 text-[10px] ${ROLE_BADGE[current.role]}`}>
              {ROLE_LABEL[current.role]}
            </span>
          </span>
          <ChevronDown className="h-4 w-4 text-zinc-400" aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          sideOffset={6}
          className="z-50 min-w-[14rem] rounded-md border border-zinc-200 bg-white p-1 shadow-md"
        >
          {DEMO_USERS.map((u) => (
            <DropdownMenuItem
              key={u.id}
              onSelect={() => handleSelect(u)}
              className="flex cursor-pointer items-center justify-between gap-3 rounded px-2 py-1.5 text-sm outline-none focus:bg-zinc-100 data-[highlighted]:bg-zinc-100"
            >
              <span className="flex flex-col leading-tight">
                <span className="font-medium">{u.name}</span>
                <span className="text-xs text-zinc-500">{ROLE_LABEL[u.role]}</span>
              </span>
              {u.id === current.id && (
                <Check className="h-4 w-4 text-zinc-700" aria-label="Currently active" />
              )}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      {/* Visually-hidden live region — screen-reader announcement. */}
      <div role="status" aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </>
  );
}
