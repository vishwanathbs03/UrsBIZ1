import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CtaSection() {
  return (
    <section aria-labelledby="cta-title" className="bg-background py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-card p-8 md:p-16 text-center shadow-card">
          <div className="pointer-events-none absolute -right-20 -top-20 size-80 rounded-full bg-primary/20 blur-3xl" />
          <div className="pointer-events-none absolute -left-20 -bottom-20 size-80 rounded-full bg-teal-500/20 blur-3xl" />

          <div className="relative z-10 max-w-3xl mx-auto space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3.5 py-1.5 text-xs font-semibold text-primary">
              <Sparkles className="size-3.5" />
              <span>Unlock Enterprise Decision Power Today</span>
            </span>

            <h2
              id="cta-title"
              className="text-balance text-3xl font-extrabold tracking-tight text-foreground md:text-5xl"
            >
              Ready to Grow Your Business with AI?
            </h2>

            <p className="mx-auto max-w-2xl text-base text-muted-foreground md:text-lg">
              Make smarter business decisions with AI-driven insights, health scoring, government scheme discovery, analytics, and executive reports—all in one platform.
            </p>

            <div className="pt-4 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button asChild size="lg" className="h-12 px-8 text-base shadow-lg shadow-primary/20 gap-2">
                <Link href="/login">
                  Get Started Free
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-12 px-6">
                <a href="#features">Learn More</a>
              </Button>
            </div>

            <p className="text-xs text-muted-foreground pt-2">
              Instant Setup • No Credit Card Required • Deterministic Rule Engine
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
