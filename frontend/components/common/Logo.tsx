"use client";

import React from "react";
import { cn } from "@/lib/utils";

export type LogoVariant =
  | "primary" // Icon + URSBiz + Subtitle
  | "compact" // Icon + URSBiz
  | "icon-only" // Just the symbol
  | "white" // White wordmark & icon for dark navy backgrounds
  | "dark" // Dark navy wordmark & icon for light backgrounds
  | "monochrome" // Single-color (black or currentColor) for print/PDF
  | "blue" // White on brand blue background
  | "app-icon"; // Square/squircle badge icon

export type LogoSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl";

export interface LogoProps {
  /** Visual variant of the logo lockup */
  variant?: LogoVariant;
  /** Scale preset */
  size?: LogoSize;
  /** Show the formal enterprise subtitle below wordmark */
  withSubtitle?: boolean;
  /** Show the brand tagline below */
  withTagline?: boolean;
  /** Custom class name on the outer container */
  className?: string;
  /** Custom class name specifically on the text wordmark */
  textClassName?: string;
  /** Custom class name on the icon */
  iconClassName?: string;
}

const SIZE_MAP: Record<
  LogoSize,
  {
    iconDim: number;
    titleSize: string;
    subtitleSize: string;
    taglineSize: string;
    gap: string;
  }
> = {
  xs: {
    iconDim: 20,
    titleSize: "text-sm",
    subtitleSize: "text-[9px]",
    taglineSize: "text-[8px]",
    gap: "gap-1.5",
  },
  sm: {
    iconDim: 26,
    titleSize: "text-base",
    subtitleSize: "text-[10px]",
    taglineSize: "text-[9px]",
    gap: "gap-2",
  },
  md: {
    iconDim: 34,
    titleSize: "text-lg",
    subtitleSize: "text-[11px]",
    taglineSize: "text-[10px]",
    gap: "gap-2.5",
  },
  lg: {
    iconDim: 44,
    titleSize: "text-xl",
    subtitleSize: "text-xs",
    taglineSize: "text-[11px]",
    gap: "gap-3",
  },
  xl: {
    iconDim: 56,
    titleSize: "text-2xl",
    subtitleSize: "text-sm",
    taglineSize: "text-xs",
    gap: "gap-3.5",
  },
  "2xl": {
    iconDim: 72,
    titleSize: "text-3xl",
    subtitleSize: "text-base",
    taglineSize: "text-sm",
    gap: "gap-4",
  },
};

/**
 * Pure SVG Symbol for URSBiz.
 * Combines:
 * 1. Stylized Geometric "U" letterform
 * 2. Ascending 3-column analytics growth bars
 * 3. Precision 4-point AI intelligence star at the upper apex
 */
export function UrsBizIcon({
  size = 32,
  variant = "compact",
  className,
}: {
  size?: number;
  variant?: LogoVariant;
  className?: string;
}) {
  const isMonochrome = variant === "monochrome";
  const isWhite = variant === "white" || variant === "blue";
  const isAppIcon = variant === "app-icon";

  const uStroke = isMonochrome
    ? "currentColor"
    : isWhite
    ? "#FFFFFF"
    : "url(#ursbiz-u-grad)";

  const bar1Fill = isMonochrome
    ? "currentColor"
    : isWhite
    ? "#93C5FD"
    : "url(#ursbiz-bar1-grad)";

  const bar2Fill = isMonochrome
    ? "currentColor"
    : isWhite
    ? "#60A5FA"
    : "url(#ursbiz-bar2-grad)";

  const bar3Fill = isMonochrome
    ? "currentColor"
    : isWhite
    ? "#FFFFFF"
    : "url(#ursbiz-bar3-grad)";

  const starFill = isMonochrome
    ? "currentColor"
    : isWhite
    ? "#67E8F9"
    : "url(#ursbiz-star-grad)";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0 select-none", className)}
      aria-hidden="true"
    >
      <defs>
        {/* Gradients */}
        <linearGradient id="ursbiz-u-grad" x1="8" y1="8" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1E3A8A" />
          <stop offset="60%" stopColor="#2563EB" />
          <stop offset="100%" stopColor="#0284C7" />
        </linearGradient>

        <linearGradient id="ursbiz-bar1-grad" x1="17" y1="26" x2="17" y2="34" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#06B6D4" />
          <stop offset="100%" stopColor="#0891B2" />
        </linearGradient>

        <linearGradient id="ursbiz-bar2-grad" x1="23" y1="20" x2="23" y2="34" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#2563EB" />
        </linearGradient>

        <linearGradient id="ursbiz-bar3-grad" x1="29" y1="14" x2="29" y2="34" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#60A5FA" />
          <stop offset="100%" stopColor="#1D4ED8" />
        </linearGradient>

        <linearGradient id="ursbiz-star-grad" x1="34" y1="4" x2="42" y2="12" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>

        {/* App Icon Container Gradient */}
        <linearGradient id="ursbiz-bg-grad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0F172A" />
          <stop offset="50%" stopColor="#1E293B" />
          <stop offset="100%" stopColor="#0A192F" />
        </linearGradient>
      </defs>

      {/* App-icon background badge */}
      {isAppIcon && (
        <>
          <rect width="48" height="48" rx="12" fill="url(#ursbiz-bg-grad)" />
          <rect
            x="0.75"
            y="0.75"
            width="46.5"
            height="46.5"
            rx="11.25"
            stroke="#38BDF8"
            strokeOpacity="0.25"
            strokeWidth="1.5"
          />
        </>
      )}

      {/* Outer Stylized "U" Track */}
      <path
        d="M10 10V27C10 34.1797 15.8203 40 23 40H25C32.1797 40 38 34.1797 38 27V18"
        stroke={uStroke}
        strokeWidth="4.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Analytics Bar 1 (Foundation / Entry) */}
      <rect
        x="15.5"
        y="25"
        width="4"
        height="9"
        rx="2"
        fill={bar1Fill}
      />

      {/* Analytics Bar 2 (Growth / Predict) */}
      <rect
        x="22"
        y="19"
        width="4"
        height="15"
        rx="2"
        fill={bar2Fill}
      />

      {/* Analytics Bar 3 (Scale / Succeed) */}
      <rect
        x="28.5"
        y="13"
        width="4"
        height="21"
        rx="2"
        fill={bar3Fill}
      />

      {/* AI Intelligence Sparkle Star at the upper-right apex */}
      <path
        d="M38 3 C38 6.866 39.634 8.5 43.5 8.5 C39.634 8.5 38 10.134 38 14 C38 10.134 36.366 8.5 32.5 8.5 C36.366 8.5 38 6.866 38 3 Z"
        fill={starFill}
      />
    </svg>
  );
}

