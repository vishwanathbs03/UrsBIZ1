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
