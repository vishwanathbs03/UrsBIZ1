/**
 * Lightweight Accordion primitive — Sprint H6.2.
 *
 * Native-style disclosure built on <details>/<summary> for max
 * accessibility without runtime JS. Used to keep detailed analysis
 * collapsible so executive answers stay above the fold.
 */
"use client";

import { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AccordionItem {
  key: string;
  title: ReactNode;
  subtitle?: ReactNode;
  content: ReactNode;
  defaultOpen?: boolean;
}

interface AccordionProps {
  items: AccordionItem[];
  className?: string;
}

export function Accordion({ items, className }: AccordionProps) {
  return (
    <div className={cn("flex flex-col divide-y divide-border rounded-lg border border-border", className)}>
      {items.map((item) => (
        <details
          key={item.key}
          className="group px-4 py-3"
          {...(item.defaultOpen ? { open: true } : {})}
        >
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 [&::-webkit-details-marker]:hidden">
            <div className="flex min-w-0 flex-col">
              <span className="text-sm font-semibold text-foreground">{item.title}</span>
              {item.subtitle && (
                <span className="text-xs text-muted-foreground">{item.subtitle}</span>
              )}
            </div>
            <ChevronDown
              className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>
          <div className="pt-3 text-sm text-foreground">{item.content}</div>
        </details>
      ))}
    </div>
  );
}
