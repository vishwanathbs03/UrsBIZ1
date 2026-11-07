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
 * Slide-in drawer used for mobile/tablet navigation (Phase 1 & Phase 6.29).
 * Fully bilingual English & Kannada, WCAG touch target compliant (>=44px),
 * and keyboard accessible.
 */
export function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const pathname = usePathname() ?? "/";
  const { t, language } = useLanguage();

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
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("a11y.openNavigation", "Mobile Navigation")}
      className="fixed inset-0 z-50 lg:hidden"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-md transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <aside
        id="mobile-drawer"
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-xs flex-col border-l border-border/80 bg-background/95 shadow-2xl backdrop-blur-xl",
          "animate-in slide-in-from-right duration-200",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border/80 px-4">
          <Link
            href="/"
            onClick={onClose}
            aria-label="UrsBiz — Home"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            <Logo size="md" />
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-muted-foreground hover:bg-card hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            aria-label={t("a11y.closeNavigation", "Close menu")}
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <div className="border-b border-border/60 bg-card/40 p-3">
          <LanguageSwitcher className="w-full justify-center" />
        </div>

        <nav aria-label="Mobile" className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => {
            const groupTitle = group.labelKey ? t(group.labelKey, group.label) : group.label;
            return (
              <div key={group.id} className="space-y-1">
                <h4 className="px-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                  {groupTitle}
                </h4>
                <ul className="space-y-0.5 pt-0.5">
                  {group.links.map((link) => {
                    const Icon = link.icon;
                    const active = isActiveLink(pathname, link.href);
                    const label = link.labelKey ? t(link.labelKey, link.label) : link.label;
                    const badgeText = link.badgeKey ? t(link.badgeKey, link.badge || "") : link.badge;

                    return (
                      <li key={link.href}>
                        <Link
                          href={link.href}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            "flex min-h-[44px] items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
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
                            <span className={cn("truncate", language === "kn" && "font-kannada")}>
                              {label}
                            </span>
                          </div>
                          {badgeText && (
                            <span className="py-0.5 rounded-full border border-primary/40 bg-primary/20 px-1.5 text-[9px] font-bold text-accent">
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

        <div className="border-t border-border/80 bg-card/40 p-4">
          <MobileDrawerAuth />
        </div>
      </aside>
    </div>
  );
}
