/**
 * Centralized theme and brand configuration for URSBiz.
 *
 * Single source of truth for:
 * - Brand Name & Wordmark
 * - Enterprise SaaS Positioning & Taglines
 * - Color Palette (Deep Navy, Vibrant Blue, Intelligent Cyan/Teal)
 * - Safe areas & typography guidelines
 */

export const theme = {
  brand: {
    name: "URSBiz",
    legalName: "URSBiz Technologies",
    category: "Enterprise SaaS Business Intelligence Platform",
    positioning: "Intelligent Business Platform for MSMEs & Growing Enterprises",
    tagline: "ANALYZE | PREDICT | GROW | SUCCEED",
    mission:
      "Empower MSMEs and growing enterprises to analyze their reality, predict outcomes with AI, make confident decisions, and scale sustainably.",
  },
  palette: {
    // Primary enterprise palette
    navy: {
      950: "#0A192F",
      900: "#0F172A",
      800: "#1E293B",
      700: "#334155",
    },
    blue: {
      700: "#1D4ED8",
      600: "#2563EB", // Primary brand accent
      500: "#3B82F6",
      400: "#60A5FA",
      100: "#DBEAFE",
      50: "#EFF6FF",
    },
    cyan: {
      600: "#0891B2",
      500: "#06B6D4", // Intelligence accent
      400: "#22D3EE",
      300: "#67E8F9",
      100: "#CFFAFE",
      50: "#ECFEFF",
    },
    slate: {
      900: "#0F172A",
      700: "#334155",
      500: "#64748B",
      300: "#CBD5E1",
      100: "#F1F5F9",
      50: "#F8FAFC",
    },
  },
  colors: {
    primary: "hsl(var(--primary))",
    primaryFg: "hsl(var(--primary-foreground))",
    muted: "hsl(var(--muted-foreground))",
    border: "hsl(var(--border))",
  },
  radius: {
    sm: "calc(var(--radius) - 4px)",
    md: "calc(var(--radius) - 2px)",
    lg: "var(--radius)",
    xl: "calc(var(--radius) + 4px)",
    "2xl": "calc(var(--radius) + 8px)",
  },
  shadow: {
    soft: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.05)",
    card: "0 4px 12px -2px rgb(15 23 42 / 0.06), 0 2px 6px -2px rgb(15 23 42 / 0.04)",
    elevated:
      "0 10px 30px -10px rgb(15 23 42 / 0.15), 0 4px 8px -4px rgb(15 23 42 / 0.08)",
  },
} as const;

export type Theme = typeof theme;
