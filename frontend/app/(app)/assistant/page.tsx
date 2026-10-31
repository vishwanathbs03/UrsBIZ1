import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AssistantView } from "@/features/assistant";

export const metadata: Metadata = {
  title: "AI Business Assistant | UrsBiz",
  description:
    "Ask about your business score, priorities, schemes, or risks. Grounded in your own Digital Twin, rules, and recommendations.",
};

/**
 * AI Business Assistant — Sprint 7 Part 1.
 *
 * Frontend only. The page composes a chat layout that
 * reads the existing Twin, Recommendations, Roadmap,
 * Insights, and Rules payloads and assembles a
 * deterministic response locally. There is no LLM
 * provider call, no streaming, and no memory.
 */
export default function AssistantPage() {
  return (
    <ProtectedRoute>
      <AssistantView />
    </ProtectedRoute>
  );
}
