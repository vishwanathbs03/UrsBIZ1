"use client";

import Link from "next/link";
import { CheckCircle2, KanbanSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/language-context";

export function ActionBoardSection() {
  const { t } = useLanguage();

  const actions = [
    {
      title: t("landing.actionBoard.a1Title"),
      priority: t("landing.actionBoard.a1Priority"),
      impact: t("landing.actionBoard.a1Impact"),
      priorityTone: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30",
    },
    {
      title: t("landing.actionBoard.a2Title"),
      priority: t("landing.actionBoard.a2Priority"),
      impact: t("landing.actionBoard.a2Impact"),
      priorityTone: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30",
    },
    {
      title: t("landing.actionBoard.a3Title"),
      priority: t("landing.actionBoard.a3Priority"),
      impact: t("landing.actionBoard.a3Impact"),
      priorityTone: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30",
    },
  ];

  return (
    <section className="py-20 md:py-28 bg-muted/20 border-t border-border/80">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
            <KanbanSquare className="size-3.5" />
            <span>{t("landing.actionBoard.badge")}</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {t("landing.actionBoard.title")}
          </h2>

          <p className="text-base sm:text-lg text-muted-foreground leading-relaxed">
            {t("landing.actionBoard.subtitle")}
          </p>
        </div>

        {/* 3 Action Cards */}
        <div className="mt-14 max-w-4xl mx-auto space-y-3.5">
          {actions.map((act) => (
            <div
              key={act.title}
              className="rounded-2xl border border-border/80 bg-card p-5 sm:p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all hover:border-primary/40 hover:shadow-soft"
            >
              <div className="flex items-start sm:items-center gap-3.5">
                <div className="size-8 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 font-bold">
                  <CheckCircle2 className="size-4.5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-foreground">{act.title}</h3>
                  <p className="text-xs font-medium text-muted-foreground pt-0.5">{act.impact}</p>
                </div>
              </div>

              <div className="flex items-center gap-3 self-end sm:self-center">
                <span className={`rounded-md border px-2.5 py-1 text-xs font-bold ${act.priorityTone}`}>
                  {act.priority}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center">
          <Button asChild size="lg" variant="outline" className="h-12 px-8 text-base font-bold rounded-xl border-border">
            <Link href="/action-board">
              {t("landing.actionBoard.cta")}
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
