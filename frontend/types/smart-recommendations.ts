/**
 * Type definitions for Context-Aware Smart Recommendations (Phase 5 Advanced Intelligence).
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

export interface CrossSignalInsight {
  id: string;
  title: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  pattern_type: string;
  signals_combined: string[];
  business_implication: string;
  recommended_action: string;
  evidence_strength: "Strong Evidence" | "Moderate Evidence" | "Limited Evidence";
  linked_recommendation_id?: string | null;
}

export interface RootCauseAnalysisItem {
  id: string;
  symptom: string;
  verified_factors: string[];
  plausible_causes: string[];
  data_gaps_and_unknowns: string[];
  urgency: "Immediate" | "Near-term" | "Watch";
}

export interface OpportunityItem {
  id: string;
  title: string;
  category: string;
  rationale: string;
  evidence_strength: "Strong Evidence" | "Moderate Evidence" | "Limited Evidence";
  feasibility: "High" | "Medium" | "Low";
  estimated_impact_description: string;
  first_step: string;
  timeframe: string;
}

export interface NextBestAction {
  recommendation_id: string;
  title: string;
  category: string;
  priority_score: number;
  priority: "Critical" | "High" | "Medium" | "Low";
  why_now: string;
  cost_of_delay: string;
  effort_level: "Low" | "Medium" | "High";
  time_to_value: string;
  first_immediate_step: string;
  source_modules: string[];
}

export interface NextBestActionResponse {
  top_priority_action?: NextBestAction | null;
  next_three_actions: NextBestAction[];
  long_term_initiatives: NextBestAction[];
}

export interface GrowthMilestone {
  milestone: string;
  target_date_window: string;
  metric_to_track: string;
}

export interface GrowthHorizonPlan {
  horizon: "0-30 Days" | "31-90 Days" | "3-12 Months";
  title: string;
  focus: string;
  actions: string[];
  milestones: GrowthMilestone[];
  kpis: string[];
}

export interface PersonalizedGrowthStrategy {
  business_name: string;
  industry: string;
  strategy_summary: string;
  is_ai_generated: boolean;
  horizons: GrowthHorizonPlan[];
  critical_success_factors: string[];
}

export interface ScenarioSimulationRequest {
  sales_growth_pct: number;
  repeat_customer_rate_improvement_pct: number;
  expense_reduction_pct: number;
  concentration_reduction_pct: number;
}

export interface ScenarioMetricResult {
  metric_name: string;
  baseline_value: number;
  projected_value: number;
  delta_value: number;
  unit: string;
  formula_explanation: string;
}

export interface ScenarioSimulationResponse {
  baseline_revenue: number;
  projected_revenue: number;
  estimated_gross_profit_change: number;
  metrics: ScenarioMetricResult[];
  key_takeaways: string[];
  projection_disclaimer: string;
}

export type FeedbackType =
  | "Useful"
  | "Not relevant"
  | "Already implemented"
  | "Not feasible"
  | "Need more explanation";

export interface RecommendationFeedbackCreate {
  recommendation_id: string;
  feedback_type: FeedbackType;
  outcome_notes?: string | null;
}

export interface RecommendationFeedbackResponse {
  id: number;
  business_id: number;
  recommendation_id: string;
  feedback_type: string;
  suppress_recommendation: boolean;
  outcome_notes?: string | null;
  created_at: string;
}

export interface AdvancedRecommendationsOverviewResponse {
  business_id: number;
  business_name: string;
  generated_at: string;
  next_best_action: NextBestActionResponse;
  multi_signal_insights: CrossSignalInsight[];
  root_cause_analyses: RootCauseAnalysisItem[];
  opportunities: OpportunityItem[];
  evidence_summary: Record<string, any>;
}
