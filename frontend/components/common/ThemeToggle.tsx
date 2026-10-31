"use client";

/**
 * ThemeToggle — minimal light/dark toggle.
 *
 * Uses the existing Tailwind `darkMode: "class"` strategy. We do NOT
 * pull in `next-themes` (out of scope for H6.1). The toggle:
 *   1. reads the saved preference from localStorage on mount,
 *   2. flips the `dark` class on <html>,
 *   3. persists the choice in localStorage,
 *   4. applies the saved preference BEFORE first paint via the
 *      inline script in app/layout.tsx, so there is no FOUC.
 */

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const STORAGE_KEY = "ursbiz.theme";

function readStoredTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
  } catch (_) {
    /* fall through */
  }
  // Default to dark for the official Dark Neon SaaS experience
  if (typeof window.matchMedia === "function") {
    if (window.matchMedia("(prefers-color-scheme: light)").matches) {
      return "light";
    }
  }
  return "dark";
}

export function applyTheme(theme: "light" | "dark"): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = readStoredTheme();
    setTheme(stored);
    applyTheme(stored);
    setMounted(true);
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch (_) {
      /* storage may be unavailable in incognito; non-fatal */
    }
  };

  // Avoid hydration mismatch: render a stable button until mounted,
  // then render the actual icon once the preference is known.
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={
        mounted
          ? theme === "dark"
            ? "Switch to light mode"
            : "Switch to dark mode"
          : "Toggle theme"
      }
      aria-pressed={mounted ? theme === "dark" : undefined}
      className="inline-flex h-10 w-10 items-center justify-center rounded-md text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      data-testid="theme-toggle"
    >
      {mounted ? (
        theme === "dark" ? (
          <Sun className="size-4" aria-hidden="true" />
        ) : (
          <Moon className="size-4" aria-hidden="true" />
        )
      ) : (
        // Tiny invisible placeholder keeps the button size stable
        // across SSR and hydration.
        <span className="block size-4" aria-hidden="true" />
      )}
    </button>
  );
}
