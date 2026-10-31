import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ForecastExecutiveView } from "@/features/forecast/ForecastExecutiveView";

export const metadata: Metadata = {
  title: "Business Forecast | UrsBiz",
  description: "Explainable scenario projections based on your current business profile.",
};

/**
 * /predictive-analytics — Sprint H6.2 executive simplification.
 *
 * The page renders the executive orchestrator (hero + main chart +
 * 3 risks + 3 opportunities + assumptions + CTA). The pre-H6.2
 * PredictiveAnalyticsView is preserved inside a collapsible
 * accordion at the bottom of the page.
 */
export default function PredictiveAnalyticsPage() {
  return (
    <ProtectedRoute>
      <ForecastExecutiveView />
    </ProtectedRoute>
  );
}
