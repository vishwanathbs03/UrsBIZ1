import { apiClient } from "./api-client";

/**
 * Scheme display model (Sprint H6.3).
 *
 * The `eligibility_status` field no longer implies official eligibility:
 *   - "matching"     = business profile is within the official scheme band
 *   - "partialMatch" = one of industry or turnover matches
 *   - "outsideBand"  = neither matches
 *
 * `official_authority`, `official_source_url`, `last_verified`,
 * `verified_status`, `match_basis`, and `notes` are surfaced in the
 * scheme card detail view so the user can see the source we used.
 */

export interface SchemeItem {
  id: string;
  name: string;
  description: string;
  category: string;
  eligibility_status: "matching" | "partialMatch" | "outsideBand";
  eligibility_reason: string;
  matching_score: number;
  priority: "High" | "Medium" | "Low";
  benefits: string[];
  documents_required: string[];
  application_steps: string[];
  application_link: string;
  target_industries: string[];
  max_turnover?: number;
  min_turnover?: number;
  official_authority: string;
  official_source_url: string;
  last_verified: string;
  verified_status: "verified" | "unverified";
  match_basis: string;
  notes?: string | null;
}

export interface CategorizedSchemes {
  recommended: SchemeItem[];
  eligible: SchemeItem[];
  partially_eligible: SchemeItem[];
  not_eligible: SchemeItem[];
}

export interface BusinessSchemesResponse {
  generated_at: string;
  total_schemes: number;
  schemes: CategorizedSchemes;
  /**
   * Top-level disclaimer from the engine. Every UI surface that
   * renders schemes must include this text somewhere visible to the
   * user — Part 3 / Part 9 of the H6.3 brief.
   */
  disclaimer: string;
}

export class SchemesService {
  async getSchemes(): Promise<BusinessSchemesResponse> {
    return apiClient.get<BusinessSchemesResponse>("/api/v1/business/schemes");
  }
}

export const schemesService = new SchemesService();
