import Link from "next/link";
import { ArrowRight, Bell, Bot, FileText, Landmark, LineChart, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

const showcases = [
  {
    id: "dashboard",
    title: "Executive Dashboard & Profile Readiness Score",
    subtitle: "Real-time visibility into your 0–100 profile-completeness index.",
    description:
      "Monitor your Profile Readiness Score out of 100. It measures how completely your digital twin is filled in across six weighted sections (profile completeness, business info, products/services, team, financial, online presence). It is not a measure of business risk — a fully-populated profile does not mean the business is risk-free.",
    icon: ShieldCheck,
    href: "/dashboard",
    stats: [
      { label: "Score", val: "0–100 (deterministic)" },
      { label: "Measures", val: "Profile completeness" },
    ],
  },
  {
    id: "schemes",
    title: "Government Scheme Discovery Engine",
    subtitle: "Unlock capital subsidies & interest subvention schemes.",
    description:
      "Profile-match central and state schemes (PMEGP, CGTMSE, Mudra, ZED, and others) against your sector, location, and turnover. Each match shows the cited authority, last-verified date, and a clear disclaimer.",
    icon: Landmark,
    href: "/schemes",
    stats: [
      { label: "Schemes Catalog", val: "MSME / NSIC / TUF / ZED" },
      { label: "Profile Match", val: "Score & Disclaimer" },
    ],
  },
  {
    id: "analytics",
    title: "Predictive Analytics & Revenue Forecasting",
    subtitle: "Forward-looking 3m, 6m, and 12m growth trajectories.",
    description:
      "Stop guessing next quarter's revenue. UrsBiz uses deterministic rule engines to model cash flow trajectories and evaluate the impact of reinvesting grant subsidies.",
    icon: LineChart,
    href: "/analytics",
    stats: [
      { label: "Projection Horizon", val: "12 Months" },
      { label: "Scoring Method", val: "Deterministic Rules" },
    ],
  },
  {
    id: "advisor",
    title: "AI Business Advisor & Priority Action Board",
    subtitle: "Daily 3-bullet briefings designed for busy founders.",
    description:
      "Every morning, the AI Advisor reviews your operational data to highlight the single highest-ROI priority action to execute today—from working capital optimization to compliance filing.",
    icon: Bot,
    href: "/advisor",
    stats: [
      { label: "Daily Briefings", val: "Actionable" },
      { label: "Grounding", val: "Deterministic + Evidence" },
    ],
  },
  {
    id: "reports",
    title: "1-Click Audit-Ready Executive Reports",
    subtitle: "Bank-ready PDF & CSV exports in seconds.",
    description:
      "Instantly export branded PDF reports complete with Business Health metrics, scheme recommendations, and 12-month projections formatted for banks, CAs, and investors.",
    icon: FileText,
    href: "/reports",
    stats: [
      { label: "Export Format", val: "PDF & CSV" },
      { label: "Includes", val: "Health + Schemes + Forecast" },
    ],
  },
  {
    id: "notifications",
    title: "Notification Center & Critical Alerting",
    subtitle: "Never miss a scheme application deadline or risk warning.",
    description:
      "Integrated notification system delivering instant alerts when new government subsidies open or critical health threshold drops are detected.",
    icon: Bell,
    href: "/notifications",
    stats: [
      { label: "Alert Type", val: "Threshold + Deadline" },
      { label: "Shortcut", val: "Ctrl + K" },
    ],
  },
];

export function ProductShowcaseSection() {
  return (
    <section id="showcase" className="border-t border-border bg-muted/20 py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">
            Interactive Product Tour
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
            Designed for Speed, Precision, and Impact
          </h2>
          <p className="mt-4 text-base text-muted-foreground">
            Explore how UrsBiz transforms every facet of your small business operations.
          </p>
        </div>

        <div className="mt-16 space-y-16">
          {showcases.map((item, idx) => {
            const Icon = item.icon;
            const isEven = idx % 2 === 0;

            return (
              <div
                key={item.id}
                className={`flex flex-col gap-8 rounded-2xl border border-border bg-card p-6 md:p-10 shadow-soft lg:flex-row lg:items-center ${
                  isEven ? "" : "lg:flex-row-reverse"
                }`}
              >
                {/* Text Content */}
                <div className="flex-1 space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
                    <Icon className="size-3.5" />
                    <span>{item.subtitle}</span>
                  </div>

                  <h3 className="text-2xl font-bold text-foreground md:text-3xl">
                    {item.title}
                  </h3>

                  <p className="text-sm leading-relaxed text-muted-foreground md:text-base">
                    {item.description}
                  </p>

                  <div className="flex flex-wrap gap-4 pt-2">
                    {item.stats.map((stat) => (
                      <div
                        key={stat.label}
                        className="rounded-lg border border-border bg-muted/40 px-3.5 py-2 text-left"
                      >
                        <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                          {stat.label}
                        </p>
                        <p className="text-sm font-bold text-foreground">{stat.val}</p>
                      </div>
                    ))}
                  </div>

                  <div className="pt-4">
                    <Button asChild size="sm" variant="outline" className="gap-2">
                      <Link href={item.href}>
                        Explore {item.id.replace("-", " ")}
                        <ArrowRight className="size-3.5" />
                      </Link>
                    </Button>
                  </div>
                </div>

                {/* Card Mockup Graphic */}
                <div className="flex-1">
                  <div className="relative rounded-xl border border-border bg-background p-6 shadow-inner">
                    <div className="flex items-center justify-between border-b border-border pb-3">
                      <div className="flex items-center gap-2">
                        <Icon className="size-5 text-primary" />
                        <span className="text-xs font-bold text-foreground uppercase tracking-wider">{item.id}</span>
                      </div>
                      <span className="text-[10px] font-semibold text-emerald-500 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                        Live Module
                      </span>
                    </div>

                    <div className="mt-4 space-y-3">
                      <div className="h-4 w-3/4 rounded bg-muted/60" />
                      <div className="h-3 w-1/2 rounded bg-muted/40" />
                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <div className="h-16 rounded-lg border border-border/60 bg-card p-2" />
                        <div className="h-16 rounded-lg border border-border/60 bg-card p-2" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
