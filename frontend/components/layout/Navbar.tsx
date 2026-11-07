"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  ChevronDown,
  Compass,
  FileText,
  LayoutDashboard,
  Menu,
  Plug,
  Scale,
  ShieldCheck,
  Sliders,
  Sparkles,
  Target,
  Users,
} from "lucide-react";
import { Logo } from "@/components/common/Logo";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { NavbarAuth } from "@/components/auth/NavbarAuth";
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import { isActiveLink } from "@/lib/navigation";
import { MobileDrawer } from "@/components/layout/MobileDrawer";

interface NavbarProps {
  className?: string;
}

export function Navbar({ className }: NavbarProps) {
  const pathname = usePathname() ?? "/";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const { t, language } = useLanguage();

  // Core flagship navigation links visible on standard desktop (lg: 1024px+)
  const coreLinks = [
    { href: "/dashboard", label: t("nav.dashboard", "Dashboard") },
    { href: "/schemes", label: t("nav.schemes", "Government Schemes") },
    { href: "/analytics", label: t("nav.analytics", "Analytics") },
  ];

  // Extended links visible on wide desktop (2xl: 1400px+)
  const wideLinks = [
    { href: "/predictive-analytics", label: t("nav.predictiveAnalytics", "Forecasts") },
    { href: "/action-board", label: t("nav.actionBoard", "Recommendations") },
    { href: "/insights", label: t("nav.insights", "Insights") },
  ];

  // All additional modules housed inside the "More" dropdown menu
  const dropdownLinks = [
    { href: "/decision-workbench", label: t("nav.decisionWorkbench", "Decision Workbench"), icon: Scale },
    { href: "/what-if", label: t("nav.whatIf", "What-If Simulator"), icon: Sliders },
    { href: "/goals", label: t("nav.goals", "Business Goals"), icon: Target },
    { href: "/data-confidence", label: t("nav.dataConfidence", "Data Confidence"), icon: ShieldCheck },
    { href: "/metrics", label: t("nav.metrics", "Metrics Dictionary"), icon: BookOpen },
    { href: "/advisor", label: t("nav.advisor", "Advisor"), icon: Compass },
    { href: "/reports", label: t("nav.reports", "Reports"), icon: FileText },
    { href: "/collaboration", label: t("nav.collaboration", "Team & Approvals"), icon: Users },
    { href: "/integrations", label: t("nav.integrations", "Integrations"), icon: Plug },
    { href: "/business", label: t("nav.business", "Business Profile"), icon: LayoutDashboard },
  ];

  const isAssistantActive = isActiveLink(pathname, "/assistant");

  return (
    <header
      className={cn(
        "sticky top-0 z-40 w-full border-b border-border/80 bg-background/85 backdrop-blur-xl transition-all duration-300",
        className,
      )}
    >
      <div className="container mx-auto flex h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        {/* Left: Brand Logo */}
        <div className="flex shrink-0 items-center">
          <Link
            href="/"
            aria-label="URSBiz — Home"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            <Logo size="md" variant="compact" />
          </Link>
        </div>

        {/* Center: Desktop Navigation Links (Collision-proof, never overflows) */}
        <nav aria-label="Primary" className="hidden shrink-0 items-center gap-1 lg:flex xl:gap-2">
          {/* Core Flagship Links */}
          {coreLinks.map((link) => {
            const active = isActiveLink(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-150",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
                  active
                    ? "border border-primary/30 bg-primary/15 font-semibold text-accent shadow-[0_0_10px_rgba(37,99,235,0.25)]"
                    : "text-muted-foreground hover:border hover:border-border/60 hover:bg-card hover:text-foreground",
                  language === "kn" && "font-kannada",
                )}
              >
                {link.label}
              </Link>
            );
          })}

          {/* Extended Links (Visible on 2xl screens, hidden on standard laptop screens to prevent overlap) */}
          {wideLinks.map((link) => {
            const active = isActiveLink(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "hidden whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-150 2xl:inline-flex",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
                  active
                    ? "border border-primary/30 bg-primary/15 font-semibold text-accent shadow-[0_0_10px_rgba(37,99,235,0.25)]"
                    : "text-muted-foreground hover:border hover:border-border/60 hover:bg-card hover:text-foreground",
                  language === "kn" && "font-kannada",
                )}
              >
                {link.label}
              </Link>
            );
          })}

          {/* AI Assistant Flagship Distinct Pill Highlight */}
          <Link
            href="/assistant"
            aria-current={isAssistantActive ? "page" : undefined}
            className={cn(
              "group relative inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] font-semibold transition-all duration-200",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
              isAssistantActive
                ? "border-accent bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-[0_0_18px_rgba(6,182,212,0.45)]"
                : "border-primary/40 bg-primary/10 text-accent hover:border-primary/80 hover:bg-primary/20 hover:shadow-[0_0_14px_rgba(37,99,235,0.35)]",
            )}
          >
            <Sparkles className="size-3.5 animate-pulse text-current" aria-hidden="true" />
            <span className={cn(language === "kn" && "font-kannada")}>{t("nav.assistant", "AI Business Assistant")}</span>
            <span
              className={cn(
                "rounded-md px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider",
                isAssistantActive
                  ? "bg-white/20 text-white"
                  : "border border-primary/40 bg-primary/25 text-accent",
              )}
            >
              AI
            </span>
          </Link>

          {/* "More" Dropdown Menu */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setMoreOpen(!moreOpen)}
              onBlur={() => setTimeout(() => setMoreOpen(false), 200)}
              aria-label={t("a11y.openNavigation", "More navigation modules")}
              aria-expanded={moreOpen}
              className={cn(
                "inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
                moreOpen
                  ? "border border-border bg-card text-foreground"
                  : "text-muted-foreground hover:bg-card hover:text-foreground",
              )}
            >
              <span className={cn(language === "kn" && "font-kannada")}>{t("nav.more", "More")}</span>
              <ChevronDown
                className={cn("size-3.5 transition-transform", moreOpen && "rotate-180")}
              />
            </button>

            {moreOpen && (
              <div className="animate-in fade-in-0 zoom-in-95 absolute right-0 top-full z-50 mt-1.5 w-60 rounded-xl border border-border/80 bg-card/95 p-1.5 shadow-2xl backdrop-blur-xl">
                {dropdownLinks.map((item) => {
                  const Icon = item.icon;
                  const active = isActiveLink(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium transition-colors",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                        active
                          ? "border border-primary/25 bg-primary/15 font-semibold text-accent"
                          : "text-muted-foreground hover:bg-accent/80 hover:text-foreground",
                      )}
                    >
                      <Icon className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
                      <span className={cn("truncate", language === "kn" && "font-kannada")}>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </nav>

        {/* Right: Language Switcher, Theme Toggle, Auth, Mobile Hamburger */}
        <div className="flex shrink-0 items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
          <NavbarAuth />

          {/* Mobile Drawer Trigger (visible on screens < lg, with 44px touch target) */}
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 lg:hidden"
            aria-label={t("a11y.openNavigation", "Open menu")}
            aria-expanded={drawerOpen}
            aria-controls="mobile-drawer"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>
        </div>
      </div>

      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </header>
  );
}
