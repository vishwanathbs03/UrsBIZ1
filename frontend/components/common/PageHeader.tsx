import React from "react";
import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  /** Small category / eyebrow label rendered above the heading. */
  badge?: React.ReactNode;
  /** Main heading text. */
  title: string;
  /** Electric-blue highlighted keyword within the heading (if present). */
  highlight?: string;
  /** Explanatory description beneath the heading. */
  description?: string;
  /** Right-aligned action buttons or controls (e.g. Export, Refresh, CTA). */
  actions?: React.ReactNode;
  /** Optional secondary metadata strip or badges beneath the description. */
  metadata?: React.ReactNode;
  className?: string;
}

/**
 * Standard Dark Neon PageHeader component for UrsBiz pages.
 * Enforces visual hierarchy:
 * - Large bold white hero headings
 * - Electric-blue highlighted keywords
 * - Muted slate secondary text
 * - Action buttons slot
 */
export function PageHeader({
  badge,
  title,
  highlight,
  description,
  actions,
  metadata,
  className,
}: PageHeaderProps) {
  // If highlight is provided, split the title and emphasize the highlighted part
  const renderTitle = () => {
    if (!highlight || !title.includes(highlight)) {
      return title;
    }
    const parts = title.split(highlight);
    return (
      <>
        {parts[0]}
        <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent drop-shadow-[0_0_12px_rgba(59,130,246,0.35)]">
          {highlight}
        </span>
        {parts.slice(1).join(highlight)}
      </>
    );
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-4 pb-2 md:flex-row md:items-start md:justify-between",
        className,
      )}
    >
      <div className="flex max-w-3xl flex-col gap-1.5">
        {badge && (
          <div className="flex items-center gap-2">
            {typeof badge === "string" ? (
              <span className="shadow-xs inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-accent">
                {badge}
              </span>
            ) : (
              badge
            )}
          </div>
        )}

        <h1 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl lg:text-4xl">
          {renderTitle()}
        </h1>

        {description && (
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            {description}
          </p>
        )}

        {metadata && <div className="mt-1 flex flex-wrap items-center gap-3">{metadata}</div>}
      </div>

      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2.5 pt-1 md:pt-0">{actions}</div>
      )}
    </div>
  );
}
