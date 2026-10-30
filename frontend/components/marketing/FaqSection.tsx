"use client";

import { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";

const faqs = [
  {
    q: "What is UrsBiz and how does it help my business?",
    a: "UrsBiz is an AI-powered Business Intelligence Platform designed for MSMEs. It creates a digital twin of your business profile to compute a 0-100 Profile Readiness Score (a measure of how completely the founder has filled in the digital twin — not a measure of business risk), profile-match 7 curated scheme and registration programs with official authorities (PMEGP, CGTMSE, MUDRA Shishu, MAI, ZED, NSIC, Udyam), generate daily priority briefings, and export bank-ready PDF executive reports.",
  },
  {
    q: "Does UrsBiz guarantee government scheme approval?",
    a: "No. UrsBiz evaluates your operational profile against official ministry eligibility rules to deliver high-confidence match scores (%) and step-by-step application document checklists. The catalog has 7 entries (CGTMSE, ZED, PMEGP, MAI, MUDRA Shishu, NSIC, Udyam). Final sanctioning rests with the respective government sanctioning authority.",
  },
  {
    q: "How does the AI engine avoid hallucinations?",
    a: "UrsBiz uses a deterministic rule engine for profile readiness scoring and scheme profile-matching, so every score and matching percentage is traceable to the input business profile and the cited rule. For natural-language questions, the assistant is grounded in the deterministic evidence bundle — the same data the rule engines produced — and the UI clearly labels each value (Calculated by UrsBiz rule engine, scenario estimate, retrieved from official source, or Generated explanation). The Generated explanation label only appears when a real OpenAI-compatible / Ollama provider answered; deterministic replies are never labelled as generated.",
  },
  {
    q: "How long does it take to onboard my business profile?",
    a: "Onboarding takes less than 2 minutes. Simply fill out our 4-step wizard detailing your turnover, sector, workforce size, and state to instantly view your health score and eligible schemes.",
  },
  {
    q: "Can I export reports for bank loan applications?",
    a: "Yes! With one click, you can download audit-ready executive PDF and CSV reports formatted for bank loan applications, CA reviews, and investor presentations.",
  },
  {
    q: "Is there a free tier available for small businesses?",
    a: "Yes, UrsBiz offers a free core tier allowing business health score calculation, basic scheme matching, and dashboard access with zero credit card required.",
  },
];

export function FaqSection() {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  return (
    <section className="bg-card py-20">
      <div className="container">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <HelpCircle className="size-3.5 text-primary" aria-hidden="true" />
            Frequently Asked Questions
          </span>
          <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
            Answers to the most common MSME questions.
          </h2>
          <p className="mt-3 text-base text-muted-foreground">
            Clear, evidence-backed answers — no padding, no sales language.
          </p>
        </div>

        <div className="mx-auto mt-12 max-w-3xl divide-y divide-border rounded-2xl border border-border bg-background shadow-sm">
          {faqs.map((faq, idx) => {
            const open = openIdx === idx;
            return (
              <div key={faq.q}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold text-foreground transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-expanded={open}
                  aria-controls={`faq-panel-${idx}`}
                  onClick={() => setOpenIdx(open ? null : idx)}
                >
                  <span>{faq.q}</span>
                  <ChevronDown
                    className={
                      "size-4 shrink-0 transition-transform " +
                      (open ? "rotate-180 text-primary" : "text-muted-foreground")
                    }
                    aria-hidden="true"
                  />
                </button>
                {open && (
                  <div
                    id={`faq-panel-${idx}`}
                    className="px-5 pb-5 text-sm text-muted-foreground"
                  >
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
