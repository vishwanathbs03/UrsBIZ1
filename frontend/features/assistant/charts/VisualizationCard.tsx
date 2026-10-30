/**
 * SPRINT AI-15 — VisualizationCard. The orchestrator wrapper.
 *
 * Takes a `VisualizationPlan` payload (from `message.visualization_plans`)
 * and routes to the matching hand-rolled chart component.
 *
 * Empty payloads surface as the "Not enough business data" notice —
 * the brief is explicit that we NEVER render an empty chart.
 */

import React from "react";
import type {
  VisualizationPlan,
  TrustSummary,
} from "@/features/assistant/types";
import { KPICard } from "./KPICard";
import { ProgressCard } from "./ProgressCard";
import {
  ComparisonTable,
  type ComparisonRow,
} from "./ComparisonTable";
import { TrendSparkline, type TrendPoint } from "./TrendSparkline";
import { ScenarioStackedBar } from "./ScenarioStackedBar";
import { RiskBar, type RiskBarProps } from "./RiskBar";
import { CompositionDonut, type CompositionSlice } from "./CompositionDonut";
import { ReadinessRadar, type ReadinessAxis } from "./ReadinessRadar";

export interface VisualizationCardProps {
  plan: VisualizationPlan;
  trust_summary?: TrustSummary | null;
}

export function VisualizationCard(
  props: VisualizationCardProps
): React.JSX.Element | null {
  const { plan } = props;
  if (plan.empty_reason) {
    return (
      <div
        className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
        data-testid="viz-empty"
      >
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">{plan.empty_reason}</div>
        {plan.missing_fields && plan.missing_fields.length > 0 && (
          <div className="mt-1 text-xs opacity-75">
            Missing: {plan.missing_fields.join(", ")}
          </div>
        )}
      </div>
    );
  }
  const data = (plan.data ?? {}) as Record<string, unknown>;
  switch (plan.chart_kind) {
    case "kpi":
      return (
        <KPICard
          title={plan.title}
          value={(data.value as number | string) ?? ""}
          unit={(data.unit as string | undefined)}
          delta={data.delta as number | undefined}
          trend={data.trend as number[] | undefined}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    case "progress":
      return (
        <ProgressCard
          title={plan.title}
          current={(data.current as number) ?? 0}
          target={(data.target as number) ?? 0}
          unit={(data.unit as string | undefined)}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    case "comparison":
      return (
        <ComparisonTable
          title={plan.title}
          left_label={(data.left_label as string) ?? "Option A"}
          right_label={(data.right_label as string) ?? "Option B"}
          rows={(data.rows as ComparisonRow[]) ?? []}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    case "trend":
      return (
        <TrendSparkline
          title={plan.title}
          points={(data.points as TrendPoint[]) ?? []}
          unit={(data.unit as string | undefined)}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    case "scenario":
      return (
        <ScenarioStackedBar
          title={plan.title}
          baseline={(data.baseline as number) ?? 0}
          changed_input={(data.changed_input as string) ?? "Updated inputs"}
          estimated_effect={(data.estimated_effect as number) ?? 0}
          unit={(data.unit as string | undefined)}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
          assumptions={plan.assumptions}
        />
      );
    case "risk":
      return (
        <RiskBar
          title={plan.title}
          segments={
            (data.segments as RiskBarProps["segments"]) ?? []
          }
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    case "composition":
      return (
        <CompositionDonut
          title={plan.title}
          slices={(data.slices as CompositionSlice[]) ?? []}
          unit={(data.unit as string | undefined)}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    case "readiness":
      return (
        <ReadinessRadar
          title={plan.title}
          axes={(data.axes as ReadinessAxis[]) ?? []}
          confidence={plan.confidence}
          source_evidence_ids={plan.source_evidence_ids}
        />
      );
    default:
      return null;
  }
}

export default VisualizationCard;
