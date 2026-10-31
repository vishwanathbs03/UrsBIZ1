"use client";

import * as React from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ProfilePanel } from "@/features/profile/ProfilePanel";

/**
 * Auth-aware section of the navbar. Renders the public CTA pair
 * when no session exists, and a single button — "open profile panel"
 * — when one does.
 *
 * Sprint 23 — the static name chip is replaced by a button that
 * opens the slide-over profile panel. Sign-out moved into the
 * panel itself; the mobile drawer footer still owns the mobile
 * sign-out surface.
 */
export function NavbarAuth() {
  const { status, user } = useAuth();
  const [open, setOpen] = React.useState(false);

  if (status === "authenticated" && user) {
    const initial = user.full_name.trim().charAt(0).toUpperCase() || "?";
    return (
      <>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label="Open profile panel"
          className="hidden md:inline-flex items-center gap-2 rounded-full border border-border bg-card px-2.5 py-1 max-w-[180px] hover:bg-accent"
        >
          <span
            aria-hidden="true"
            className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
          >
            {initial}
          </span>
          <span className="truncate text-sm font-medium text-foreground">
            {user.full_name}
          </span>
        </Button>
        <ProfilePanel open={open} onOpenChange={setOpen} />
      </>
    );
  }

  return (
    <div className="hidden items-center gap-2 md:flex">
      <Button asChild variant="ghost" size="sm">
        <Link href="/login">Sign in</Link>
      </Button>
      <Button asChild size="sm">
        <Link href="/register">Get Started</Link>
      </Button>
    </div>
  );
}
