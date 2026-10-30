import { Building, Globe, Flame, Clock } from "lucide-react";

const stats = [
  {
    val: "0–100",
    label: "Profile Readiness Score",
    desc: "Deterministic measure of how completely the business profile is filled in across six weighted sections. Same inputs always produce the same score.",
    icon: Building,
  },
  {
    val: "7",
    label: "Curated Schemes & Registrations",
    desc: "CGTMSE, ZED, PMEGP, MAI, MUDRA Shishu, NSIC, Udyam — each with official authority, last-verified date and disclaimer.",
    icon: Globe,
  },
  {
    val: "3m / 6m / 12m",
    label: "Scenario Horizons",
    desc: "Forecast engine with horizon, confidence, and ‘no guarantee’ labels.",
    icon: Clock,
  },
  {
    val: "1-click",
    label: "Audit-Ready Reports",
    desc: "PDF + CSV exports with health snapshot, scheme recommendations, and forecasts.",
    icon: Globe,
  },
];

export function ImpactSection() {
  return (
    <section className="bg-gradient-to-b from-background via-primary/5 to-background py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">
            Economic Impact & Social Reach
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
            Driving Scale for Grassroots Economies
          </h2>
          <p className="mt-4 text-base text-muted-foreground">
            Aligned with UN SDG 8 (Decent Work & Economic Growth) to democratize CFO-level intelligence.
          </p>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="flex flex-col justify-between rounded-2xl border border-border bg-card p-6 text-center shadow-soft hover-lift transition-all hover:border-primary/40"
              >
                <div>
                  <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="size-6" />
                  </div>
                  <h3 className="text-4xl font-extrabold text-foreground tracking-tight">{s.val}</h3>
                  <p className="mt-1 text-sm font-bold text-primary">{s.label}</p>
                  <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{s.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
