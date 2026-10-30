"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  ChevronDown,
  Compass,
  KanbanSquare,
  LayoutDashboard,
  Lightbulb,
  Menu,
  Sparkles,
  TrendingUp,
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
  const { t } = useLanguage();

  // Core flagship navigation links visible on standard desktop (lg: 1024px+)
  const coreLinks = [
    { href: "/dashboard", label: t("nav.dashboard") },
    { href: "/schemes", label: t("nav.schemes") },
    { href: "/analytics", label: t("nav.analytics") },
  ];

  // Extended links visible on wide desktop (2xl: 1400px+)
  const wideLinks = [
    { href: "/predictive-analytics", label: t("nav.predictiveAnalytics") },
    { href: "/action-board", label: t("nav.actionBoard") },
    { href: "/insights", label: t("nav.insights") },
  ];

  // All additional modules housed inside the "More" dropdown menu
  const dropdownLinks = [
    { href: "/predictive-analytics", label: t("nav.predictiveAnalytics"), icon: TrendingUp },
    { href: "/action-board", label: t("nav.actionBoard"), icon: KanbanSquare },
    { href: "/insights", label: t("nav.insights"), icon: Lightbulb },
    { href: "/advisor", label: t("nav.advisor", "Advisor"), icon: Compass },
    { href: "/reports", label: t("nav.reports"), icon: BarChart3 },
    { href: "/business", label: t("nav.business"), icon: LayoutDashboard },
  ];

  const isAssistantActive = isActiveLink(pathname, "/assistant");

  return (
    <header
      className={cn(
        "sticky top-0 z-40 w-full border-b border-border/70 bg-background/80 backdrop-blur-md transition-all",
        className,
      )}
    >
      <div className="container mx-auto flex h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        {/* Left: Brand Logo */}
        <div className="flex shrink-0 items-center">
          <Link
            href="/"
            aria-label="URSBiz — Home"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <Logo size="md" variant="compact" />
          </Link>
        </div>

        {/* Center: Desktop Navigation Links (Collision-proof, never overflows) */}
        <nav aria-label="Primary" className="hidden lg:flex items-center gap-1 xl:gap-1.5 shrink-0">
          {/* Core Flagship Links */}
          {coreLinks.map((link) => {
            const active = isActiveLink(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary font-semibold shadow-xs"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
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
                  "hidden 2xl:inline-flex whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary font-semibold shadow-xs"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
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
              "group relative inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[13px] font-semibold transition-all duration-200",
              isAssistantActive
                ? "border-primary bg-primary text-primary-foreground shadow-sm shadow-primary/25"
                : "border-primary/30 bg-primary/5 text-primary hover:border-primary/60 hover:bg-primary/10 hover:shadow-xs",
            )}
          >
            <Sparkles className="size-3.5 animate-pulse text-current" aria-hidden="true" />
            <span>{t("nav.assistant")}</span>
            <span
              className={cn(
                "rounded-md px-1 py-0.2 text-[9px] font-bold uppercase tracking-wider",
                isAssistantActive
                  ? "bg-primary-foreground/20 text-primary-foreground"
                  : "bg-primary/15 text-primary",
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
              aria-label="More navigation modules"
              aria-expanded={moreOpen}
              className={cn(
                "inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-[13px] font-medium transition-colors",
                moreOpen
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
              )}
            >
              <span>More</span>
              <ChevronDown className={cn("size-3.5 transition-transform", moreOpen && "rotate-180")} />
            </button>

            {moreOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-52 rounded-xl border border-border/80 bg-popover/95 p-1.5 shadow-elevated backdrop-blur-md animate-in fade-in-0 zoom-in-95 z-50">
                {dropdownLinks.map((item) => {
                  const Icon = item.icon;
                  const active = isActiveLink(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                        active
                          ? "bg-primary/10 text-primary font-semibold"
                          : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                      )}
                    >
                      <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                      <span>{item.label}</span>
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

          {/* Mobile Drawer Trigger (visible on screens < lg) */}
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-foreground hover:bg-accent lg:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Open menu"
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
