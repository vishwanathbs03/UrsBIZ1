import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

/**
 * Friendly error fallback for both route-level errors and inline
 * component failures. Honors role="alert" so screen readers announce
 * the error immediately.
 */
export function ErrorState({
  title = "Something went wrong",
  description = "An unexpected error occurred. Please try again.",
  actionLabel = "Try again",
  onAction,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "border-destructive/30 shadow-soft flex flex-col items-center justify-center rounded-xl border bg-card/90 px-6 py-14 text-center backdrop-blur-md",
        "border-rose-500/30 shadow-[0_0_24px_-4px_rgba(244,63,94,0.15)]",
        className,
      )}
    >
      <div className="bg-destructive/15 border-destructive/30 mb-4 flex size-12 items-center justify-center rounded-xl border text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.25)]">
        <AlertTriangle className="size-6" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-bold text-foreground">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">{description}</p>
      {onAction && (
        <Button
          onClick={onAction}
          variant="outline"
          className="mt-6 border-border/80 hover:border-primary/50"
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
