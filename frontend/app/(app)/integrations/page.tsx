import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { IntegrationsView } from "@/features/integrations";

export const metadata: Metadata = {
  title: "Data Integrations & Connectors | UrsBiz",
  description:
    "Modular connector framework for accounting (Tally, Zoho Books) and POS data sources with encrypted credentials and provenance tracking.",
};

export default function IntegrationsPage() {
  return (
    <ProtectedRoute>
      <IntegrationsView />
    </ProtectedRoute>
  );
}
