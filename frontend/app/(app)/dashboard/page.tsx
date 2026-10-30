import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { DashboardView } from "@/features/dashboard";

export const metadata: Metadata = {
  title: "Executive Command Center | UrsBiz",
  description:
    "How is my business doing, what deserves attention, and what should I do next? Health, top priorities, biggest risk, biggest opportunity.",
};

/**
 * Main Business Intelligence Dashboard.
 *
 * Sprint 4 – Part 1. Renders the live snapshot of every
 * upstream payload (intelligence, scores, DNA, rules, AI
 * decision) in a single responsive grid. The view is a client
 * component (it owns data loading + state) and is wrapped in
 * <ProtectedRoute> so unauthenticated visitors are redirected.
 */
export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardView />
    </ProtectedRoute>
  );
}
