"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, Bot, Sparkles, ShieldCheck, Languages } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DashboardAssistantSpotlightProps {
  businessName?: string;
}

const SUGGESTED_PROMPTS = [
  "What is my biggest operational risk and how do I fix it?",
  "Which MSME government subsidies can I apply for right now?",
  "Explain my health score and show the mathematical lineage.",
  "ಉದ್ಯಮದ ಬೆಳವಣಿಗೆಗೆ ಯಾವ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು ಲಭ್ಯವಿದೆ?", // Kannada question
];

/**
 * Section 9: AI Assistant Entry Point (Phase 1 Dark Neon).
 * Invites the user into the grounded AI Copilot with quick-start queries.
 */
export function DashboardAssistantSpotlight({
  businessName = "your business",
}: DashboardAssistantSpotlightProps) {
  return (
    <section
      aria-label="AI Business Assistant Spotlight"
      className="relative overflow-hidden rounded-2xl border border-primary/40 bg-gradient-to-r from-card via-card to-primary/10 p-6 shadow-[0_0_30px_-5px_rgba(37,99,235,0.2)] backdrop-blur-xl md:p-8"
    >
      {/* Top subtle neon glow line */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-cyan-400 to-indigo-500"
      />

      <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        {/* Left side: Assistant Info */}
        <div className="max-w-2xl space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/20 px-3 py-0.5 text-xs font-bold uppercase tracking-wider text-accent shadow-[0_0_10px_rgba(59,130,246,0.3)]">
              <Sparkles className="size-3.5 animate-pulse text-accent" aria-hidden="true" />
              Grounded AI Copilot
            </span>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400">
              <ShieldCheck className="size-3.5" aria-hidden="true" /> Zero Hallucinations
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Languages className="size-3.5 text-cyan-400" aria-hidden="true" /> English & Kannada
              Native
            </span>
          </div>

          <h2 className="text-xl font-extrabold tracking-tight text-foreground sm:text-2xl lg:text-3xl">
            Ask Your Strategic{" "}
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              AI Decision Partner
            </span>
          </h2>

          <p className="text-sm leading-relaxed text-muted-foreground">
            Unlike generic chatbots, UrsBiz answers strategic questions directly grounded in{" "}
            {businessName}&apos;s verified balance sheet, operational metrics, and gazetted MSME
            ministry policies.
          </p>

          {/* Suggested Quick Question Pills */}
          <div className="pt-2">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground/80">
              Try asking:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_PROMPTS.map((q) => (
                <Link
                  key={q}
                  href={`/assistant?prompt=${encodeURIComponent(q)}`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border/80 bg-secondary/70 px-3 py-1.5 text-xs text-muted-foreground transition-all duration-200 hover:border-primary/50 hover:bg-card hover:text-foreground"
                >
                  <span className="max-w-[260px] truncate sm:max-w-none">{q}</span>
                  <ArrowRight className="size-3 shrink-0 text-accent" aria-hidden="true" />
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Right side: Launch CTA Button */}
        <div className="flex shrink-0 flex-col items-start justify-center lg:items-end">
          <Button asChild size="lg" variant="neon" className="gap-2 px-6 py-6 text-base">
            <Link href="/assistant">
              <Bot className="size-5" aria-hidden="true" />
              <span>Launch AI Copilot</span>
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
          <span className="mt-2 text-[11px] text-muted-foreground">
            Sub-second response • Immutable audit trail
          </span>
        </div>
      </div>
    </section>
  );
}
