/**
 * AnalysisScreen — full-page "Analyzing your business…" view.
 *
 * Drives the demo runner on mount, tracks which stage is active,
 * then routes the user to the dashboard when the run finishes.
 *
 * Reads the business name from the cached BusinessWithCompleteness
 * payload via useBusinessQuery. If the cache is empty, it falls
 * back to a generic greeting.
 *
 * The page is intentionally stateless about how the run happens
 * — the runner handles the work; this component only reflects
 * state. Replacing the runner body with a real provider later
 * is a drop-in change.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/services/api-client";
import { useBusinessQuery } from "@/features/business/use-business-data";
import { AnalysisProgress } from "./AnalysisProgress";
import { runAnalysis } from "./use-analysis-runner";
import type { AnalysisStatus } from "./types";

export function AnalysisScreen() {
  const router = useRouter();
  const { data } = useBusinessQuery();
  const businessName = data?.business.legal_name ?? "your business";

  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [percent, setPercent] = useState(0);
  const [status, setStatus] = useState<AnalysisStatus>("running");
  const startedRef = useRef(false);
  const completedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    const ac = new AbortController();
    const handle = runAnalysis({ signal: ac.signal });
    let cancelled = false;

    (async () => {
      try {
        for await (const tick of handle) {
          if (cancelled) return;
          setActiveIndex(tick.completedIndex);
          setPercent(tick.percent);
          setStatus(tick.status);
        }
        // Mark every stage complete + 100% once the iterator ends.
        if (!cancelled) {
          setActiveIndex(5);
          setPercent(100);
          setStatus("complete");
          if (!completedRef.current) {
            completedRef.current = true;
            setTimeout(() => router.push("/dashboard"), 900);
          }
        }
      } catch {
        if (!cancelled) setStatus("failed");
      }
    })();

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [router]);

  return (
    <PageContainer width="default">
      <DashboardCard
        badge="AI Analysis"
        title="Running UrsBiz intelligence"
        caption="Six stages. One comprehensive read on your business."
        trailing={
          status === "complete" ? (
            <Button size="sm" onClick={() => router.push("/dashboard")}>
              Open dashboard
            </Button>
          ) : null
        }
      >
        <AnalysisProgress
          businessName={businessName}
          activeIndex={activeIndex}
          percent={percent}
          status={status}
        />
      </DashboardCard>
    </PageContainer>
  );
}
