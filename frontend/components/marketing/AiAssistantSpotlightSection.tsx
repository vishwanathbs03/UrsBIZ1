"use client";

import Link from "next/link";
import {
  CheckCircle2,
  FileSearch,
  Lightbulb,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { UrsBizIcon } from "@/components/common/Logo";
import { useLanguage } from "@/context/language-context";

export function AiAssistantSpotlightSection() {
  const { t } = useLanguage();

  return (
    <section className="py-20 md:py-28 bg-[#0A192F] text-slate-100 border-y border-slate-800 relative overflow-hidden">
      {/* Ambient background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-1/4 -translate-y-1/2 size-[500px] rounded-full bg-blue-600/10 blur-[130px]"
      />

      <div className="container relative z-10 mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-12 lg:items-center">
          {/* Left Column: Narrative & Trust Concept */}
          <div className="lg:col-span-5 space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-500/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-sky-300 backdrop-blur">
              <Sparkles className="size-3.5 text-sky-400" />
              <span>{t("landing.aiSection.badge")}</span>
            </div>

            <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl md:text-5xl">
              {t("landing.aiSection.title")}
            </h2>

            <p className="text-base sm:text-lg text-slate-300 leading-relaxed">
              {t("landing.aiSection.subtitle")}
            </p>

            {/* Architecture Flow Breakdown */}
            <div className="space-y-3 pt-2">
              {[
                "1. Verified Business Twin Data as the only grounding source",
                "2. Deterministic rule-engine checks for financial invariants",
                "3. Zero hallucinations — answers cite exact Evidence IDs",
              ].map((point) => (
                <div key={point} className="flex items-start gap-2.5 text-xs text-slate-300">
                  <CheckCircle2 className="size-4 text-cyan-400 shrink-0 mt-0.5" />
                  <span>{point}</span>
                </div>
              ))}
            </div>

            <div className="pt-4">
              <Button
                asChild
                size="lg"
                className="h-12 px-8 text-base font-bold bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-lg shadow-blue-600/30 border border-blue-400/30"
              >
                <Link href="/assistant">
                  {t("landing.aiSection.cta")}
                </Link>
              </Button>
            </div>
          </div>

          {/* Right Column: Realistic Grounded AI Conversation Box */}
          <div className="lg:col-span-7">
            <div className="rounded-2xl border border-slate-700/80 bg-[#0F172A]/95 p-6 shadow-2xl shadow-blue-950/70 space-y-4">
              {/* Chat Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2.5">
                  <UrsBizIcon size={26} />
                  <div>
                    <span className="text-xs font-bold text-white">UrsBiz AI Copilot</span>
                    <p className="text-[10px] text-slate-400">Strict Grounded Mode</p>
                  </div>
                </div>
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                  <ShieldCheck className="size-3" /> Grounded In Reality
                </span>
              </div>

              {/* User Question Bubble */}
              <div className="flex items-start gap-3 justify-end">
                <div className="max-w-md rounded-2xl rounded-tr-xs bg-blue-600 px-4 py-3 text-xs sm:text-sm font-medium text-white shadow-xs">
                  <p className="text-[10px] font-bold text-blue-200 uppercase tracking-wider mb-1">
                    {t("landing.aiSection.userLabel")}
                  </p>
                  {t("landing.aiSection.userQuery")}
                </div>
                <div className="size-7 rounded-lg bg-blue-700 flex items-center justify-center text-white shrink-0 text-xs font-bold">
                  <User className="size-3.5" />
                </div>
              </div>

              {/* Assistant Grounded Answer */}
              <div className="flex items-start gap-3">
                <div className="size-7 rounded-lg bg-sky-500/20 border border-sky-400/30 flex items-center justify-center text-sky-400 shrink-0">
                  <Sparkles className="size-3.5" />
                </div>

                <div className="flex-1 space-y-3 rounded-2xl rounded-tl-xs border border-slate-800 bg-slate-900/80 p-4 text-xs sm:text-sm text-slate-200">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider">
                      {t("landing.aiSection.aiLabel")}
                    </span>
                    <span className="rounded-md bg-slate-800 px-1.5 py-0.5 text-[9px] font-mono text-slate-300">
                      {t("landing.aiSection.evidenceBadge")}
                    </span>
                  </div>

                  <p className="leading-relaxed font-sans text-slate-100">
                    {t("landing.aiSection.aiAnswer")}
                  </p>

                  {/* Why this answer card */}
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 space-y-1">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      <FileSearch className="size-3 text-cyan-400" />
                      <span>{t("landing.aiSection.whyBadge")}</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {t("landing.aiSection.whyBody")}
                    </p>
                  </div>

                  {/* Recommended Action card */}
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3 space-y-1">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                      <Lightbulb className="size-3" />
                      <span>{t("landing.aiSection.actionBadge")}</span>
                    </div>
                    <p className="text-xs text-slate-200 leading-relaxed">
                      {t("landing.aiSection.actionBody")}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
