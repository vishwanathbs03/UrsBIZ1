"use client";

import { CheckCircle2, Compass, Layers, Sparkles } from "lucide-react";
import { useLanguage } from "@/context/language-context";

export function HowItWorksSection() {
  const { t } = useLanguage();

  const steps = [
    {
      num: t("landing.howItWorks.step1Num"),
      title: t("landing.howItWorks.step1Title"),
      desc: t("landing.howItWorks.step1Desc"),
      icon: Compass,
    },
    {
      num: t("landing.howItWorks.step2Num"),
      title: t("landing.howItWorks.step2Title"),
      desc: t("landing.howItWorks.step2Desc"),
      icon: Sparkles,
    },
    {
      num: t("landing.howItWorks.step3Num"),
      title: t("landing.howItWorks.step3Title"),
      desc: t("landing.howItWorks.step3Desc"),
      icon: Layers,
    },
  ];

  return (
    <section className="py-20 md:py-28 bg-background border-t border-border/80">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-primary">
            <CheckCircle2 className="size-3.5" />
            <span>{t("landing.howItWorks.badge")}</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {t("landing.howItWorks.title")}
          </h2>

          <p className="text-base sm:text-lg text-muted-foreground leading-relaxed">
            {t("landing.howItWorks.subtitle")}
          </p>
        </div>

        {/* 3 Horizontal Steps on Desktop, Vertical on Mobile */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 relative">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div
                key={step.num}
                className="relative rounded-2xl border border-border/80 bg-card p-8 shadow-xs flex flex-col justify-between space-y-4"
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-3xl font-black text-primary">
                      {step.num}
                    </span>
                    <div className="size-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                      <Icon className="size-5" />
                    </div>
                  </div>

                  <h3 className="text-xl font-bold text-foreground tracking-tight">
                    {step.title}
                  </h3>

                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {step.desc}
                  </p>
                </div>

                <div className="pt-2 text-xs font-semibold text-primary">
                  Step {idx + 1} of 3
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
