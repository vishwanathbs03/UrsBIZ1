"use client";

import { ReportSection } from "../ReportSection";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import {
  confidenceToTone,
  levelToTone,
  scoreTone,
} from "@/features/dashboard/tones";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import type { ReportSectionMeta } from "../sections";
import type { ReportsData } from "../use-reports-data";

const META: ReportSectionMeta = {
  key: "business-dna",
  id: "report-business-dna",
  badge: "DNA",
  title: "Business DNA",
  caption: "Archetype, secondary traits, and SWOT quadrants.",
};

interface BusinessDnaSectionProps {
  data: ReportsData;
}

const QUADS = [
  { key: "strengths", title: "Strengths", tone: "text-emerald-700" },
  { key: "weaknesses", title: "Weaknesses", tone: "text-rose-700" },
  { key: "opportunities", title: "Opportunities", tone: "text-sky-700" },
  { key: "risks", title: "Risk areas", tone: "text-amber-700" },
] as const;

/**
 * Business DNA — the archetype headline, secondary trait
 * chips, confidence badge, and a 2x2 SWOT grid. All values
 * come straight from the DNA engine payload.
 */
export function BusinessDnaSection({ data }: BusinessDnaSectionProps) {
  const body = data.dna.dna;
  const archetype = body.archetype;
  const traits = body.secondary_traits;
  const conf = confidenceToTone(body.confidence);
  const present = traits.filter((t) => t.present);
  const swot: Record<(typeof QUADS)[number]["key"], typeof body.strengths> = {
    strengths: body.strengths,
    weaknesses: body.weaknesses,
    opportunities: body.opportunities,
    risks: body.risk_areas,
  };

  return (
    <ReportSection meta={META}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-secondary/30 p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Archetype
          </p>
          <div className="flex items-center justify-between gap-2">
            <span className="text-base font-semibold text-foreground">
              {archetype.title}
            </span>
            <span
              className={`inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${conf.tone}`}
              aria-label={`DNA confidence: ${conf.label} (${Math.round(body.confidence)}%)`}
              role="status"
            >
              <AnimatedCounter
                value={Math.round(body.confidence)}
                suffix="%"
                className="normal-case tracking-normal"
                durationMs={500}
              />
              {conf.label}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Match</span>
            <span className="font-mono">{archetype.key}</span>
            <LevelBadge
              level={`${archetype.match_score}`}
              tone={levelToTone(
                archetype.match_score >= 70
                  ? "high"
                  : archetype.match_score >= 40
                    ? "medium"
                    : "low",
              )}
            />
          </div>
          {archetype.description && (
            <p className="text-xs leading-snug text-muted-foreground">
              {archetype.description}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-2 rounded-lg border border-border bg-secondary/30 p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Secondary traits ({present.length}/{traits.length})
          </p>
          {present.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No secondary traits detected — the profile is in the
              catch-all Foundation Builder state.
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {present.map((t) => (
                <li
                  key={t.key}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground"
                >
                  <span className={`size-1.5 rounded-full ${scoreTone("High")}`} />
                  {t.title}
                  <span className="text-muted-foreground">{t.strength}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {QUADS.map((q) => {
          const items = swot[q.key];
          return (
            <div
              key={q.key}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3"
            >
              <p className={`text-[10px] font-semibold uppercase tracking-wider ${q.tone}`}>
                {q.title} <span className="text-muted-foreground">({items.length})</span>
              </p>
              {items.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No findings.
                </p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {items.slice(0, 6).map((it, idx) => (
                    <li
                      key={`${q.key}-${it.id ?? idx}-${idx}`}
                      className="flex items-start justify-between gap-2 rounded-md border border-border bg-secondary/30 px-2 py-1.5 text-xs"
                    >
                      <span className="font-medium text-foreground leading-snug">
                        {it.title}
                      </span>
                      <LevelBadge
                        level={it.severity}
                        tone={levelToTone(it.severity === "high" ? "low" : it.severity === "medium" ? "medium" : "high")}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </ReportSection>
  );
}
