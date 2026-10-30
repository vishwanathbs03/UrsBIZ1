import {
  Bot,
  Building2,
  FileText,
  Landmark,
  LineChart,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Feature {
  title: string;
  description: string;
  icon: LucideIcon;
  badge: string;
}

const features: Feature[] = [
  {
    title: "AI Business Advisor",
    description:
      "Get daily priority action briefings, plain-language Q&A responses, and strategy suggestions grounded in the deterministic evidence bundle — every recommendation ties back to a business input.",
    icon: Bot,
    badge: "Daily Guidance",
  },
  {
    title: "Business Digital Twin",
    description:
      "Construct a live digital model of your operational parameters, turnover, workforce, and sector positioning in under 2 minutes.",
    icon: Building2,
    badge: "Core Profile",
  },
  {
    title: "Profile Readiness Engine",
    description:
      "Instantly compute a 0-100 Profile Readiness Score measuring how completely the founder has filled in their business profile across six weighted sections. Same inputs always produce the same score.",
    icon: ShieldCheck,
    badge: "0-100 Index",
  },
  {
    title: "Smart Analytics",
    description:
      "Visualize revenue trends, working capital risks, and 3m/6m/12m scenario estimates. Every figure carries a horizon, confidence, and explicit 'no guarantee' disclaimer.",
    icon: LineChart,
    badge: "Predictive",
  },
  {
    title: "Government Scheme Discovery",
    description:
      "Automatically match official central and state MSME subsidies (PMEGP, CGTMSE, Mudra, ZED and others) with profile-match scores and direct application links.",
    icon: Landmark,
    badge: "Capital Match",
  },
  {
    title: "Executive Reports",
    description:
      "Generate 1-click audit-ready PDF and CSV reports formatted for bank loan applications, tax CAs, and investor meetings.",
    icon: FileText,
    badge: "1-Click PDF",
  },
];

export function FeaturesSection() {
  return (
    <section
      id="features"
      aria-labelledby="features-title"
      className="bg-background py-20 md:py-28"
    >
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">
            Unified Platform Capability
          </p>
          <h2
            id="features-title"
            className="mt-3 text-3xl font-extrabold tracking-tight text-foreground md:text-4xl lg:text-5xl"
          >
            Six Powerful Engines. One Seamless Platform.
          </h2>
          <p className="mt-4 text-base text-muted-foreground md:text-lg">
            UrsBiz consolidates fragmented business intelligence tools into a single, intuitive operating system for growing small businesses.
          </p>
        </div>

        <ul className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <li
                key={feature.title}
                className="group relative flex flex-col justify-between rounded-2xl border border-border bg-card p-6 shadow-soft hover-lift transition-all hover:border-primary/40 hover:shadow-card"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="inline-flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                      <Icon className="size-6" aria-hidden="true" />
                    </div>
                    <span className="rounded-full bg-secondary/80 px-2.5 py-1 text-[11px] font-bold text-muted-foreground">
                      {feature.badge}
                    </span>
                  </div>

                  <h3 className="mt-5 text-xl font-bold text-foreground">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
