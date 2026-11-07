/**
 * Service layer.
 *
 * Per-domain service modules (e.g. business, simulation) live here in
 * later milestones and call into the shared `apiClient`.
 */
export { apiClient, ApiError, apiRequest } from "./api-client";
export type { RequestOptions } from "./api-client";

export {
  authService,
  AuthServiceError,
  type LoginPayload,
  type RegisterPayload,
} from "./auth-service";

export { intelligenceService } from "./intelligence-service";
export { scoresService } from "./scores-service";
export { dnaService } from "./dna-service";
export { rulesService } from "./rules-service";
export { decisionService } from "./decision-service";
export { recommendationsService } from "./recommendations-service";
export { smartRecommendationsService } from "./smart-recommendations-service";
export { roadmapService } from "./roadmap-service";
export { twinService } from "./twin-service";
export {
  chatService,
  type ChatMessageOut,
  type ChatMessageAppendResponse,
  type ChatSessionDetail,
  type ChatSessionSummary,
  type ChatSource,
} from "./chat-service";

export { advisorService } from "./advisor-service";
export { businessService } from "./business-service";
export { dashboardService } from "./dashboard-service";
export { businessAnalyticsService } from "./business-analytics-service";
export { schemesService } from "./schemes-service";
export {
  decisionWorkbenchService,
  type DecisionOptionEvaluation,
  type DecisionEvidenceItem,
  type DecisionEstimatedImpact,
  type DecisionEvaluateRequest,
  type DecisionEvaluateResponse,
  type DecisionCreateRequest,
  type DecisionUpdateRequest,
  type DecisionOut,
  type DecisionListResponse,
} from "./decision-workbench-service";

export {
  whatIfScenarioService,
  type ScenarioType,
  type ScenarioParameterIn,
  type AssumptionItem,
  type ScenarioCaseResult,
  type MitigationAction,
  type SimulationResult,
  type ScenarioSimulateRequest,
  type ScenarioSaveRequest,
  type ScenarioUpdateRequest,
  type ScenarioOut,
  type ScenarioListResponse,
  type ScenarioCompareResponse,
} from "./what-if-scenario-service";

export {
  dataConfidenceService,
  type IngestionReconciliationSummary,
  type ObservationWindowSummary,
  type InsightReadinessItem,
  type DataAnomalySummary,
  type DataImprovementAction,
  type DataConfidenceCentreResponse,
  type DataQualityReportPayload,
} from "./data-confidence-service";

export {
  metricsDictionaryService,
  type MetricCategory,
  type MetricVariable,
  type CalculationStep,
  type MetricDefinition,
  type MetricExplorerResult,
  type MetricDictionaryResponse,
} from "./metrics-dictionary-service";

export {
  alertsService,
  type EventSeverity,
  type EventNature,
  type EventStatus,
  type BusinessSignalItem,
  type AlertListResponse,
  type AlertSummaryResponse,
  type AlertStatusUpdate,
  type AlertAuditHistoryItem,
  type AlertExplainResponse,
  type ListAlertsParams,
} from "./alerts-service";

export {
  goalsService,
  type GoalMeasurementMethod,
  type GoalStatus,
  type GoalDataAvailability,
  type GoalMetricKey,
  type RelatedItem,
  type BusinessGoalAudit,
  type BusinessGoal,
  type BusinessGoalListResponse,
  type BusinessGoalCreate,
  type BusinessGoalUpdate,
  type BusinessGoalStatusUpdate,
  type BusinessGoalManualProgress,
  type GoalAIExplanationResponse,
  type ListGoalsParams,
} from "./goals-service";

export {
  reportsService,
  type ReportType,
  type ReportCategory,
  type ReportFileFormat,
  type ReportCoverageStatus,
  type ReportCatalogItem,
  type ReportCatalogResponse,
  type ReportTableData,
  type ReportProvenance,
  type ReportPreviewRequest,
  type ReportPreviewResponse,
  type ReportGenerateRequest,
  type ReportItemOut,
  type ReportHistoryResponse,
} from "./reports-service";

export {
  collaborationService,
  type BusinessRole,
  type ApprovalEntityType,
  type ApprovalStatus,
  type MemberOut,
  type MemberListResponse,
  type InvitationOut,
  type InvitationListResponse,
  type InvitationCreateRequest,
  type InvitationAcceptRequest,
  type InvitationAcceptResponse,
  type TransferOwnershipRequest,
  type TransferOwnershipResponse,
  type ApprovalAuditOut,
  type ApprovalRequestOut,
  type ApprovalRequestCreate,
  type ApprovalReviewRequest,
  type ApprovalListResponse,
  type ApprovalSummaryResponse,
} from "./collaboration-service";

export {
  integrationService,
  type ConnectionStatus,
  type SyncExecutionStatus,
  type OperationalStatus,
  type ConnectorCatalogueItem,
  type ConnectionOut,
  type ConnectionTestResultOut,
  type SyncExecutionOut,
  type IntegrationAuditOut,
} from "./integration-service";

export {
  chatFeedbackService,
  FEEDBACK_CATEGORIES,
  type FeedbackCategory,
  type ChatFeedbackResponse,
  type ChatFeedbackCreateRequest,
  type ChatFeedbackUpdateRequest,
  type GroundingCorrelationMetrics,
  type ChatFeedbackAnalytics,
} from "./chat-feedback-service";



