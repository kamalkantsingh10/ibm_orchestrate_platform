// TanStack Query hook for GET /v1/users/me (Story 1.4 → Story 2.2 typed).
// Now uses the openapi-fetch client; query key + return type unchanged.

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { User } from '@/lib/demoUsers';

export function useUsersMe() {
  return useQuery<User>({
    queryKey: ['users', 'me'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/users/me');
      if (error || !data) {
        throw new Error(`GET /v1/users/me failed: ${JSON.stringify(error)}`);
      }
      return data;
    },
  });
}
