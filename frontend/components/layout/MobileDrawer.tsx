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
import { isActiveLink, mainNavLinks } from "@/lib/navigation";

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Slide-in drawer used for mobile/tablet navigation.
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
        "fixed inset-0 z-50 overflow-x-hidden md:hidden",
        open ? "pointer-events-auto" : "pointer-events-none",
        !open && "hidden",
      )}
    >
      <button
        type="button"
        aria-label="Close menu"
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-foreground/40 backdrop-blur-sm transition-opacity",
          open ? "opacity-100" : "opacity-0",
        )}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
        className={cn(
          "absolute right-0 top-0 flex h-full w-72 flex-col border-l border-border bg-background shadow-elevated transition-transform",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          <Logo size="sm" />
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent"
            aria-label="Close menu"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <div className="border-b border-border/60 p-3">
          <LanguageSwitcher className="w-full justify-center" />
        </div>

        <nav aria-label="Mobile" className="flex-1 overflow-y-auto p-4">
          <ul className="flex flex-col gap-1">
            {mainNavLinks.map((link) => {
              const active = isActiveLink(pathname, link.href);
              const label = getLocalizedLabel(link.href, link.label);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-accent font-semibold text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    )}
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-border p-4">
          <MobileDrawerAuth />
        </div>
      </aside>
    </div>
  );
}
