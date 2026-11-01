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
  is_autonomous_opportunity?: boolean;
  opportunity_quality_status?: string | null;
  opportunity_hypothesis_id?: string | null;

  // Personalization & Business DNA Adaptation
  personalization_explanation?: PersonalizationExplanation | null;
  personalization_score?: number | null;
  goal_alignment_score?: number | null;
  maturity_fit_score?: number | null;
  constraint_adjusted_feasibility?: number | null;
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

export type OpportunityQualityStatus =
  | "VERIFIED_OPPORTUNITY"
  | "PROMISING_OPPORTUNITY"
  | "NEEDS_INVESTIGATION"
  | "INSUFFICIENT_EVIDENCE"
  | "NOT_ACTIONABLE";

export interface OpportunitySupportingSignal {
  signal_name: string;
  observed_value: any;
  baseline_value?: any;
  source_module: string;
  interpretation: string;
}

export interface OpportunityHypothesis {
  id: string;
  title: string;
  category: string;
  business_problem_or_opportunity: string;
  quality_status: OpportunityQualityStatus;
  supporting_signals: OpportunitySupportingSignal[];
  evidence_references: string[];
  relevant_time_period: string;
  possible_explanation: string;
  alternative_explanations: string[];
  confidence: number;
  missing_information: string[];
  recommended_investigation: string;
  potential_business_benefit: string;
  cost_of_inaction?: string | null;
  limitations: string[];
  observed_facts: string[];
  inferred_explanations: string[];
  correlation_causation_disclaimer: string;
  relevant_entity?: string | null;
  underlying_issue?: string | null;
  version: number;
  version_notes?: string | null;
  conflicting_signals: string[];
  validation_status: string;
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
  quality_status?: OpportunityQualityStatus;
  hypothesis_id?: string | null;
  cost_of_inaction?: string | null;
  observed_facts?: string[];
  inferred_explanations?: string[];
  alternative_explanations?: string[];
  recommended_investigation?: string | null;
  confidence?: number;
  version?: number;
  version_notes?: string | null;
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
  | "Relevant"
  | "Not helpful"
  | "Incorrect information"
  | "Missing information"
  | "Not relevant to my business"
  | "Not relevant"
  | "Already implemented"
  | "Need more explanation"
  | "Need more information"
  | "Not feasible"
  | "Too expensive"
  | "Not aligned with my current goal";

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
  opportunity_hypotheses?: OpportunityHypothesis[];
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

export interface PersonalizationExplanation {
  why_relevant_to_this_business: string;
  triggering_conditions: string[];
  maturity_suitability: string;
  constraints_considered: string[];
  missing_information: string[];
  ranking_rationale: string;
  goal_alignment_score: number;
  maturity_fit_score: number;
  preference_score: number;
  constraint_penalty: number;
  is_critical_risk_override?: boolean;
}

export interface RecommendationPersonalizationProfile {
  business_id: number;
  business_name: string;
  industry: string;
  sub_industry?: string | null;
  business_type?: string | null;
  dna_archetype: string;
  dna_stage: string;
  evaluated_maturity: "Early Stage" | "Growing" | "Established";
  maturity_drivers: string[];
  active_goals: string[];
  active_constraints: string[];
  preferred_effort_level: string;
  preferred_investment_level: string;
  focus_areas: string[];
  feedback_summary: Record<string, number>;
  source: string;
  updated_at: string;
}

export interface PersonalizationSettingsUpdate {
  goals: string[];
  constraints: string[];
  preferred_effort_level?: string;
  preferred_investment_level?: string;
  focus_areas?: string[];
}

export interface RecommendationDependency {
  recommendation_id: string;
  depends_on_id: string;
  dependency_type: "PREREQUISITE" | "ENABLER" | "DATA_DEPENDENCY";
  reason: string;
  is_satisfied: boolean;
}

export interface RecommendationConflict {
  conflict_id: string;
  rec_a_id: string;
  rec_a_title: string;
  rec_b_id: string;
  rec_b_title: string;
  conflict_type: "RESOURCE_COMPETITION" | "STRATEGIC_CONTRADICTION" | "TIMING_MISMATCH";
  description: string;
  evidence_a: string[];
  evidence_b: string[];
  trade_off_analysis: string;
  recommended_resolution: string;
  owner_decision_required: boolean;
}

export interface SequencedAction {
  sequence_order: number;
  stage: "FIRST_ACTION" | "SUPPORTING_ACTION" | "DEPENDENT_ACTION" | "STRATEGIC_INITIATIVE";
  recommendation_id: string;
  title: string;
  category: string;
  priority: string;
  timeframe_label: string;
  why_this_order: string;
  unlocks_recommendation_ids: string[];
  status: string;
}

export interface PortfolioObsoleteItem {
  recommendation_id: string;
  title: string;
  reason_obsolete: string;
  previous_status: string;
}

export interface RecommendationPortfolioResponse {
  business_id: number;
  business_name: string;
  generated_at: string;
  portfolio_health_score: number;
  total_active_count: number;
  critical_risks: SmartRecommendationItem[];
  quick_wins: SmartRecommendationItem[];
  short_term_improvements: SmartRecommendationItem[];
  strategic_initiatives: SmartRecommendationItem[];
  dependencies: RecommendationDependency[];
  conflicts: RecommendationConflict[];
  execution_sequence: SequencedAction[];
  obsolete_recommendations: PortfolioObsoleteItem[];
  resource_summary: Record<string, any>;
}

// --------------------------------------------------------------------------
// Closed-Loop Outcome Tracking & Business Measurement (Phase 5)
// --------------------------------------------------------------------------

export interface OutcomeRecordingRequest {
  is_started?: boolean | null;
  is_completed?: boolean | null;
  is_abandoned?: boolean | null;
  started_at?: string | null;
  completed_at?: string | null;
  actual_effort?: string | null;
  owner_rating?: number | null;
  qualitative_feedback?: string | null;
  perceived_utility?: string | null;
  non_completion_reason?: string | null;
  still_relevant?: boolean | null;
  notes?: string | null;
}

export interface MetricComparison {
  metric_name: string;
  unit: string;
  baseline_value: number;
  post_value: number;
  delta_absolute: number;
  delta_percentage: number;
  direction: "INCREASED" | "DECREASED" | "UNCHANGED";
  observation_statement: string;
}

export interface BeforeAfterMeasurementResponse {
  recommendation_id: string;
  title: string;
  completed_at?: string | null;
  measurement_window_days: number;
  window_status: "COMPLETED_WINDOW" | "PARTIAL_WINDOW_IN_PROGRESS" | "INSUFFICIENT_BASELINE_DATA";
  elapsed_days_since_completion: number;
  pre_period_start?: string | null;
  pre_period_end?: string | null;
  post_period_start?: string | null;
  post_period_end?: string | null;
  comparison_methodology: string;
  data_gaps: string[];
  metrics: MetricComparison[];
  causal_disclaimer: string;
  learning_quality_tier: string;
}

export interface OutcomeTrackingResponse {
  id: number;
  business_id: number;
  recommendation_id: string;
  is_started: boolean;
  is_completed: boolean;
  is_abandoned: boolean;
  started_at?: string | null;
  completed_at?: string | null;
  actual_effort?: string | null;
  owner_rating?: number | null;
  qualitative_feedback?: string | null;
  perceived_utility?: string | null;
  non_completion_reason?: string | null;
  still_relevant: boolean;
  measured_outcome_summary?: string | null;
  measurement?: BeforeAfterMeasurementResponse | null;
  created_at: string;
  updated_at: string;
}

export interface CategoryEffectivenessItem {
  category: string;
  total_suggested: number;
  total_accepted: number;
  total_completed: number;
  total_abandoned: number;
  acceptance_rate_pct: number;
  completion_rate_pct: number;
  average_rating?: number | null;
  positive_outcomes_count: number;
  statistical_reliability: "Reliable" | "Moderate" | "Insufficient Sample Size";
  small_sample_warning?: string | null;
}

export interface RecommendationEffectivenessResponse {
  business_id: number;
  total_recommendations: number;
  total_accepted: number;
  total_completed: number;
  total_dismissed: number;
  total_abandoned: number;
  overall_acceptance_rate_pct: number;
  overall_completion_rate_pct: number;
  abandonment_reasons_breakdown: Record<string, number>;
  category_effectiveness: CategoryEffectivenessItem[];
  top_performing_categories: string[];
  insufficient_evidence_categories: string[];
  small_sample_safeguard_applied: boolean;
  methodology_notes: string[];
}

export interface RecommendationAuditEventItem {
  id: number;
  recommendation_id: string;
  version: number;
  title: string;
  category: string;
  priority: string;
  priority_score: number;
  evidence_version?: string | null;
  evidence_summary?: string | null;
  event_type: string;
  event_notes?: string | null;
  metrics_snapshot?: Record<string, any> | null;
  created_at: string;
}

export interface RecommendationHistoryResponse {
  recommendation_id: string;
  current_version: number;
  events: RecommendationAuditEventItem[];
}

export interface CompleteHistoryResponse {
  business_id: number;
  total_events: number;
  events: RecommendationAuditEventItem[];
}

// --------------------------------------------------------------------------- //
// Proactive AI Business Monitoring & Event Intelligence (Phase 5)             //
// --------------------------------------------------------------------------- //

export interface BusinessSignalItem {
  event_id: string;
  business_id: number;
  event_type: string;
  source: string;
  relevant_entity?: string | null;
  detected_at: string;
  evidence: Record<string, any>;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL";
  priority_score: number;
  data_period: string;
  event_version: number;
  title: string;
  what_changed: string;
  why_it_matters: string;
  suggested_action: string;
  confidence: number;
  is_suppressed: boolean;
  suppression_reason?: string | null;
  escalation_level: number;
  linked_recommendation_id?: string | null;
  status: string;
}

export interface BusinessSignalsFeedResponse {
  business_id: number;
  total_signals: number;
  active_signals_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_and_info_count: number;
  signals: BusinessSignalItem[];
  last_evaluated_at: string;
}

export interface RecommendationRefreshDetail {
  recommendation_id: string;
  refresh_reason: string;
  old_priority_score: number;
  new_priority_score: number;
  old_status: string;
  new_status: string;
  explanation: string;
  refreshed_at: string;
}

export interface MonitoringEvaluationResponse {
  business_id: number;
  evaluated_at: string;
  new_events_detected: number;
  suppressed_events: number;
  refreshed_recommendations: number;
  signals: BusinessSignalItem[];
  recommendation_refreshes: RecommendationRefreshDetail[];
}

export interface MonitoringPreferencesSchema {
  business_id: number;
  monitored_metrics: string[];
  areas_of_interest: string[];
  alert_frequency: string;
  preferred_notification_types: string[];
  min_severity: string;
  cooldown_days: number;
  updated_at?: string | null;
}

export interface MonitoringPreferencesUpdate {
  monitored_metrics?: string[];
  areas_of_interest?: string[];
  alert_frequency?: string;
  preferred_notification_types?: string[];
  min_severity?: string;
  cooldown_days?: number;
}
