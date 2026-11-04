import { Metadata } from "next";
import { BusinessGoalsView } from "@/features/goals/components/BusinessGoalsView";

export const metadata: Metadata = {
  title: "Business Goals & Progress Tracker | UrsBiz",
  description:
    "Track measurable strategic business targets backed by deterministic ledger data, honest data availability states, and immutable audit logs.",
};

export default function GoalsPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <BusinessGoalsView />
    </div>
  );
}
