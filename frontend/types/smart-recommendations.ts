/**
 * Type definitions for Context-Aware Smart Recommendations (Phase 5).
 */

export type RecommendationCategory =
  | "Revenue Growth"
  | "Cost Optimization"
  | "Customer Retention"
  | "Product Performance"
  | "Demand and Sales Planning"
  | "Digital Transformation"
  | "Financial Management"
  | "Operational Efficiency"
  | "Government Schemes and Funding"
  | "Risk Reduction";

export type RecommendationPriority = "Critical" | "High" | "Medium" | "Low";

export type RecommendationStatus =
  | "New"
  | "Viewed"
  | "Accepted"
  | "In Progress"
  | "Completed"
  | "Dismissed";

export interface ActionStep {
  step_number: number;
  title: string;
  description: string;
  timeframe: string;
  resources_required: string;
}

export interface ActionPlan {
  objective: string;
  steps: ActionStep[];
  suggested_timeframe: string;
  success_metric: string;
}

export interface SmartRecommendationItem {
  id: string;
  title: string;
  category: RecommendationCategory;
  priority: RecommendationPriority;
  priority_score: number;
  description: string;
  business_context: string;
  evidence: string[];
  reasoning: string;
  recommended_actions: string[];
  action_plan?: ActionPlan | null;
  expected_benefit: string;
  estimated_impact?: number | null;
  impact_unit?: string | null;
  confidence: number;
  data_quality: "High" | "Moderate" | "Limited" | "Insufficient";
  limitations: string[];
  source_modules: string[];
  source_module_link?: string | null;
  created_at: string;
  status: RecommendationStatus;
  status_updated_at?: string | null;
  notes?: string | null;
}

export interface SmartRecommendationsResponse {
  generated_at: string;
  business_id: number;
  business_name: string;
  total_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  status_counts: Record<string, number>;
  category_counts: Record<string, number>;
  recommendations: SmartRecommendationItem[];
}

export interface RecommendationExplainResponse {
  recommendation_id: string;
  title: string;
  explanation: string;
  is_ai_generated: boolean;
  practical_steps: string[];
  limitations: string[];
}
