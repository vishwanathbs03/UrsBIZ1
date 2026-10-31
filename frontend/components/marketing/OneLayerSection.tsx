"use client";

import { Compass, Landmark, Layers, TrendingUp } from "lucide-react";
import { useLanguage } from "@/context/language-context";

export function OneLayerSection() {
  const { t } = useLanguage();

  const cards = [
    {
      num: t("landing.oneLayer.c1Number"),
      title: t("landing.oneLayer.c1Title"),
      desc: t("landing.oneLayer.c1Desc"),
      icon: Compass,
      tone: "text-blue-500 bg-blue-500/10 border-blue-500/20",
    },
    {
      num: t("landing.oneLayer.c2Number"),
      title: t("landing.oneLayer.c2Title"),
      desc: t("landing.oneLayer.c2Desc"),
      icon: Landmark,
      tone: "text-cyan-500 bg-cyan-500/10 border-cyan-500/20",
    },
    {
      num: t("landing.oneLayer.c3Number"),
      title: t("landing.oneLayer.c3Title"),
      desc: t("landing.oneLayer.c3Desc"),
      icon: TrendingUp,
      tone: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
    },
    {
      num: t("landing.oneLayer.c4Number"),
      title: t("landing.oneLayer.c4Title"),
      desc: t("landing.oneLayer.c4Desc"),
      icon: Layers,
      tone: "text-sky-500 bg-sky-500/10 border-sky-500/20",
    },
  ];

  return (
    <section id="platform-overview" className="py-20 md:py-28 bg-background">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="mx-auto max-w-3xl text-center space-y-4">
          <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
            {t("landing.oneLayer.title")}
          </h2>
          <p className="text-base sm:text-lg text-muted-foreground leading-relaxed">
            {t("landing.oneLayer.subtitle")}
          </p>
        </div>

        {/* 4 Editorial Cards Grid */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.num}
                className="group relative rounded-2xl border border-border/80 bg-card p-7 shadow-xs transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-soft flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between border-b border-border/50 pb-4">
                    <span className="font-mono text-3xl font-black text-muted-foreground/50 group-hover:text-primary transition-colors">
                      {card.num}
                    </span>
                    <div className={`p-2.5 rounded-xl border ${card.tone}`}>
                      <Icon className="size-5" aria-hidden="true" />
                    </div>
                  </div>

                  <h3 className="mt-6 text-xl font-bold tracking-tight text-foreground">
                    {card.title}
                  </h3>

                  <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                    {card.desc}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-border/40 text-[11px] font-bold uppercase tracking-wider text-primary">
                  URSBiz Core Engine
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
