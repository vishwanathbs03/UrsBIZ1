import { Metadata } from "next";
import { MetricsDictionaryView } from "@/features/metrics-dictionary/components/MetricsDictionaryView";

export const metadata: Metadata = {
  title: "Metrics Dictionary & Calculation Explorer | UrsBiz",
  description:
    "Authoritative mathematical definitions, exclusion rules, industry benchmarks, and step-by-step calculation explorer for all UrsBiz business metrics.",
};

export default function MetricsPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <MetricsDictionaryView />
    </div>
  );
}
