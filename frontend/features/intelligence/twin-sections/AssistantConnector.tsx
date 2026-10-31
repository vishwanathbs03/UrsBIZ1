"use client";

/**
 * Section 10 — Connect to AI Assistant.
 * Five contextual deep-links that open the existing
 * `/assistant` route with a pre-filled question. We do not
 * create a second chatbot — these are routing anchors into
 * the existing assistant.
 *
 * The five links:
 *   1. Explain my Health Score           → current score + level
 *   2. Create a 30-day action plan       → top recommendation
 *   3. How can I improve my weakest area? → lowest analyzer
 *   4. Which government scheme should I explore? → top scheme
 *   5. What is my biggest risk?          → top risk
 */

import React from "react";
import Link from "next/link";
import type {
  IntelligenceResponse,
  IntelligenceAnalyzer,
} from "@/types/dashboard";
import type { TwinResponse, TwinRiskEntry } from "@/types/analytics";
import type { BusinessSchemesResponse } from "@/services/schemes-service";

interface AssistantConnectorProps {
  twin?: TwinResponse | null;
  intelligence?: IntelligenceResponse | null;
  schemes?: BusinessSchemesResponse | null;
}

function buildHref(question: string): string {
  return `/assistant?prompt=${encodeURIComponent(question)}`;
}

function pickWeakest(analyzers: IntelligenceAnalyzer[] | undefined): IntelligenceAnalyzer | null {
  if (!analyzers || analyzers.length === 0) return null;
  return [...analyzers].sort((a, b) => a.score - b.score)[0] || null;
}

function pickTopScheme(s: BusinessSchemesResponse | null | undefined): string | null {
  if (!s?.schemes) return null;
  const list = [
    ...(s.schemes.recommended || []),
    ...(s.schemes.eligible || []),
    ...(s.schemes.partially_eligible || []),
  ];
  const top = [...list]
    .filter((x) => x.eligibility_status === "matching" || x.eligibility_status === "partialMatch")
    .sort((a, b) => (b.matching_score || 0) - (a.matching_score || 0))[0];
  return top ? top.name : list[0]?.name || null;
}

function pickTopRisk(m: TwinResponse | null | undefined): TwinRiskEntry | null {
  if (!m) return null;
  const all: TwinRiskEntry[] = [
    ...(m.risk_matrix?.critical_risks || []),
    ...(m.risk_matrix?.high_risks || []),
    ...(m.risk_matrix?.medium_risks || []),
  ];
  return all[0] || null;
}

interface Action {
  id: string;
  label: string;
  question: string;
  ariaLabel?: string;
}

export const AssistantConnector: React.FC<AssistantConnectorProps> = ({
  twin,
  intelligence,
  schemes,
}) => {
  const weakest = pickWeakest(intelligence?.analyzers);
  const topScheme = pickTopScheme(schemes);
  const topRisk = pickTopRisk(twin);
  const overallScore = intelligence?.overall?.score;

  const actions: Action[] = [
    {
      id: "explain-health",
      label: "Explain my Health Score",
      question:
        overallScore != null
          ? `Walk me through my health score of ${overallScore}/100 — what's driving it and what should I focus on?`
          : "Walk me through my health score — what's driving it and what should I focus on?",
      ariaLabel: "Ask the AI assistant to explain my Health Score",
    },
    {
      id: "thirty-day-plan",
      label: "Create a 30-day action plan",
      question: "Create a 30-day action plan for me based on my current priorities.",
      ariaLabel: "Ask the AI assistant to create a 30-day action plan",
    },
    {
      id: "improve-weakest",
      label: "How can I improve my weakest area?",
      question: weakest
        ? `My weakest area is ${weakest.title.toLowerCase()} at ${weakest.score}/100. How can I improve it?`
        : "How can I improve my weakest area?",
      ariaLabel: "Ask the AI assistant how to improve my weakest area",
    },
    {
      id: "explore-scheme",
      label: "Which government scheme should I explore?",
      question: topScheme
        ? `Tell me more about ${topScheme} — am I eligible and what documents do I need?`
        : "Which government scheme should I explore for my business?",
      ariaLabel: "Ask the AI assistant which government scheme I should explore",
    },
    {
      id: "biggest-risk",
      label: "What is my biggest risk?",
      question: topRisk
        ? `My top risk is ${topRisk.title.toLowerCase()}. How should I mitigate it?`
        : "What is my biggest risk and how should I mitigate it?",
      ariaLabel: "Ask the AI assistant what my biggest risk is",
    },
  ];

  return (
    <section
      aria-labelledby="twin-section-assistant"
      data-testid="twin-section-assistant"
      className="rounded-xl border border-border bg-card p-5 shadow-sm sm:p-6"
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Section 10
          </span>
          <h2 id="twin-section-assistant" className="mt-0.5 text-lg font-bold text-card-foreground sm:text-xl">
            Connect to AI Assistant
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            One-click handoff into your existing assistant — no second chatbot.
          </p>
        </div>
        <Link
          href="/assistant"
          className="shrink-0 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-all hover:bg-muted"
        >
          Open assistant →
        </Link>
      </header>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {actions.map((a) => (
          <li key={a.id}>
            <Link
              href={buildHref(a.question)}
              data-testid={`twin-action-${a.id}`}
              aria-label={a.ariaLabel || a.label}
              className="flex h-full items-start gap-2 rounded-lg border border-border bg-muted/20 px-3 py-2.5 text-sm font-medium text-card-foreground transition-all hover:border-primary/40 hover:bg-primary/5"
            >
              <span aria-hidden="true" className="mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full bg-primary" />
              <span>{a.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
};
