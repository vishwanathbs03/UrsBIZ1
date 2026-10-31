import { ShieldCheck, FileText, BarChart3, ListChecks } from "lucide-react";

const signals = [
  {
    icon: BarChart3,
    title: "Deterministic Profile Readiness Score",
    body: "Computed every time from your business profile — the same inputs always produce the same 0–100 score. It measures how completely the digital twin is populated (six weighted sections), not business risk.",
  },
  {
    icon: ListChecks,
    title: "Profile-Matched Schemes",
    body: "Each scheme card shows match %, the rule we applied, the official source, the last-verified date, and a disclaimer. Final sanctioning rests with the sanctioning authority.",
  },
  {
    icon: ShieldCheck,
    title: "Grounded Advisor Replies",
    body: "Every answer is generated from the deterministic evidence bundle, not the open web. Values are labeled (rule-engine, scenario estimate, retrieved, generated).",
  },
  {
    icon: FileText,
    title: "Audit-Ready Reports",
    body: "One-click PDF and CSV exports include the health snapshot, scheme matches, and scenario horizons so a CA or banker can reproduce every figure from your profile.",
  },
];

export function TestimonialsSection() {
  return (
    <section className="border-t border-border bg-background py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">
            What You Can Verify
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
            Built on Evidence, Not Promises
          </h2>
          <p className="mt-4 text-base text-muted-foreground">
            Every number in UrsBiz is traceable to a rule, a profile input, or a cited source. We do not publish fabricated customer quotes — judge the platform on what the rule engines actually produce.
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {signals.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.title}
                className="flex flex-col rounded-2xl border border-border bg-card p-6 shadow-soft hover-lift transition-all"
              >
                <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-6" />
                </div>
                <h3 className="text-base font-bold text-foreground text-center">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed text-center">
                  {s.body}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
