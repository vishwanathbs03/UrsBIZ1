import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { IntelligenceView } from "@/features/intelligence/IntelligenceView";

export const metadata: Metadata = {
  title: "Business Digital Twin | UrsBiz",
  description: "Deterministic Business DNA, SWOT Analysis, Readiness Index & Growth Opportunities",
};

export default function BusinessIntelligencePage() {
  return (
    <ProtectedRoute>
      <IntelligenceView />
    </ProtectedRoute>
  );
}
