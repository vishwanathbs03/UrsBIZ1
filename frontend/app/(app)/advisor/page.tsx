import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AdvisorExecutiveView } from "@/features/advisor/AdvisorExecutiveView";

export const metadata: Metadata = {
  title: "Business Advisor | UrsBiz",
  description:
    "What should this business prioritize now? Three priorities, strengths and concerns, and detailed analysis.",
};

/**
 * Autonomous Business Advisor — Sprint H6.2 executive simplification.
 *
 * The page renders the executive orchestrator (brief + top 3
 * priorities + strengths/concerns + impact/effort buckets) and
 * preserves the pre-H6.2 detailed analysis inside a collapsible
 * accordion.
 */
export default function AdvisorPage() {
  return (
    <ProtectedRoute>
      <AdvisorExecutiveView />
    </ProtectedRoute>
  );
}
