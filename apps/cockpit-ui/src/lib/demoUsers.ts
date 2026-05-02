// Demo user records consumed by the user-switcher (Story 1.4 + Story 2.2).
//
// Types come from the generated OpenAPI shadow at `@/api-types`. Runtime
// data lives here because the cockpit-ui pre-renders the switcher with all
// three options before any API call and `make seed` doesn't (yet) populate
// users on the server.

import type { components } from '@/api-types';

export type User = components['schemas']['User'];
export type Role = components['schemas']['Role'];

// Pinned UUIDs — mirror of contracts.users module constants.
// .env.example carries the same values for any consumer that wants overrides.
export const ANALYST_ID = 'dc2aaaa3-555b-4636-89d0-6047dc205220';
export const TEAM_LEAD_ID = 'a725a9bb-5b8e-4984-8d23-19c682225002';
export const REGULATOR_ID = 'a1582a20-62e1-497b-910c-45c0b0ee7030';

export const DEMO_USERS: readonly User[] = [
  { id: ANALYST_ID, name: 'Kamal Singh', role: 'analyst', initials: 'KS' },
  { id: TEAM_LEAD_ID, name: 'Rohan Mehta', role: 'team_lead', initials: 'RM' },
  { id: REGULATOR_ID, name: 'Anika Iyer', role: 'regulator', initials: 'AI' },
] as const;
