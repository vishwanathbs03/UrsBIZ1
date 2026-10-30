import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ReportsView } from "@/features/reports";

export const metadata: Metadata = {
  title: "Executive Report | UrsBiz",
  description:
    "Download the executive PDF and CSV reports for your business — branded UrsBiz, with methodology and limitations clearly stated.",
};

/**
 * Executive Reports — Sprint 6 Part 2.
 *
 * Frontend only. Aggregates the existing Digital Twin,
 * Roadmap, Recommendations, Scores, DNA, Rules, Decision,
 * and Intelligence endpoints into a single print-ready
 * executive report with a sticky table-of-contents
 * sidebar and jump-to-section navigation.
 */
export default function ReportsPage() {
  return (
    <ProtectedRoute>
      <ReportsView />
    </ProtectedRoute>
  );
}
