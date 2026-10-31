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

  // 9-Pillar Business Growth Consultant Dimensions
  what_is_happening?: string | null;
  why_it_matters?: string | null;
  root_cause?: string | null;
  missed_opportunity?: string | null;
  action_scenario?: string | null;
  cost_of_inaction?: string | null;
  measurement_kpis?: string[];
  implementation_difficulty?: "Quick Win" | "Tactical" | "Strategic";
  prerequisites_and_tradeoffs?: string[];
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

export interface ImplementationPhase {
  phase: string;
  timeframe: string;
  focus: string;
  steps: string[];
  resources?: string;
}

export interface RecommendationExplainResponse {
  recommendation_id: string;
  title: string;
  explanation: string;
  is_ai_generated: boolean;
  practical_steps: string[];
  limitations: string[];

  // 9-Pillar Executive Diagnostic Brief
  executive_summary?: string | null;
  what_is_happening?: string | null;
  what_is_going_wrong?: string | null;
  why_is_it_happening?: string | null;
  missed_opportunity?: string | null;
  action_outcome?: string | null;
  inaction_cost?: string | null;
  implementation_phases?: ImplementationPhase[];
  measurement_kpis?: string[];
  confidence_score?: number | null;
  data_quality_label?: string | null;
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
  | "Helpful"
  | "Useful"
  | "Not helpful"
  | "Incorrect information"
  | "Missing information"
  | "Not relevant to my business"
  | "Not relevant"
  | "Already implemented"
  | "Need more explanation"
  | "Not feasible";

export type AnswerabilityStatus =
  | "ANSWERABLE"
  | "PARTIALLY_ANSWERABLE"
  | "NEEDS_CLARIFICATION"
  | "INSUFFICIENT_DATA"
  | "UNSUPPORTED_REQUEST";

export type StatementClassification =
  | "VERIFIED_FACT"
  | "CALCULATED_RESULT"
  | "FORECAST_ESTIMATE"
  | "AI_INTERPRETATION"
  | "GENERAL_BUSINESS_ADVICE"
  | "HYPOTHESIS";

export interface GroundedFinding {
  id: string;
  claim_type: StatementClassification;
  statement: string;
  source_module: string;
  source_metric?: string | null;
  time_period?: string | null;
  value?: any;
  unit?: string | null;
  currency?: string | null;
  calculation_methodology?: string | null;
  data_freshness_iso?: string | null;
  data_quality?: "High" | "Moderate" | "Limited" | "Insufficient";
  provenance_record_ref?: string | null;
  freshness_status?: string | null;
}

export interface AnswerQualityEvaluation {
  overall_quality_score: number;
  normalized_score: number;
  dimension_scores: Record<string, number>;
  evidence_coverage_pct: number;
  missing_information: string[];
  warnings: string[];
  validation_status: "PASSED" | "WARNING" | "FAILED";
}

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

export interface RecommendationAskRequest {
  question: string;
  session_id?: string | null;
  conversation_history?: Array<{ role: string; content: string }> | null;
}

export interface CalculationStep {
  name: string;
  formula: string;
  result: string;
}

export interface SituationalRecommendation {
  title: string;
  category: string;
  priority: "Critical" | "High" | "Medium" | "Low";
  situational_rationale: string;
  action_steps: string[];
  timeframe: string;
  cost_of_delay: string;
}

export interface ToolExecutionTrace {
  tool: string;
  status: string;
  duration_ms: number;
  arguments?: Record<string, any>;
  error?: string;
}

export interface RecommendationAskResponse {
  question: string;
  intent: string;
  direct_answer: string;
  evidence_points: string[];
  calculations: CalculationStep[];
  situational_recommendations: SituationalRecommendation[];
  data_limitations_and_gaps: string[];
  follow_up_questions: string[];
  tool_executions?: ToolExecutionTrace[];
  query_type?: string | null;
  is_ai_generated: boolean;
  generated_at: string;
  answerability?: AnswerabilityStatus;
  answerability_reason?: string | null;
  grounded_findings?: GroundedFinding[];
  quality_evaluation?: AnswerQualityEvaluation | null;
  trust_label?: string;
}
