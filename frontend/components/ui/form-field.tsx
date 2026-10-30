"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface FormFieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Pairs a label, control, error message, and optional hint.
 * The control is expected to forward the id down to its input.
 */
export function FormField({
  id,
  label,
  error,
  hint,
  required,
  children,
  className,
}: FormFieldProps) {
  const errorId = error ? `${id}-error` : undefined;
  const hintId = hint ? `${id}-hint` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <label
        htmlFor={id}
        className="text-sm font-medium text-foreground"
      >
        {label}
        {required && (
          <span aria-hidden="true" className="ml-0.5 text-destructive">
            *
          </span>
        )}
      </label>
      <FormFieldContext.Provider value={{ id, describedBy, invalid: Boolean(error) }}>
        {children}
      </FormFieldContext.Provider>
      {hint && !error && (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

interface FormFieldContextValue {
  id: string;
  describedBy?: string;
  invalid: boolean;
}

const FormFieldContext = React.createContext<FormFieldContextValue | null>(null);

export function useFormField(): FormFieldContextValue {
  const ctx = React.useContext(FormFieldContext);
  if (!ctx) {
    throw new Error("useFormField must be used inside <FormField>.");
  }
  return ctx;
}

export function useOptionalFormField(): FormFieldContextValue | null {
  return React.useContext(FormFieldContext);
}
