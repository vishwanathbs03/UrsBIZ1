/**
 * Business Digital Twin data hooks.
 *
 * Mirrors the per-endpoint hook pattern established by
 * `features/dashboard/use-dashboard-data.ts`: a thin `useQuery` for the
 * read endpoint plus three `useMutation`s for create / update / delete.
 *
 * Every mutation invalidates the `["business", "profile"]` cache so the
 * next render of any analytics page (which subscribes to
 * `["business", ...]` query keys) re-fetches against the freshly
 * persisted Business row.
 *
 * The 404 from GET /api/v1/business is the canonical "no business yet"
 * signal — the same signal the dashboard / advisor / insights views
 * already key off. Consumers can read `useBusinessQuery().error` and
 * check `ApiError.status === 404` to switch into the wizard.
 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { businessService } from "@/services";
import { queryKeys } from "@/lib/query-keys";
import type {
  BusinessCreate,
  BusinessUpdate,
  BusinessWithCompleteness,
} from "@/types/business";

// --------------------------------------------------------------------------- //
// Read
// --------------------------------------------------------------------------- //

export function useBusinessQuery() {
  return useQuery<BusinessWithCompleteness>({
    queryKey: queryKeys.business(),
    queryFn: () => businessService.get(),
  });
}

// --------------------------------------------------------------------------- //
// Mutations
// --------------------------------------------------------------------------- //

export function useCreateBusiness() {
  const queryClient = useQueryClient();
  return useMutation<BusinessWithCompleteness, Error, BusinessCreate>({
    mutationFn: (payload) => businessService.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["business"] });
    },
  });
}

export function useUpdateBusiness() {
  const queryClient = useQueryClient();
  return useMutation<BusinessWithCompleteness, Error, BusinessUpdate>({
    mutationFn: (payload) => businessService.update(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["business"] });
    },
  });
}

// Sprint 23 — the legacy "delete the active business, no args" hook
// was removed. The single source of truth for business deletion is now
// ``useDeleteBusinessById`` (see features/profile/use-businesses.ts),
// which takes the explicit business id and calls the new
// DELETE /api/v1/business/{business_id} route. The previous
// ``businessService.delete()`` (no-arg, active-only) endpoint was
// retired alongside it.
