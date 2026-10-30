"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/language-context";

export function FinalCtaSection() {
  const { t } = useLanguage();

  return (
    <section className="py-24 md:py-32 bg-gradient-to-b from-[#0F172A] to-[#0A192F] text-slate-100 border-t border-slate-800 relative overflow-hidden text-center">
      {/* Glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 size-[600px] rounded-full bg-blue-600/15 blur-[140px]"
      />

      <div className="container relative z-10 mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl space-y-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-500/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-sky-300">
          <Sparkles className="size-3.5 text-sky-400" />
          <span>URSBiz Enterprise SaaS</span>
        </div>

        <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl md:text-5xl lg:text-6xl text-balance leading-tight">
          {t("landing.finalCta.title")}
        </h2>

        <p className="max-w-2xl mx-auto text-base sm:text-lg text-slate-300 leading-relaxed text-balance">
          {t("landing.finalCta.subtitle")}
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          <Button
            asChild
            size="lg"
            className="h-13 px-8 text-base font-bold bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-lg shadow-blue-600/30 border border-blue-400/30 w-full sm:w-auto"
          >
            <Link href="/register">
              {t("landing.finalCta.ctaPrimary")}
            </Link>
          </Button>

          <Button
            asChild
            size="lg"
            variant="outline"
            className="h-13 px-7 text-base font-semibold border-slate-700 bg-slate-900/60 hover:bg-slate-800 text-slate-200 hover:text-white rounded-xl w-full sm:w-auto backdrop-blur-sm"
          >
            <Link href="/assistant">
              {t("landing.finalCta.ctaSecondary")}
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
