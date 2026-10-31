"use client";

/**
 * Profile panel hooks (Sprint 23).
 *
 * Four hooks, all backed by TanStack Query:
 *
 *   - ``useBusinessesQuery`` — every business the user owns +
 *     the current active id. Primary data source for the panel.
 *   - ``useSetActiveBusiness`` — mutation that flips the active
 *     id via PATCH /auth/me, refreshes the AuthContext, and
 *     invalidates every per-business query so the dashboard,
 *     analytics, advisor, and assistant all re-fetch.
 *   - ``useCreateBusinessMinimal`` — mutation for the inline
 *     'Add a business' form. Same invalidation discipline.
 *   - ``useDeleteBusinessById`` — mutation for the per-row 'Delete'
 *     button. Same invalidation discipline. Named with a ``ById``
 *     suffix to keep it distinct from the active-business delete
 *     hook that used to live in ``features/business/use-business-data.ts``
 *     (that hook was removed when the no-arg endpoint was retired).
 *
 * Cache invalidation pattern
 * --------------------------
 * Every mutation invalidates the ``["business"]`` namespace so the
 * panel's ``useBusinessesQuery`` and every per-business dashboard
 * query (``["business", "profile"]``, ``["business", "dashboard"]``,
 * ``["business", "analytics"]``, etc.) re-fetches after the user
 * switches / adds / deletes.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";

import { authService } from "@/services/auth-service";
import { businessService } from "@/services";
import { queryKeys } from "@/lib/query-keys";
import { useAuth } from "@/hooks/use-auth";
import type {
  BusinessListResponse,
  BusinessMinimalCreate,
  BusinessWithCompleteness,
} from "@/types/business";
import type { User } from "@/types/auth";

// --------------------------------------------------------------------------- //
// Read
// --------------------------------------------------------------------------- //

export function useBusinessesQuery() {
  return useQuery<BusinessListResponse>({
    queryKey: queryKeys.businesses(),
    queryFn: () => businessService.list(),
  });
}

// --------------------------------------------------------------------------- //
// Mutations
// --------------------------------------------------------------------------- //

/**
 * Switch the active business. The hook:
 *
 *   1. Calls ``authService.updateMe`` which returns the updated User.
 *   2. Calls ``setUser`` so the AuthContext reflects the new active id
 *      without a full page reload.
 *   3. Invalidates the ``["business"]`` namespace so the panel's
 *      ``useBusinessesQuery`` and every per-business dashboard query
 *      re-fetch under the new active id.
 */
export function useSetActiveBusiness(): UseMutationResult<
  User,
  Error,
  number
> {
  const queryClient = useQueryClient();
  const { setUser } = useAuth();
  return useMutation<User, Error, number>({
    mutationFn: (businessId) =>
      authService.updateMe({ active_business_id: businessId }),
    onSuccess: (updatedUser) => {
      setUser(updatedUser);
      void queryClient.invalidateQueries({ queryKey: ["business"] });
    },
  });
}

/**
 * Add a business via the inline panel form. After the row is
 * created (and promoted to active by the backend), the same
 * invalidation discipline as ``useSetActiveBusiness`` runs.
 */
export function useCreateBusinessMinimal(): UseMutationResult<
  BusinessWithCompleteness,
  Error,
  BusinessMinimalCreate
> {
  const queryClient = useQueryClient();
  const { refresh } = useAuth();
  return useMutation<BusinessWithCompleteness, Error, BusinessMinimalCreate>({
    mutationFn: (payload) => businessService.createMinimal(payload),
    onSuccess: async () => {
      // The backend promoted the new business to active; pull the
      // updated User so the navbar / context reflect the change.
      await refresh();
      void queryClient.invalidateQueries({ queryKey: ["business"] });
    },
  });
}

/**
 * Delete a business. Same invalidation discipline; no need to
 * refresh the AuthContext because the backend re-points
 * ``active_business_id`` automatically when the deleted row was
 * active, but a stale ``user.active_business_id`` in the AuthContext
 * would still cause flicker until the next page load. Calling
 * ``refresh()`` is the cheapest fix.
 */
export function useDeleteBusinessById(): UseMutationResult<
  { detail: string; id: number },
  Error,
  number
> {
  const queryClient = useQueryClient();
  const { refresh } = useAuth();
  return useMutation<{ detail: string; id: number }, Error, number>({
    mutationFn: (businessId) => businessService.deleteById(businessId),
    onSuccess: async () => {
      await refresh();
      void queryClient.invalidateQueries({ queryKey: ["business"] });
    },
  });
}
