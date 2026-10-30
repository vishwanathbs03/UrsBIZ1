"use client";

import {
  Activity,
  AlertTriangle,
  DollarSign,
  KanbanSquare,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useLanguage } from "@/context/language-context";

export function BiMetricsSection() {
  const { t } = useLanguage();

  const metrics = [
    {
      label: t("landing.biSection.healthLabel"),
      value: t("landing.biSection.healthValue"),
      caption: "Established Band",
      icon: Sparkles,
      tone: "text-blue-600 bg-blue-500/10 border-blue-500/20",
    },
    {
      label: t("landing.biSection.revenueLabel"),
      value: t("landing.biSection.revenueValue"),
      caption: "Verified Turnover",
      icon: DollarSign,
      tone: "text-emerald-600 bg-emerald-500/10 border-emerald-500/20",
    },
    {
      label: t("landing.biSection.growthLabel"),
      value: t("landing.biSection.growthValue"),
      caption: "Trajectory",
      icon: TrendingUp,
      tone: "text-cyan-600 bg-cyan-500/10 border-cyan-500/20",
    },
    {
      label: t("landing.biSection.actionsLabel"),
      value: t("landing.biSection.actionsValue"),
      caption: "Action Board",
      icon: KanbanSquare,
      tone: "text-amber-600 bg-amber-500/10 border-amber-500/20",
    },
    {
      label: t("landing.biSection.riskLabel"),
      value: t("landing.biSection.riskValue"),
      caption: "Single-Supplier Flag",
      icon: AlertTriangle,
      tone: "text-rose-600 bg-rose-500/10 border-rose-500/20",
    },
  ];

  return (
    <section className="py-20 md:py-24 bg-background">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
            <Activity className="size-3.5" />
            <span>{t("landing.biSection.badge")}</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {t("landing.biSection.title")}
          </h2>

          <p className="text-base sm:text-lg text-muted-foreground leading-relaxed">
            {t("landing.biSection.subtitle")}
          </p>
        </div>

        {/* 5 KPI Cards Grid */}
        <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {metrics.map((m) => {
            const Icon = m.icon;
            return (
              <div
                key={m.label}
                className="rounded-2xl border border-border/80 bg-card p-5 shadow-xs flex flex-col justify-between space-y-3 transition-all hover:border-primary/40 hover:shadow-soft"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {m.label}
                  </span>
                  <div className={`p-2 rounded-lg border ${m.tone}`}>
                    <Icon className="size-4" />
                  </div>
                </div>

                <div>
                  <div className="text-2xl sm:text-3xl font-black text-foreground tracking-tight">
                    {m.value}
                  </div>
                  <span className="text-[11px] font-medium text-muted-foreground">
                    {m.caption}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
