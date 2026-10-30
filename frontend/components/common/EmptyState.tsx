import { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Preset illustrations used across the empty states. Each one
 * is a small inline SVG that uses `currentColor` so it picks
 * up the surrounding text colour. The shared container is
 * `relative w-32 h-32 text-primary/65` (or larger) so the
 * illustrations sit centred above the title.
 */
export type EmptyIllustration =
  | "inbox"
  | "bell"
  | "lightbulb"
  | "clipboard"
  | "chat"
  | "briefcase"
  | "chart"
  | "rocket"
  | "trending-up"
  | "scroll"
  | "building"
  | "shield"
  | "compass"
  | "search"
  | "sparkles";

interface EmptyStateProps {
  title: string;
  description?: string;
  /** Single CTA button. */
  actionLabel?: string;
  onAction?: () => void;
  /** Secondary CTA button (e.g. "Learn more"). */
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  /** Legacy small icon chip — rendered above the illustration if both are provided. */
  icon?: React.ReactNode;
  /** Rich inline SVG illustration preset. */
  illustration?: EmptyIllustration | ReactNode;
  /** Size of the illustration. Defaults to "md". */
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * Generic empty state for lists, dashboards, and placeholder screens.
 * Each instance combines an illustrative SVG (preset or custom), a
 * title, an explanatory description, and up to two CTA buttons.
 * The styling intentionally mirrors the rest of the design system
 * (rounded card, dashed border, primary tint) so it slots into any
 * surface without further configuration.
 */
export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
  icon,
  illustration,
  size = "md",
  className,
}: EmptyStateProps) {
  const illustrationNode =
    illustration === undefined
      ? null
      : typeof illustration === "string"
        ? renderIllustration(illustration as EmptyIllustration, size)
        : illustration;

  const sizeClasses = size === "lg" ? "size-40" : size === "sm" ? "size-20" : "size-32";

  return (
    <div
      className={cn(
        "shadow-soft flex flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-card/70 px-6 py-16 text-center backdrop-blur-md transition-colors hover:border-primary/40",
        className,
      )}
    >
      {icon && (
        <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-secondary text-muted-foreground">
          {icon}
        </div>
      )}
      {illustrationNode && (
        <div
          className={cn("mb-4 text-primary/65 dark:text-primary/55", sizeClasses)}
          aria-hidden="true"
        >
          {illustrationNode}
        </div>
      )}
      {!illustrationNode && !icon && (
        <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-secondary text-muted-foreground">
          <Inbox className="size-6" aria-hidden="true" />
        </div>
      )}
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
      {(actionLabel && onAction) || (secondaryActionLabel && onSecondaryAction) ? (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {actionLabel && onAction && (
            <Button onClick={onAction} size="default">
              {actionLabel}
            </Button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <Button onClick={onSecondaryAction} variant="outline" size="default">
              {secondaryActionLabel}
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Illustration library
// --------------------------------------------------------------------------- //

function renderIllustration(name: EmptyIllustration, _size: "sm" | "md" | "lg"): ReactNode {
  // size param is reserved for future size-aware variants; the
  // current presets scale to the container via Tailwind classes.
  void _size;
  // All illustrations sit in a 64x64 viewBox and scale to the
  // enclosing container. Keep the line-art consistent across
  // presets so the empty states look like one family.
  switch (name) {
    case "inbox":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M16 18 L16 44 L48 44 L48 22 L42 16 L16 16 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M16 16 L42 16 L48 22"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path d="M22 36 L42 36" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M22 30 L36 30" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      );
    case "bell":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M32 14 C24 14 22 20 22 26 L22 36 L18 42 L46 42 L42 36 L42 26 C42 20 40 14 32 14 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M28 46 C28 49 30 51 32 51 C34 51 36 49 36 46"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            fill="none"
          />
          <circle cx="32" cy="10" r="2.5" fill="currentColor" />
        </svg>
      );
    case "lightbulb":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M32 14 C24 14 20 20 20 26 C20 30 22 33 25 35 L25 40 L39 40 L39 35 C42 33 44 30 44 26 C44 20 40 14 32 14 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M27 44 L37 44 M28 48 L36 48"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <path d="M32 8 L32 14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M50 16 L46 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M14 16 L18 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      );
    case "clipboard":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <rect
            x="16"
            y="14"
            width="32"
            height="40"
            rx="3"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
          <rect
            x="24"
            y="10"
            width="16"
            height="8"
            rx="2"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
          <path
            d="M22 28 L42 28 M22 36 L42 36 M22 44 L34 44"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      );
    case "chat":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M14 18 L46 18 C49 18 50 19 50 22 L50 40 C50 43 49 44 46 44 L26 44 L18 52 L20 44 L14 44 C11 44 10 43 10 40 L10 22 C10 19 11 18 14 18 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <circle cx="22" cy="31" r="2" fill="currentColor" />
          <circle cx="30" cy="31" r="2" fill="currentColor" />
          <circle cx="38" cy="31" r="2" fill="currentColor" />
        </svg>
      );
    case "briefcase":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <rect
            x="10"
            y="20"
            width="44"
            height="32"
            rx="3"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
          <path
            d="M26 20 L26 16 C26 14 27 12 30 12 L34 12 C37 12 38 14 38 16 L38 20"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path d="M10 32 L54 32" stroke="currentColor" strokeWidth="2.5" />
          <path
            d="M32 32 L36 36 L40 32"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      );
    case "chart":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path d="M10 50 L54 50" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M10 50 L10 12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <rect
            x="18"
            y="34"
            width="6"
            height="16"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
          <rect
            x="29"
            y="26"
            width="6"
            height="24"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
          <rect
            x="40"
            y="20"
            width="6"
            height="30"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
        </svg>
      );
    case "rocket":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M32 8 C36 12 40 20 40 28 L40 40 L24 40 L24 28 C24 20 28 12 32 8 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <circle cx="32" cy="24" r="3" stroke="currentColor" strokeWidth="2.5" fill="none" />
          <path
            d="M24 38 L18 44 L20 50 L24 46"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M40 38 L46 44 L44 50 L40 46"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M28 50 L32 56 L36 50"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      );
    case "trending-up":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M10 50 L24 32 L36 42 L54 18"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M44 18 L54 18 L54 28"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <circle cx="54" cy="18" r="3" stroke="currentColor" strokeWidth="2.5" fill="none" />
        </svg>
      );
    case "scroll":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M14 14 L46 14 C50 14 52 16 52 20 L52 46 C52 50 50 52 46 52 L18 52"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M14 14 C12 14 10 16 10 20 L10 46 C10 50 12 52 14 52 L18 52"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M20 24 L46 24 M20 32 L46 32 M20 40 L38 40"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      );
    case "building":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <rect
            x="14"
            y="10"
            width="36"
            height="48"
            rx="2"
            stroke="currentColor"
            strokeWidth="2.5"
            fill="none"
          />
          <path d="M14 24 L50 24" stroke="currentColor" strokeWidth="2.5" />
          <path d="M14 38 L50 38" stroke="currentColor" strokeWidth="2.5" />
          <rect
            x="20"
            y="16"
            width="6"
            height="6"
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
          />
          <rect
            x="38"
            y="16"
            width="6"
            height="6"
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
          />
          <rect
            x="20"
            y="30"
            width="6"
            height="6"
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
          />
          <rect
            x="38"
            y="30"
            width="6"
            height="6"
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M28 58 L28 46 L36 46 L36 58"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      );
    case "shield":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M32 8 L52 14 L52 32 C52 44 44 52 32 56 C20 52 12 44 12 32 L12 14 L32 8 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M24 32 L30 38 L42 26"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      );
    case "compass":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <circle cx="32" cy="32" r="22" stroke="currentColor" strokeWidth="2.5" fill="none" />
          <path
            d="M32 16 L36 26 L32 32 L28 26 L32 16 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M32 48 L28 38 L32 32 L36 38 L32 48 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <circle cx="32" cy="32" r="2" fill="currentColor" />
        </svg>
      );
    case "search":
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <circle cx="28" cy="28" r="14" stroke="currentColor" strokeWidth="2.5" fill="none" />
          <path d="M40 40 L52 52" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      );
    case "sparkles":
    default:
      return (
        <svg viewBox="0 0 64 64" fill="none" className="size-full">
          <path
            d="M32 12 L34 26 L48 28 L34 30 L32 44 L30 30 L16 28 L30 26 L32 12 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M48 40 L49 46 L55 47 L49 48 L48 54 L47 48 L41 47 L47 46 L48 40 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
          <path
            d="M16 40 L17 46 L23 47 L17 48 L16 54 L15 48 L9 47 L15 46 L16 40 Z"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      );
  }
}
