import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { CollaborationView } from "@/features/collaboration";

export const metadata: Metadata = {
  title: "Team & Approvals (RBAC) | UrsBiz",
  description:
    "Multi-user MSME collaboration with role-based access control (Owner, Administrator, Manager, Analyst, Viewer) and dual-control approval workflows.",
};

export default function CollaborationPage() {
  return (
    <ProtectedRoute>
      <CollaborationView />
    </ProtectedRoute>
  );
}
