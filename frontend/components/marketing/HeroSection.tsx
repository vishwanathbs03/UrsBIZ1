"use client";

import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  ChevronRight,
  Landmark,
  Layers,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { UrsBizIcon } from "@/components/common/Logo";
import { useLanguage } from "@/context/language-context";

export function HeroSection() {
  const { t } = useLanguage();

  return (
    <section
      aria-labelledby="hero-title"
      className="relative overflow-hidden bg-gradient-to-b from-[#0A192F] via-[#0F172A] to-[#0A192F] text-slate-100 pt-12 pb-20 md:pt-20 md:pb-28 border-b border-slate-800"
    >
      {/* Background ambient lighting */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-48 left-1/2 -translate-x-1/2 size-[650px] rounded-full bg-blue-600/15 blur-[140px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/3 right-10 size-[400px] rounded-full bg-cyan-500/10 blur-[120px]"
      />

      <div className="container relative z-10 mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-12 lg:items-center">
          {/* Left Column: Focused Executive Copy */}
          <div className="flex flex-col items-start text-left lg:col-span-6 xl:col-span-7">
            {/* Eyebrow badge */}
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-500/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-sky-300 backdrop-blur-md">
              <Sparkles className="size-3.5 text-sky-400 animate-pulse" aria-hidden="true" />
              <span>{t("landing.hero.eyebrow")}</span>
            </div>

            {/* Main Headline */}
            <h1
              id="hero-title"
              className="text-balance text-4xl font-black tracking-tight text-white sm:text-5xl md:text-6xl lg:text-[62px] lg:leading-[1.1]"
            >
              {t("landing.hero.headlineStart")}
              <span className="bg-gradient-to-r from-sky-400 via-blue-400 to-cyan-300 bg-clip-text text-transparent">
                {t("landing.hero.headlineHighlight")}
              </span>
              {t("landing.hero.headlineEnd")}
            </h1>

            {/* Subheadline */}
            <p className="mt-6 max-w-2xl text-balance text-base text-slate-300 sm:text-lg md:text-xl leading-relaxed">
              {t("landing.hero.subheadline")}
            </p>

            {/* Max 3 Clean Capability Pills */}
            <div className="mt-6 flex flex-wrap gap-2 sm:gap-2.5">
              {[
                { label: t("landing.hero.badge1"), icon: Sparkles },
                { label: t("landing.hero.badge2"), icon: TrendingUp },
                { label: t("landing.hero.badge3"), icon: BarChart3 },
              ].map((pill) => {
                const Icon = pill.icon;
                return (
                  <span
                    key={pill.label}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700/80 bg-slate-800/60 px-3 py-1 text-xs font-medium text-slate-300 backdrop-blur-sm shadow-xs"
                  >
                    <Icon className="size-3.5 text-sky-400" aria-hidden="true" />
                    {pill.label}
                  </span>
                );
              })}
            </div>

            {/* Primary & Secondary CTAs */}
            <div className="mt-8 flex flex-col sm:flex-row items-stretch sm:items-center gap-4 w-full sm:w-auto">
              <Button
                asChild
                size="lg"
                className="h-12 px-8 text-base font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30 border border-blue-400/30 rounded-xl"
              >
                <Link href="/register">
                  {t("landing.hero.ctaPrimary")}
                  <ArrowRight className="ml-2 size-4" aria-hidden="true" />
                </Link>
              </Button>

              <Button
                asChild
                size="lg"
                variant="outline"
                className="h-12 px-6 text-base font-semibold border-slate-700 bg-slate-900/60 hover:bg-slate-800 text-slate-200 hover:text-white rounded-xl backdrop-blur-sm"
              >
                <a href="#platform-overview">
                  {t("landing.hero.ctaSecondary")}
                  <ChevronRight className="ml-1 size-4 text-slate-400" aria-hidden="true" />
                </a>
              </Button>
            </div>
          </div>

          {/* Right Column: Premium "UrsBiz Intelligence Console" Preview */}
          <div className="lg:col-span-6 xl:col-span-5">
            <div className="relative rounded-2xl border border-slate-700/90 bg-[#0F172A]/90 p-5 sm:p-6 shadow-2xl shadow-blue-950/60 backdrop-blur-xl transition-all hover:border-slate-600">
              {/* Header Bar */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div className="flex items-center gap-2.5">
                  <UrsBizIcon size={24} variant="app-icon" />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-white tracking-wide">URSBiz Intelligence Console</span>
                    </div>
                    <p className="text-[10px] font-semibold text-emerald-400 flex items-center gap-1">
                      <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      {t("landing.console.liveTwin")}
                    </p>
                  </div>
                </div>
                <span className="rounded-md border border-slate-700 bg-slate-800/80 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                  v2.0 Active
                </span>
              </div>

              {/* Console Metrics Grid */}
              <div className="mt-4 grid grid-cols-2 gap-3">
                {/* Health Score Tile */}
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-slate-400">{t("landing.console.healthTitle")}</span>
                    <Sparkles className="size-3.5 text-blue-400" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-1.5">
                    <span className="text-2xl font-black text-white">{t("landing.console.healthScore")}</span>
                    <span className="text-xs text-slate-400">/ 100</span>
                    <span className="ml-auto rounded-md bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400">
                      {t("landing.console.healthBand")}
                    </span>
                  </div>
                </div>

                {/* Projected Trajectory */}
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-slate-400">{t("landing.console.revenueTrajectory")}</span>
                    <TrendingUp className="size-3.5 text-emerald-400" />
                  </div>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="text-xl font-bold text-emerald-400">{t("landing.console.revenueValue")}</span>
                    <span className="text-[10px] text-slate-400">Deterministic</span>
                  </div>
                </div>
              </div>

              {/* Key Opportunity & Action Row */}
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between rounded-xl border border-slate-800/90 bg-slate-900/60 p-2.5 text-xs">
                  <div className="flex items-center gap-2">
                    <Landmark className="size-3.5 text-cyan-400 shrink-0" />
                    <span className="text-slate-400 font-medium">{t("landing.console.topOpportunity")}:</span>
                  </div>
                  <span className="font-semibold text-cyan-300">{t("landing.console.topOpportunityValue")}</span>
                </div>

                <div className="flex items-center justify-between rounded-xl border border-slate-800/90 bg-slate-900/60 p-2.5 text-xs">
                  <div className="flex items-center gap-2">
                    <Layers className="size-3.5 text-sky-400 shrink-0" />
                    <span className="text-slate-400 font-medium">{t("landing.console.priorityAction")}:</span>
                  </div>
                  <span className="font-semibold text-slate-200">{t("landing.console.priorityActionValue")}</span>
                </div>
              </div>

              {/* AI Copilot Grounded Insight Box */}
              <div className="mt-3 rounded-xl border border-blue-500/30 bg-blue-950/40 p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-sky-300">
                    <Sparkles className="size-3 text-sky-400" />
                    <span>{t("landing.console.aiInsightTitle")}</span>
                  </div>
                  <span className="text-[10px] font-mono text-cyan-400">{t("landing.console.confidence")}</span>
                </div>
                <p className="text-xs text-slate-200 leading-relaxed font-sans">
                  &ldquo;{t("landing.console.aiInsightBody")}&rdquo;
                </p>
                <div className="pt-1 flex items-center justify-between text-[10px] text-slate-400 border-t border-blue-900/50">
                  <span className="font-mono">{t("landing.console.evidenceVerified")}</span>
                  <span className="text-sky-400 font-semibold flex items-center gap-0.5">
                    <ShieldCheck className="size-3" /> Grounded
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
