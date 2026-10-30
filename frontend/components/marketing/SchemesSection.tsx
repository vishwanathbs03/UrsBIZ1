"use client";

import Link from "next/link";
import { ChevronRight, Landmark, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/language-context";

export function SchemesSection() {
  const { t } = useLanguage();

  const schemes = [
    {
      title: t("landing.schemes.s1Title"),
      match: t("landing.schemes.s1Match"),
      benefit: t("landing.schemes.s1Subsidy"),
      desc: t("landing.schemes.s1Desc"),
      badgeTone: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
    },
    {
      title: t("landing.schemes.s2Title"),
      match: t("landing.schemes.s2Match"),
      benefit: t("landing.schemes.s2Benefit"),
      desc: t("landing.schemes.s2Desc"),
      badgeTone: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
    },
    {
      title: t("landing.schemes.s3Title"),
      match: t("landing.schemes.s3Match"),
      benefit: t("landing.schemes.s3Benefit"),
      desc: t("landing.schemes.s3Desc"),
      badgeTone: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/30",
    },
  ];

  return (
    <section className="py-20 md:py-28 bg-background border-t border-border/80">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-cyan-600 dark:text-cyan-400">
            <Landmark className="size-3.5" />
            <span>{t("landing.schemes.badge")}</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {t("landing.schemes.title")}
          </h2>

          <p className="text-base sm:text-lg text-muted-foreground leading-relaxed">
            {t("landing.schemes.subtitle")}
          </p>
        </div>

        {/* Schemes 3-Card Grid */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-6">
          {schemes.map((s) => (
            <div
              key={s.title}
              className="rounded-2xl border border-border/80 bg-card p-6 shadow-xs flex flex-col justify-between space-y-5 transition-all hover:border-primary/40 hover:shadow-soft"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold ${s.badgeTone}`}>
                    <Sparkles className="size-3" />
                    {s.match}
                  </span>
                  <span className="text-[11px] font-bold text-muted-foreground">Active Scheme</span>
                </div>

                <h3 className="text-lg font-bold text-foreground tracking-tight">
                  {s.title}
                </h3>

                <div className="rounded-xl bg-muted/40 p-2.5 text-xs font-semibold text-foreground">
                  {s.benefit}
                </div>

                <p className="text-xs text-muted-foreground leading-relaxed">
                  {s.desc}
                </p>
              </div>

              <div className="pt-3 border-t border-border/40 flex items-center justify-between text-xs font-semibold text-primary">
                <span>Auto-Matched by Digital Twin</span>
                <ChevronRight className="size-4" />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center">
          <Button asChild size="lg" className="h-12 px-8 text-base font-bold rounded-xl">
            <Link href="/schemes">
              {t("landing.schemes.cta")}
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
