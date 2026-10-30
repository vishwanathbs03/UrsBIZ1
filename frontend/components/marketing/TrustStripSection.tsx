"use client";

import { CheckCircle2 } from "lucide-react";
import { useLanguage } from "@/context/language-context";

export function TrustStripSection() {
  const { t } = useLanguage();

  const items = [
    t("landing.trustStrip.item1"),
    t("landing.trustStrip.item2"),
    t("landing.trustStrip.item3"),
    t("landing.trustStrip.item4"),
    t("landing.trustStrip.item5"),
  ];

  return (
    <section className="border-b border-border/80 bg-muted/30 py-5">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">
            {t("landing.trustStrip.title")}
          </span>

          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs font-semibold text-foreground">
            {items.map((item) => (
              <span key={item} className="inline-flex items-center gap-1.5">
                <CheckCircle2 className="size-3.5 text-primary shrink-0" aria-hidden="true" />
                <span>{item}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
