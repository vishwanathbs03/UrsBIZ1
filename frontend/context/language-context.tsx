"use client";

import React, { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { translations, type SupportedLanguage, type Translations } from "@/i18n/translations";

const STORAGE_KEY = "ursbiz.language";

interface LanguageContextValue {
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  t: (key: string, fallback?: string) => string;
  dictionary: Translations;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<SupportedLanguage>("en");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "en" || stored === "kn") {
        setLanguageState(stored);
      }
    } catch {
      // Ignore localStorage errors (e.g. private browsing)
    }
    setMounted(true);
  }, []);

  const setLanguage = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
      document.documentElement.lang = lang;
    } catch {
      // Ignore localStorage errors
    }
  };

  const dictionary = translations[language] || translations.en;

  const t = (path: string, fallback?: string): string => {
    const keys = path.split(".");
    let current: unknown = dictionary;
    for (const key of keys) {
      if (current && typeof current === "object" && key in current) {
        current = (current as Record<string, unknown>)[key];
      } else {
        // Fallback to English dictionary if missing in target
        let enCurrent: unknown = translations.en;
        for (const enKey of keys) {
          if (enCurrent && typeof enCurrent === "object" && enKey in enCurrent) {
            enCurrent = (enCurrent as Record<string, unknown>)[enKey];
          } else {
            return fallback ?? path;
          }
        }
        return typeof enCurrent === "string" ? enCurrent : (fallback ?? path);
      }
    }
    return typeof current === "string" ? current : (fallback ?? path);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, dictionary }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    // Return a safe fallback for SSR or pre-mount render
    return {
      language: "en",
      setLanguage: () => {},
      t: (path: string, fallback?: string) => fallback ?? path,
      dictionary: translations.en,
    };
  }
  return ctx;
}
