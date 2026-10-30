import { Check, X } from "lucide-react";

const comparisons = [
  {
    feature: "Business Analysis",
    traditional: "Manual, retrospective bookkeeping from last month",
    ursbiz: "Real-time AI-driven business health scoring",
  },
  {
    feature: "Profile Readiness Score",
    traditional: "Fragmented spreadsheets with zero unified index",
    ursbiz: "Unified 0-100 Profile Readiness Score across 6 weighted sections — measures how complete the digital twin is",
  },
  {
    feature: "Government Schemes",
    traditional: "Manual search across multiple ministry portals",
    ursbiz: "Profile-match with score, last-verified date, and disclaimer",
  },
  {
    feature: "Executive Reports",
    traditional: "Manual CA consultation (third-party fee)",
    ursbiz: "One-click audit-ready PDF & CSV exports",
  },
  {
    feature: "Growth Strategy",
    traditional: "Unsubstantiated intuition and guesswork",
    ursbiz: "Deterministic 3m/6m/12m scenario estimates with horizon & confidence labels",
  },
  {
    feature: "Platform Tooling",
    traditional: "Multiple disconnected apps (Tally + Excel + CA)",
    ursbiz: "Single integrated platform — business profile, health scoring, schemes, reports, advisor",
  },
];

export function WhyUrsBizSection() {
  return (
    <section className="border-t border-border bg-muted/20 py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">
            Competitive Superiority
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
            Why UrsBiz Stands Out
          </h2>
          <p className="mt-4 text-base text-muted-foreground">
            See how UrsBiz compares to traditional manual bookkeeping and fragmented consulting services.
          </p>
        </div>

        {/* Comparison Table */}
        <div className="mt-14 overflow-x-auto rounded-2xl border border-border bg-card shadow-soft">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                <th className="p-4 font-bold">Feature / Capability</th>
                <th className="p-4 font-bold text-red-500/90">Traditional Approach</th>
                <th className="p-4 font-bold text-primary">UrsBiz Platform</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {comparisons.map((row) => (
                <tr key={row.feature} className="transition-colors hover:bg-muted/20">
                  <td className="p-4 font-bold text-foreground">{row.feature}</td>
                  <td className="p-4 text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <X className="size-4 text-red-500 shrink-0" />
                      <span>{row.traditional}</span>
                    </div>
                  </td>
                  <td className="p-4 font-semibold text-foreground">
                    <div className="flex items-center gap-2">
                      <Check className="size-4 text-emerald-500 shrink-0" />
                      <span>{row.ursbiz}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
