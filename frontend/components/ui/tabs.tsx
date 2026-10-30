/**
 * Lightweight Tabs primitive — Sprint H6.2.
 *
 * Zero dependencies (no Radix). Renders a tablist of buttons that
 * switch the visibility of associated panels. Accessibility:
 *   - role="tablist" / role="tab" / role="tabpanel"
 *   - aria-selected on the active tab
 *   - arrow-key navigation between tabs (Left/Right)
 *   - tabindex=0 only on the active tab (roving tabindex)
 *   - Tab key moves focus into the panel
 *
 * Kept in-house so we don't pull in @radix-ui/react-tabs for the
 * executive pages.
 */
"use client";

import {
  KeyboardEvent,
  ReactNode,
  useCallback,
  useId,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";

export interface TabItem {
  key: string;
  label: string;
  icon?: ReactNode;
  content: ReactNode;
  /** Optional badge shown next to the label. */
  badge?: ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  /** Initial active key. Defaults to the first tab. */
  defaultKey?: string;
  /** Optional controlled value + change handler. */
  value?: string;
  onChange?: (key: string) => void;
  /** Layout variant. */
  variant?: "underline" | "pill";
  className?: string;
}

export function Tabs({
  tabs,
  defaultKey,
  value,
  onChange,
  variant = "underline",
  className,
}: TabsProps) {
  const initial = defaultKey ?? tabs[0]?.key ?? "";
  const isControlled = value !== undefined;
  const [internal, setInternal] = useState(initial);
  const active = isControlled ? value! : internal;
  const baseId = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const setActive = useCallback(
    (key: string) => {
      if (!isControlled) setInternal(key);
      onChange?.(key);
    },
    [isControlled, onChange],
  );

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
      let next = -1;
      if (e.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (e.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = tabs.length - 1;
      if (next >= 0) {
        e.preventDefault();
        const key = tabs[next].key;
        setActive(key);
        refs.current[key]?.focus();
      }
    },
    [tabs, setActive],
  );

  const activeIdx = Math.max(
    0,
    tabs.findIndex((t) => t.key === active),
  );
  const activeTab = tabs[activeIdx];

  return (
    <div className={className}>
      <div
        role="tablist"
        aria-label="Sections"
        className={cn(
          "flex w-full items-center gap-1 overflow-x-auto",
          variant === "underline"
            ? "border-b border-border"
            : "rounded-lg bg-secondary/40 p-1",
        )}
      >
        {tabs.map((tab, idx) => {
          const selected = tab.key === active;
          return (
            <button
              key={tab.key}
              ref={(el) => {
                refs.current[tab.key] = el;
              }}
              role="tab"
              type="button"
              id={`${baseId}-tab-${tab.key}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${tab.key}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(tab.key)}
              onKeyDown={(e) => onKeyDown(e, idx)}
              className={cn(
                "inline-flex shrink-0 items-center gap-2 px-3 py-2 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                variant === "underline" && cn(
                  "border-b-2 -mb-px",
                  selected
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
                ),
                variant === "pill" && cn(
                  "rounded-md",
                  selected
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                ),
              )}
            >
              {tab.icon}
              <span>{tab.label}</span>
              {tab.badge}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${activeTab?.key ?? "default"}`}
        aria-labelledby={`${baseId}-tab-${activeTab?.key ?? "default"}`}
        className="pt-4"
      >
        {activeTab?.content}
      </div>
    </div>
  );
}
