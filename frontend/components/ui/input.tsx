"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { useOptionalFormField } from "@/components/ui/form-field";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

/**
 * Bare text input. Kept minimal so the form layer controls labels,
 * errors, and hints via composition.
 *
 * When rendered inside a <FormField>, the id, aria-describedby and
 * invalid flag are wired automatically from context — callers only
 * need to spread field-register props.
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, ...props }, ref) => {
    const formCtx = useOptionalFormField();
    const ctxInvalid = formCtx?.invalid ?? false;
    const idFromCtx = formCtx?.id;
    const describedBy = formCtx?.describedBy;
    return (
      <input
        ref={ref}
        id={idFromCtx ?? props.id}
        aria-invalid={(invalid ?? ctxInvalid) || undefined}
        aria-describedby={describedBy}
        className={cn(
          "h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground",
          "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          "disabled:cursor-not-allowed disabled:opacity-60",
          (invalid || ctxInvalid) && "border-destructive focus-visible:ring-destructive",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";