/**
 * URSBiz Enterprise Visual Identity Lockup.
 *
 * Supports:
 * - primary: [Icon] + URSBiz + "Enterprise SaaS Business Intelligence Platform"
 * - compact: [Icon] + URSBiz
 * - icon-only: [Icon]
 * - white: For dark enterprise backgrounds
 * - monochrome: Pure single color for reports/printing
 * - blue: White on blue navbar
 * - app-icon: Badge container with glowing border
 */
export function Logo({
  variant = "compact",
  size = "md",
  withSubtitle = false,
  withTagline = false,
  className,
  textClassName,
  iconClassName,
}: LogoProps) {
  const cfg = SIZE_MAP[size];
  const isIconOnly = variant === "icon-only";
  const showSubtitle = withSubtitle || variant === "primary";

  // Color logic for wordmark
  const isWhite = variant === "white" || variant === "blue";
  const isMonochrome = variant === "monochrome";

  const ursColor = isMonochrome
    ? "text-current"
    : isWhite
    ? "text-white"
    : "text-slate-900 dark:text-slate-50";

  const bizColor = isMonochrome
    ? "text-current"
    : isWhite
    ? "text-sky-300"
    : "text-blue-600 dark:text-blue-400";

  return (
    <span
      className={cn(
        "inline-flex items-center select-none tracking-tight",
        cfg.gap,
        className,
      )}
      data-testid="ursbiz-logo"
    >
      {/* Primary Brand Icon */}
      <UrsBizIcon
        size={cfg.iconDim}
        variant={variant}
        className={iconClassName}
      />

      {/* Wordmark Lockup */}
      {!isIconOnly && (
        <span className="flex flex-col leading-none min-w-0">
          <span
            className={cn(
              "font-extrabold tracking-tight font-sans inline-flex items-baseline",
              cfg.titleSize,
              textClassName,
            )}
          >
            <span className={cn("transition-colors", ursColor)}>URS</span>
            <span className={cn("transition-colors font-black", bizColor)}>Biz</span>
          </span>

          {/* Optional Subtitle */}
          {showSubtitle && (
            <span
              className={cn(
                "pt-0.5 font-medium tracking-wide uppercase text-muted-foreground transition-colors",
                cfg.subtitleSize,
                isWhite && "text-slate-300",
              )}
            >
              Enterprise SaaS Business Intelligence
            </span>
          )}

          {/* Optional Tagline */}
          {withTagline && (
            <span
              className={cn(
                "pt-0.5 font-semibold tracking-wider uppercase text-sky-600 dark:text-sky-400",
                cfg.taglineSize,
                isWhite && "text-sky-200",
              )}
            >
              ANALYZE · PREDICT · GROW · SUCCEED
            </span>
          )}
        </span>
      )}
    </span>
  );
}

export default Logo;
