"use client";

import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import { Languages } from "lucide-react";

interface LanguageSwitcherProps {
  className?: string;
  showIcon?: boolean;
}

export function LanguageSwitcher({ className, showIcon = true }: LanguageSwitcherProps) {
  const { language, setLanguage } = useLanguage();

  return (
    <div
      role="group"
      aria-label="Language selector"
      className={cn(
        "inline-flex items-center rounded-lg border border-border/70 bg-background/60 p-0.5 text-xs shadow-xs backdrop-blur-xs",
        className,
      )}
    >
      {showIcon && (
        <span className="flex size-7 items-center justify-center text-muted-foreground/70" aria-hidden="true">
          <Languages className="size-3.5" />
        </span>
      )}
      <button
        type="button"
        onClick={() => setLanguage("en")}
        aria-pressed={language === "en"}
        aria-label="English language"
        className={cn(
          "rounded-md px-2 py-1 font-medium transition-all",
          language === "en"
            ? "bg-primary text-primary-foreground shadow-xs font-semibold"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLanguage("kn")}
        aria-pressed={language === "kn"}
        aria-label="Kannada language (ಕನ್ನಡ)"
        className={cn(
          "rounded-md px-2 py-1 font-medium transition-all font-kannada",
          language === "kn"
            ? "bg-primary text-primary-foreground shadow-xs font-semibold"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        ಕನ್ನಡ
      </button>
    </div>
  );
}
