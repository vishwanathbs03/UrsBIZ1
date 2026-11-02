import { Metadata } from "next";
import { DataConfidenceCentreView } from "@/features/data-confidence/components/DataConfidenceCentreView";

export const metadata: Metadata = {
  title: "Data Quality & Confidence Centre | UrsBiz",
  description:
    "Review data quality completeness, valid ingestion rates, observation windows, and insight sufficiency matrix across your business.",
};

export default function DataConfidencePage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <DataConfidenceCentreView />
    </div>
  );
}
