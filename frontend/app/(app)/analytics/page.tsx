import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AnalyticsExecutiveView } from "@/features/analytics/AnalyticsExecutiveView";

export const metadata: Metadata = {
  title: "Analytics | UrsBiz",
  description:
    "How is my business performing, and what should I improve? Overall score, strongest and weakest dimensions, readiness, and comparison.",
};

/**
 * Business Analytics Dashboard — Sprint H6.2 executive simplification.
 *
 * The page renders the executive orchestrator (hero + 4 tabs) and
 * preserves the pre-H6.2 detailed analytics view inside a collapsible
 * accordion at the bottom of the page.
 */
export default function AnalyticsPage() {
  return (
    <ProtectedRoute>
      <AnalyticsExecutiveView />
    </ProtectedRoute>
  );
}
