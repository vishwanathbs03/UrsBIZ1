"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { Logo } from "@/components/common/Logo";
import { MobileDrawerAuth } from "@/components/auth/MobileDrawerAuth";
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import { isActiveLink, navGroups } from "@/lib/navigation";

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Slide-in drawer used for mobile/tablet navigation (Phase 1 Dark Neon).
 */
export function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const pathname = usePathname() ?? "/";
  const { t } = useLanguage();

  const getLocalizedLabel = (href: string, defaultLabel: string): string => {
    switch (href) {
      case "/":
        return t("nav.home", defaultLabel);
      case "/dashboard":
        return t("nav.dashboard", defaultLabel);
      case "/schemes":
        return t("nav.schemes", defaultLabel);
      case "/analytics":
        return t("nav.analytics", defaultLabel);
      case "/predictive-analytics":
        return t("nav.predictiveAnalytics", defaultLabel);
      case "/action-board":
        return t("nav.actionBoard", defaultLabel);
      case "/insights":
        return t("nav.insights", defaultLabel);
      case "/reports":
        return t("nav.reports", defaultLabel);
      case "/assistant":
        return t("nav.assistant", defaultLabel);
      case "/business":
        return t("nav.business", defaultLabel);
      case "/advisor":
        return t("nav.advisor", defaultLabel);
      case "/notifications":
        return t("nav.notifications", defaultLabel);
      default:
        return defaultLabel;
    }
  };

  useEffect(() => {
    if (!open) {
      return;
    }
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <div
      id="mobile-drawer"
      aria-hidden={!open}
      className={cn(
        "fixed inset-0 z-50 overflow-x-hidden lg:hidden",
        open ? "pointer-events-auto" : "pointer-events-none",
        !open && "hidden",
      )}
    >
      <button
        type="button"
        aria-label="Close menu"
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-black/75 backdrop-blur-sm transition-opacity duration-300",
          open ? "opacity-100" : "opacity-0",
        )}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
        className={cn(
          "absolute right-0 top-0 flex h-full w-80 max-w-[85vw] flex-col border-l border-border/80 bg-background/95 shadow-2xl backdrop-blur-2xl transition-transform duration-300 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border/80 px-4">
          <Logo size="sm" />
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-card hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Close menu"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <div className="border-b border-border/60 bg-card/40 p-3">
          <LanguageSwitcher className="w-full justify-center" />
        </div>

        <nav aria-label="Mobile" className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.id} className="space-y-1">
              <h4 className="px-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                {group.label}
              </h4>
              <ul className="space-y-0.5 pt-0.5">
                {group.links.map((link) => {
                  const Icon = link.icon;
                  const active = isActiveLink(pathname, link.href);
                  const label = getLocalizedLabel(link.href, link.label);
                  return (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                          active
                            ? "border border-primary/30 bg-primary/15 font-semibold text-accent shadow-[0_0_8px_rgba(37,99,235,0.25)]"
                            : "text-muted-foreground hover:bg-card hover:text-foreground",
                        )}
                      >
                        <div className="flex items-center gap-2.5 truncate">
                          <Icon
                            className={cn(
                              "size-4 shrink-0",
                              active ? "text-accent" : "text-muted-foreground",
                            )}
                            aria-hidden="true"
                          />
                          <span className="truncate">{label}</span>
                        </div>
                        {link.badge && (
                          <span className="py-0.2 rounded-full border border-primary/40 bg-primary/20 px-1.5 text-[9px] font-bold text-accent">
                            {link.badge}
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-border/80 bg-card/40 p-4">
          <MobileDrawerAuth />
        </div>
      </aside>
    </div>
  );
}
