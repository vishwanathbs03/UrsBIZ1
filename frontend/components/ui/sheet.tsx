"use client";

/**
 * Sheet — bespoke slide-over panel primitive (Sprint 23).
 *
 * Built without Radix so the assistant / dashboard pages do not
 * need to install @radix-ui/react-dialog. Behaviour:
 *
 *   - Renders a backdrop (`fixed inset-0 bg-black/50`).
 *   - Panel slides in from the right (`max-w-sm sm:max-w-md`).
 *   - Closes on backdrop click or Escape.
 *   - Locks background scroll while open.
 *   - Light focus management: focuses the close button on open,
 *     restores the previously focused element on close.
 *
 * Use as:
 *
 *   <Sheet open={isOpen} onOpenChange={setOpen}>
 *     <SheetContent title="Profile">
 *       ...panel body...
 *     </SheetContent>
 *   </Sheet>
 *
 * `SheetContent` requires a `title` for the accessible label and
 * a `closeButtonLabel` for the screen-reader-only close button.
 */
import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

const SheetContext = React.createContext<{
  onClose: () => void;
  titleId: string;
} | null>(null);

function useSheet(): {
  onClose: () => void;
  titleId: string;
} {
  const ctx = React.useContext(SheetContext);
  if (!ctx) {
    throw new Error("SheetContent must be rendered inside <Sheet>.");
  }
  return ctx;
}

export function Sheet({ open, onOpenChange, children }: SheetProps) {
  const titleId = React.useId();
  const onClose = React.useCallback(() => onOpenChange(false), [onOpenChange]);

  // Track mount so we can safely call createPortal on the client only.
  // SSR rendering never reaches this branch because open starts false.
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Background scroll lock + focus restore.
  React.useEffect(() => {
    if (!open) return;
    const previousActive = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
      previousActive?.focus?.();
    };
  }, [open]);

  // Escape closes the sheet.
  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !mounted) return null;

  // Render via a portal so the dialog escapes any ancestor that creates
  // a containing block for `position: fixed` (e.g. the navbar header
  // uses `backdrop-blur-md`, which makes the dialog otherwise sized to
  // the navbar's bounding box instead of the viewport).
  const dialog = (
    <SheetContext.Provider value={{ onClose, titleId }}>
      <div
        className="fixed inset-0 z-[60] flex"
        aria-modal="true"
        role="dialog"
        aria-labelledby={titleId}
      >
        <div
          role="presentation"
          aria-hidden="true"
          onClick={onClose}
          className="absolute inset-0 bg-black/50"
        />
        <div
          className={cn(
            "relative ml-auto flex h-full w-full max-w-sm flex-col gap-4 border-l border-border bg-card p-6 shadow-2xl",
            "sm:max-w-md",
          )}
        >
          {children}
        </div>
      </div>
    </SheetContext.Provider>
  );

  return createPortal(dialog, document.body);
}

interface SheetContentProps {
  title: string;
  children: React.ReactNode;
}

/**
 * SheetContent — the right-side panel body.
 *
 * Renders the title, a close button (X icon), and the children.
 * The title is the dialog's accessible label.
 */
export function SheetContent({ title, children }: SheetContentProps) {
  const { onClose, titleId } = useSheet();
  const closeRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    // Focus the close button on mount; matches the bespoke
    // focus-restoration contract documented on the Sheet primitive.
    closeRef.current?.focus();
  }, []);

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <h2
          id={titleId}
          className="text-lg font-semibold leading-none tracking-tight text-foreground"
        >
          {title}
        </h2>
        <Button
          ref={closeRef}
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close"
        >
          <X className="size-5" aria-hidden="true" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">{children}</div>
    </>
  );
}
