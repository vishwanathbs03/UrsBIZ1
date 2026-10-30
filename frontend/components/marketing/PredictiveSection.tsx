"use client";

import { ArrowUpRight, Sparkles, TrendingUp } from "lucide-react";
import { useLanguage } from "@/context/language-context";

export function PredictiveSection() {
  const { t } = useLanguage();

  return (
    <section className="py-20 md:py-28 bg-muted/20 border-t border-border/80">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
            <TrendingUp className="size-3.5" />
            <span>{t("landing.predictive.badge")}</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {t("landing.predictive.title")}
          </h2>

          <p className="text-base sm:text-lg text-muted-foreground leading-relaxed">
            {t("landing.predictive.subtitle")}
          </p>
        </div>

        {/* Predictive Showcase Card */}
        <div className="mt-14 max-w-4xl mx-auto rounded-3xl border border-border/80 bg-card p-6 sm:p-8 shadow-card space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 border-b border-border/60 pb-8">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {t("landing.predictive.currentLabel")}
              </span>
              <div className="text-3xl font-black text-foreground">{t("landing.predictive.currentValue")}</div>
              <span className="text-[11px] text-muted-foreground">Baseline Active Run-Rate</span>
            </div>

            <div className="space-y-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {t("landing.predictive.projectedLabel")}
              </span>
              <div className="text-3xl font-black text-primary">{t("landing.predictive.projectedValue")}</div>
              <span className="text-[11px] text-primary font-medium">Target with Optimized DSO</span>
            </div>

            <div className="space-y-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {t("landing.predictive.growthLabel")}
              </span>
              <div className="text-3xl font-black text-emerald-600 dark:text-emerald-400 flex items-center">
                {t("landing.predictive.growthValue")}
                <ArrowUpRight className="size-6" />
              </div>
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">Model Confidence: 92%</span>
            </div>
          </div>

          {/* Forward Scenario Simulation Box */}
          <div className="rounded-2xl border border-border/80 bg-background/50 p-5 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-foreground">
              <Sparkles className="size-4 text-primary" />
              <span>{t("landing.predictive.scenarioTitle")}</span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {t("landing.predictive.scenarioDesc")}
            </p>
          </div>

          <div className="text-center text-xs text-muted-foreground/80 italic">
            * {t("landing.predictive.disclaimer")}
          </div>
        </div>
      </div>
    </section>
  );
}
