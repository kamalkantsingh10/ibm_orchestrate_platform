// TanStack Query hook for GET /v1/users/me (Story 1.4 AC #11).
// Established here as the canonical pattern; consumed by future stories.

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { User } from '@/lib/types/user';

export function useUsersMe() {
  return useQuery<User>({
    queryKey: ['users', 'me'],
    queryFn: () => apiFetch<User>('/v1/users/me'),
  });
}
