import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { SalesView } from "@/features/sales/SalesView";

export const metadata: Metadata = {
  title: "Sales Intelligence | UrsBiz",
  description:
    "Upload historical MSME sales records to uncover customer behavior, product velocity, and validated revenue patterns.",
};

export default function SalesPage() {
  return (
    <ProtectedRoute>
      <SalesView />
    </ProtectedRoute>
  );
}
