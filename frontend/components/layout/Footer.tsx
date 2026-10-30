"use client";

import Link from "next/link";
import { Logo } from "@/components/common/Logo";
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher";
import { useLanguage } from "@/context/language-context";
import { theme } from "@/lib/theme";
import { ShieldCheck } from "lucide-react";

export function Footer() {
  const year = new Date().getFullYear();
  const { t } = useLanguage();

  const productLinks = [
    { href: "/assistant", label: t("nav.assistant") },
    { href: "/analytics", label: t("nav.analytics") },
    { href: "/predictive-analytics", label: t("nav.predictiveAnalytics") },
    { href: "/schemes", label: t("nav.schemes") },
    { href: "/action-board", label: t("nav.actionBoard") },
    { href: "/dashboard", label: t("nav.dashboard") },
  ];

  const companyLinks = [
    { href: "/pitch-deck.html", label: "Pitch Deck" },
    { href: "#", label: "Privacy Policy" },
    { href: "#", label: "Terms of Service" },
    { href: "#", label: "Security Architecture" },
  ];

  return (
    <footer className="border-t border-border bg-card">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-5">
          {/* Brand Column */}
          <div className="lg:col-span-2 space-y-4">
            <Logo size="lg" variant="primary" withSubtitle />
            <p className="max-w-sm text-sm text-muted-foreground leading-relaxed">
              Enterprise AI-powered Business Intelligence Platform for MSMEs &amp; Growing Enterprises.
            </p>
            <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground pt-1">
              <ShieldCheck className="size-4 text-emerald-500" />
              <span>Enterprise Grounded Reasoning • Zero Data Leakage</span>
            </div>
          </div>

          {/* Product Links */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              Product &amp; Engines
            </h3>
            <ul className="space-y-2">
              {productLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company & Resources */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              Company &amp; Resources
            </h3>
            <ul className="space-y-2">
              {companyLinks.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Language Selector Column */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              Language / ಭಾಷೆ
            </h3>
            <LanguageSwitcher />
            <p className="text-[11px] text-muted-foreground leading-relaxed pt-2">
              Available in English and Kannada across the entire AI reasoning pipeline.
            </p>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-14 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-border pt-8 text-xs text-muted-foreground">
          <p>© {year} {theme.brand.name}. All rights reserved.</p>
          <div className="flex items-center gap-4 text-xs">
            <span className="font-mono text-[11px]">{theme.brand.tagline}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
