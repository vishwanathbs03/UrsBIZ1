import { Metadata } from "next";
import { WhatIfScenarioSimulatorView } from "@/features/what-if/components/WhatIfScenarioSimulatorView";

export const metadata: Metadata = {
  title: "What-If Scenario Simulator | UrsBiz",
  description:
    "Test hypothetical revenue shocks, supplier cost changes, pricing elasticity, and cash runway impact before committing real resources.",
};

export default function WhatIfPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <WhatIfScenarioSimulatorView />
    </div>
  );
}
