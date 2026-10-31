import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { BusinessSurface } from "./BusinessSurface";

export const metadata: Metadata = {
  title: "Business Profile | UrsBiz",
  description: "Your business profile, classification, and Business Digital Twin inputs.",
};

/**
 * /business — the Business Digital Twin surface.
 *
 * The page is a thin server component that supplies metadata; the
 * interactive surface lives in `BusinessSurface.tsx` (a client
 * component) so this file can stay a server component for the
 * `export const metadata` Next.js pattern.
 */
export default function BusinessPage() {
  return (
    <ProtectedRoute>
      <BusinessSurface />
    </ProtectedRoute>
  );
}
