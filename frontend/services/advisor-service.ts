/**
 * Service module — GET /api/v1/advisor
 */

import { apiClient } from "@/services/api-client";
import type { AdvisorAggregateResponse, AdvisorResponse } from "@/types/advisor";

export const advisorService = {
  get: async (): Promise<AdvisorResponse> => {
    const raw = await apiClient.get<any>("/api/v1/advisor");
    const report = raw?.report || raw;

    const summary = raw?.business_summary || {
      legal_name: report?.executive_summary ? "Business Profile" : "UrsBiz Business",
      industry: "General MSME",
      archetype: report?.business_maturity_level || "Growth Enterprise",
      overall_score: report?.overall_advisor_score ?? 75,
      overall_level: "Established",
      band: "Established",
      dna_match: 85,
      rule_critical_count: 0,
      rule_high_count: 2,
      recommendation_count: report?.recommendations?.total_count ?? 5,
      roadmap_items_count: 4,
      highest_priority_action: "Review priorities",
      headline: report?.executive_summary || "Operational overview loaded successfully.",
    };

    const healthReview = raw?.health_review || {
      current_overall_score: report?.overall_advisor_score ?? 75,
      current_overall_level: "Established",
      projected_3m: (report?.overall_advisor_score ?? 75) + 3,
      projected_6m: (report?.overall_advisor_score ?? 75) + 6,
      projected_12m: (report?.overall_advisor_score ?? 75) + 10,
      delta_3m: 3,
      delta_6m: 6,
      delta_12m: 10,
      band: "Established",
      risk_count: report?.risks?.total_risks_detected ?? 2,
      opportunity_count: report?.growth_opportunities?.length ?? 3,
    };

    return {
      generated_at: raw?.generated_at || new Date().toISOString(),
      advisor_id: raw?.advisor_id || "advisor_v1",
      business_summary: summary,
      daily_brief: raw?.daily_brief || [],
      weekly_summary: raw?.weekly_summary || [],
      health_review: healthReview,
      priority_changes: raw?.priority_changes || [],
      upcoming_risks: raw?.upcoming_risks || [],
      missed_opportunities: raw?.missed_opportunities || [],
      suggested_actions: raw?.suggested_actions || [],
      inputs: raw?.inputs || {
        twin_generated_at: null,
        rules_generated_at: null,
        recommendations_generated_at: null,
        roadmap_generated_at: null,
        decision_generated_at: null,
        predictive_generated_at: null,
        notifications_generated_at: null,
      },
    };
  },

  getAggregate: async (): Promise<AdvisorAggregateResponse> => {
    const raw = await apiClient.get<any>("/api/v1/business/advisor");
    return {
      generated_at: raw?.generated_at || new Date().toISOString(),
      report: raw?.report || raw,
    };
  },
};
