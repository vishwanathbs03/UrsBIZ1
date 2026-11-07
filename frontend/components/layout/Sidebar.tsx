"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Logo } from "@/components/common/Logo";
import { cn } from "@/lib/utils";
import { isActiveLink, navGroups } from "@/lib/navigation";
import { useLanguage } from "@/context/language-context";

interface SidebarProps {
  className?: string;
}

/**
 * Modern Dark Neon Desktop Sidebar (Phase 1 & Phase 6.29).
 * Features organized hierarchical navigation groups with full bilingual
 * English & Kannada parity, electric-blue active indicators, subtle glassmorphism,
 * and deterministic engine trust badge.
 */
export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname() ?? "/";
  const { t, language } = useLanguage();

  // Save last visited page in localStorage for smooth navigation memory
  if (typeof window !== "undefined" && pathname !== "/" && !pathname.startsWith("/auth")) {
    try {
      localStorage.setItem("urs_last_visited_page", pathname);
    } catch {
      // Ignore quota errors
    }
  }

  return (
    <aside
      aria-label={t("a11y.openNavigation", "Sidebar navigation")}
      className={cn(
        "hidden lg:fixed lg:inset-y-0 lg:z-30 lg:flex lg:w-64 lg:flex-col",
        "border-r border-border/80 bg-background/90 backdrop-blur-xl transition-all duration-300",
        className,
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-border/80 px-6">
        <Link
          href="/"
          aria-label="UrsBiz — home"
          className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          <Logo size="md" />
        </Link>
      </div>

      {/* Grouped Navigation */}
      <nav
        aria-label={language === "kn" ? "ಪ್ರಾಥಮಿಕ ನ್ಯಾವಿಗೇಷನ್" : "Sidebar primary"}
        className="scrollbar-thin scrollbar-thumb-border/50 flex-1 space-y-5 overflow-y-auto px-3 py-4"
      >
        {navGroups.map((group) => {
          const groupTitle = group.labelKey ? t(group.labelKey, group.label) : group.label;
          return (
            <div key={group.id} className="space-y-1">
              <h3 className="px-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground/70">
                {groupTitle}
              </h3>
              <ul className="space-y-0.5 pt-1">
                {group.links.map((link) => {
                  const Icon = link.icon;
                  const active = isActiveLink(pathname, link.href);
                  const linkTitle = link.labelKey ? t(link.labelKey, link.label) : link.label;
                  const badgeText = link.badgeKey ? t(link.badgeKey, link.badge || "") : link.badge;

                  return (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "group relative flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-xs font-medium transition-all duration-200",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
                          active
                            ? "shadow-xs border border-primary/25 bg-primary/10 font-semibold text-primary"
                            : "text-muted-foreground hover:border hover:border-border/60 hover:bg-card/80 hover:text-foreground",
                        )}
                      >
                        <div className="flex items-center gap-2.5 truncate">
                          {/* Active vertical neon highlight bar */}
                          {active && (
                            <span
                              aria-hidden="true"
                              className="absolute bottom-1.5 left-0 top-1.5 w-1 rounded-r-md bg-accent shadow-[0_0_8px_rgba(59,130,246,0.8)]"
                            />
                          )}
                          <Icon
                            className={cn(
                              "size-4 shrink-0 transition-colors duration-200",
                              active
                                ? "text-accent drop-shadow-[0_0_6px_rgba(59,130,246,0.5)]"
                                : "text-muted-foreground group-hover:text-foreground",
                            )}
                            aria-hidden="true"
                          />
                          <span className={cn("truncate", language === "kn" && "font-kannada")}>
                            {linkTitle}
                          </span>
                        </div>

                        {/* Badge if present */}
                        {badgeText && (
                          <span
                            className={cn(
                              "rounded-full px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wide",
                              link.neonBadge
                                ? "animate-pulse border border-primary/40 bg-primary/20 text-accent shadow-[0_0_8px_rgba(37,99,235,0.4)]"
                                : "border border-border/80 bg-secondary text-secondary-foreground",
                            )}
                          >
                            {badgeText}
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Footer Trust & Architecture Badge */}
      <div className="border-t border-border/80 bg-card/40 p-3.5">
        <div className="shadow-xs rounded-xl border border-border/80 bg-card/80 p-3 text-card-foreground">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="size-3.5 shrink-0 text-emerald-400" aria-hidden="true" />
            <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
              {language === "kn" ? "ಆಧಾರಿತ AI ಎಂಜಿನ್" : "Grounded AI Engine"}
            </p>
          </div>
          <p className="mt-1 text-[11px] leading-tight text-muted-foreground">
            {language === "kn"
              ? "ಶೂನ್ಯ ಕಲ್ಪನೆ. ಕಟ್ಟುನಿಟ್ಟಾದ ಗಣಿತೀಯ ವಂಶಾವಳಿ."
              : "Zero hallucinations. Strict mathematical lineage."}
          </p>
        </div>
      </div>
    </aside>
  );
}
