/**
 * Service module - Business Digital Twin CRUD.
 *
 * Endpoints
 * ---------
 *   GET    /api/v1/business            - fetch the *active* business profile
 *                                        (with completeness sidecar)
 *   POST   /api/v1/business            - create a new business; becomes active
 *   POST   /api/v1/business/minimal    - create with only the 6 required fields
 *   PUT    /api/v1/business            - partial update of the active business
 *   GET    /api/v1/business/list       - list every business the user owns
 *   DELETE /api/v1/business/{id}       - delete a specific business (404 if
 *                                        not owned, 409 if it is the user's
 *                                        last remaining business)
 *
 * Mirrors the backend routes in `backend/app/api/v1/endpoints/business.py`.
 * Wire shape is the Pydantic `BusinessWithCompleteness` envelope on read
 * and the `BusinessCreate` / `BusinessUpdate` payloads on write.
 */

import { apiClient } from "@/services/api-client";
import type {
  BusinessCreate,
  BusinessListResponse,
  BusinessMinimalCreate,
  BusinessUpdate,
  BusinessWithCompleteness,
  DeleteResponse,
} from "@/types/business";

export const businessService = {
  get: (): Promise<BusinessWithCompleteness> =>
    apiClient.get<BusinessWithCompleteness>("/api/v1/business"),

  create: (payload: BusinessCreate): Promise<BusinessWithCompleteness> =>
    apiClient.post<BusinessWithCompleteness>("/api/v1/business", payload),

  /**
   * Sprint 23 - inline 'Add a business' form inside the profile panel.
   * Accepts only the six required fields of the BasicSection.
   */
  createMinimal: (
    payload: BusinessMinimalCreate,
  ): Promise<BusinessWithCompleteness> =>
    apiClient.post<BusinessWithCompleteness>(
      "/api/v1/business/minimal",
      payload,
    ),

  update: (payload: BusinessUpdate): Promise<BusinessWithCompleteness> =>
    apiClient.put<BusinessWithCompleteness>("/api/v1/business", payload),

  /**
   * Sprint 23 - list every business the authenticated user owns.
   * The profile panel uses this to render the Switch / Delete list.
   */
  list: (): Promise<BusinessListResponse> =>
    apiClient.get<BusinessListResponse>("/api/v1/business/list"),

  /**
   * Sprint 23 - delete a specific business. The 409 (last business)
   * case is signalled via `ApiError.status === 409`; the panel
   * disables the Delete button when only one business remains,
   * so 409 should never reach production.
   */
  deleteById: (businessId: number): Promise<DeleteResponse> =>
    apiClient.delete<DeleteResponse>(`/api/v1/business/${businessId}`),
};
