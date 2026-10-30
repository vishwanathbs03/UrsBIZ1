"use client";

/**
 * Barrel for the dashboard feature module. Re-exports the hook
 * + each card so consumers can `import { DashboardView } from
 * "@/features/dashboard"`.
 */

export { DashboardView } from "./DashboardView";
export { DashboardKpiCards } from "./DashboardKpiCards";
export { DashboardPerformanceChart } from "./DashboardPerformanceChart";
export { DashboardAssistantSpotlight } from "./DashboardAssistantSpotlight";
export { useDashboardData } from "./use-dashboard-data";
export { useDashboardEndpointData } from "./use-dashboard-endpoint-data";
export { KPICard } from "./KPICard";
export { KPIGrid } from "./KPIGrid";
export { HealthScoreCard } from "./HealthScoreCard";
export { AISummaryCard } from "./AISummaryCard";
export { RecentActivityCard } from "./RecentActivityCard";
export { QuickActionsCard } from "./QuickActionsCard";
export type {
  DashboardData,
  DashboardDataState,
  UseDashboardDataResult,
} from "./use-dashboard-data";
export {
  useIntelligenceQuery,
  useScoresQuery,
  useDnaQuery,
  useRulesQuery,
  useDecisionQuery,
} from "./use-dashboard-data";
