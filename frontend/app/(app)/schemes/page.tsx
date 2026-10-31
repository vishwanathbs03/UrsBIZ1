import type { Metadata } from "next";
import { SchemesView } from "@/features/schemes/SchemesView";

export const metadata: Metadata = {
  title: "Government Schemes | UrsBiz",
  description:
    "Match your business profile against official MSME, NSIC, SIDBI, KVIC, MUDRA, and Department of Commerce schemes. Matching is informational — final eligibility and approval are decided by the official authority.",
};

/**
 * Government Schemes — Sprint H6.3.
 *
 * Frontend-only page that surfaces the static MSME / NSIC / SIDBI /
 * KVIC / MUDRA / Department of Commerce catalog with matching,
 * eligibility, and approval kept as separate concepts.
 */
export default function SchemesPage() {
  return <SchemesView />;
}
