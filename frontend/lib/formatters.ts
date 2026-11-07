/**
 * UrsBiz MSME Formatting Library (Phase 6.29).
 *
 * Provides deterministic, locale-sensitive formatters for:
 * 1. Indian Rupee (INR / ₹) with Indian numbering system grouping (lakhs/crores)
 *    and bilingual compact representations (English and Kannada).
 * 2. Standardized calendar dates adhering strictly to Indian business convention (DD-MM-YYYY),
 *    with robust timezone parsing preventing date-boundary shifts.
 * 3. Relative time with authentic grammatical pluralization in English and Kannada.
 * 4. Operational durations (DSO) and percentages.
 */

export type SupportedLanguage = "en" | "kn";

export interface FormatINROptions {
  /** If true, formats numbers into compact units (e.g., ₹12.5 L / ₹12.5 ಲಕ್ಷ). */
  compact?: boolean;
  /** Language context ('en' | 'kn'). Defaults to 'en'. */
  language?: SupportedLanguage;
  /** Decimal places to display. Defaults to 2 (or 1 for compact). */
  decimals?: number;
  /** Whether to prefix with the ₹ symbol. Defaults to true. */
  showSymbol?: boolean;
  /** Fallback string if value is null, undefined, or NaN. Defaults to '—'. */
  fallback?: string;
}

export interface FormatDateOptions {
  /** Format style:
   * - 'short': DD-MM-YYYY (e.g., 15-05-2026)
   * - 'datetime': DD-MM-YYYY, HH:mm (e.g., 15-05-2026, 14:30)
   * - 'long': DD Month YYYY (e.g., 15 May 2026 / 15 ಮೇ 2026)
   * - 'monthYear': Month YYYY (e.g., May 2026 / ಮೇ 2026)
   */
  format?: "short" | "datetime" | "long" | "monthYear";
  /** Language context ('en' | 'kn'). Defaults to 'en'. */
  language?: SupportedLanguage;
  /** Fallback string if date is invalid or null. Defaults to '—'. */
  fallback?: string;
}

const KANNADA_MONTHS = [
  "ಜನವರಿ",
  "ಫೆಬ್ರವರಿ",
  "ಮಾರ್ಚ್",
  "ಏಪ್ರಿಲ್",
  "ಮೇ",
  "ಜೂನ್",
  "ಜುಲೈ",
  "ಆಗಸ್ಟ್",
  "ಸೆಪ್ಟೆಂಬರ್",
  "ಅಕ್ಟೋಬರ್",
  "ನವೆಂಬರ್",
  "ಡಿಸೆಂಬರ್",
];

const ENGLISH_MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/**
 * Format a numeric amount in Indian Rupees (INR / ₹) conforming to Indian numbering.
 * Supports compact display (Lakhs / Crores) in English and Kannada, negative handling,
 * and edge-case zero formatting.
 */
export function formatINR(
  amount: number | null | undefined,
  options: FormatINROptions = {},
): string {
  const {
    compact = false,
    language = "en",
    decimals,
    showSymbol = true,
    fallback = "—",
  } = options;

  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return fallback;
  }

  // Handle clean zero
  if (amount === 0 || Object.is(amount, -0)) {
    const symbol = showSymbol ? "₹" : "";
    if (compact) {
      return `${symbol}0`;
    }
    const fixedZero = (decimals ?? 2) > 0 ? `0.${"0".repeat(decimals ?? 2)}` : "0";
    return `${symbol}${fixedZero}`;
  }

  const symbol = showSymbol ? "₹" : "";
  const isNegative = amount < 0;
  const absValue = Math.abs(amount);

  if (compact) {
    const compactDecimals = decimals ?? (absValue >= 100 ? 1 : 2);
    let scaled = absValue;
    let unit = "";

    if (absValue >= 1_00_00_000) {
      scaled = absValue / 1_00_00_000;
      unit = language === "kn" ? " ಕೋಟಿ" : " Cr";
    } else if (absValue >= 1_00_000) {
      scaled = absValue / 1_00_000;
      unit = language === "kn" ? " ಲಕ್ಷ" : " L";
    } else if (absValue >= 1_000) {
      scaled = absValue / 1_000;
      unit = language === "kn" ? " ಸಾ" : " k";
    }

    const formattedScaled = scaled.toFixed(compactDecimals);
    const sign = isNegative ? "-" : "";
    return `${sign}${symbol}${formattedScaled}${unit}`.trim();
  }

  // Full Indian numbering formatting
  const fixedDecimals = decimals ?? 2;
  const fixedString = absValue.toFixed(fixedDecimals);
  const [integerPart, decimalPart] = fixedString.split(".");

  // Format integer part with Indian grouping: last 3 digits, then groups of 2 digits
  const lastThree = integerPart.slice(-3);
  const otherDigits = integerPart.slice(0, -3);
  let formattedInteger = lastThree;
  if (otherDigits.length > 0) {
    const formattedOther = otherDigits.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    formattedInteger = `${formattedOther},${lastThree}`;
  }

  const sign = isNegative ? "-" : "";
  const decimalFormatted = fixedDecimals > 0 ? `.${decimalPart}` : "";
  return `${sign}${symbol}${formattedInteger}${decimalFormatted}`;
}

/**
 * Parses any date representation safely.
 * Includes timezone-safe extraction for date-only strings (e.g., 'YYYY-MM-DD')
 * to eliminate day-boundary shifts across timezones.
 */
function parseDateParts(
  input: string | number | Date | null | undefined,
): { year: number; monthIdx: number; day: number; hours: number; minutes: number } | null {
  if (!input) return null;

  if (typeof input === "string") {
    const trimmed = input.trim();
    if (!trimmed) return null;

    // Check for date-only string: YYYY-MM-DD
    const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
    if (dateOnlyMatch) {
      const year = parseInt(dateOnlyMatch[1], 10);
      const monthIdx = parseInt(dateOnlyMatch[2], 10) - 1;
      const day = parseInt(dateOnlyMatch[3], 10);
      if (monthIdx >= 0 && monthIdx < 12 && day >= 1 && day <= 31) {
        return { year, monthIdx, day, hours: 0, minutes: 0 };
      }
    }
  }

  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return null;

  return {
    year: d.getFullYear(),
    monthIdx: d.getMonth(),
    day: d.getDate(),
    hours: d.getHours(),
    minutes: d.getMinutes(),
  };
}

/**
 * Format date adhering strictly to Indian business convention (DD-MM-YYYY).
 */
export function formatDate(
  dateInput: string | number | Date | null | undefined,
  options: FormatDateOptions = {},
): string {
  const { format = "short", language = "en", fallback = "—" } = options;
  const parts = parseDateParts(dateInput);
  if (!parts) return fallback;

  const dayStr = String(parts.day).padStart(2, "0");
  const monthNum = String(parts.monthIdx + 1).padStart(2, "0");
  const yearStr = String(parts.year);
  const hoursStr = String(parts.hours).padStart(2, "0");
  const minutesStr = String(parts.minutes).padStart(2, "0");

  switch (format) {
    case "short":
      return `${dayStr}-${monthNum}-${yearStr}`;
    case "datetime":
      return `${dayStr}-${monthNum}-${yearStr}, ${hoursStr}:${minutesStr}`;
    case "long": {
      const monthName =
        language === "kn" ? KANNADA_MONTHS[parts.monthIdx] : ENGLISH_MONTHS[parts.monthIdx];
      return `${dayStr} ${monthName} ${yearStr}`;
    }
    case "monthYear": {
      const monthName =
        language === "kn" ? KANNADA_MONTHS[parts.monthIdx] : ENGLISH_MONTHS[parts.monthIdx];
      return `${monthName} ${yearStr}`;
    }
    default:
      return `${dayStr}-${monthNum}-${yearStr}`;
  }
}

/**
 * Formats a percentage value with optional sign.
 */
export function formatPercentage(
  value: number | null | undefined,
  options: { includeSign?: boolean; decimals?: number; fallback?: string } = {},
): string {
  const { includeSign = false, decimals = 1, fallback = "—" } = options;
  if (value === null || value === undefined || Number.isNaN(value)) {
    return fallback;
  }
  const sign = includeSign && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Formats DSO (Days Sales Outstanding) or working capital cycle in English or Kannada,
 * strictly honoring singular vs. plural grammar.
 */
export function formatDSO(
  days: number | null | undefined,
  language: SupportedLanguage = "en",
  fallback = "—",
): string {
  if (days === null || days === undefined || Number.isNaN(days)) {
    return fallback;
  }
  const rounded = Math.round(days);
  if (language === "kn") {
    // Grammatical singular vs plural: 1 ದಿನ vs 2+ ದಿನಗಳು
    return rounded === 1 ? "1 ದಿನ" : `${rounded} ದಿನಗಳು`;
  }
  return rounded === 1 ? "1 day" : `${rounded} days`;
}

/**
 * Formats a relative timestamp in English or Kannada with authentic grammatical
 * singular and plural declensions (e.g., '1 ಗಂಟೆಯ ಹಿಂದೆ' vs '2 ಗಂಟೆಗಳ ಹಿಂದೆ').
 */
export function formatRelativeTime(
  dateInput: string | number | Date | null | undefined,
  language: SupportedLanguage = "en",
): string {
  if (!dateInput) return "—";
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (Number.isNaN(d.getTime())) return "—";

  const now = Date.now();
  const diffMs = now - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (language === "kn") {
    if (diffMin < 1) return "ಈಗಷ್ಟೇ";
    // Minute singular/plural
    if (diffMin === 1) return "1 ನಿಮಿಷದ ಹಿಂದೆ";
    if (diffMin < 60) return `${diffMin} ನಿಮಿಷಗಳ ಹಿಂದೆ`;
    // Hour singular/plural: 1 ಗಂಟೆಯ ಹಿಂದೆ vs X ಗಂಟೆಗಳ ಹಿಂದೆ
    if (diffHours === 1) return "1 ಗಂಟೆಯ ಹಿಂದೆ";
    if (diffHours < 24) return `${diffHours} ಗಂಟೆಗಳ ಹಿಂದೆ`;
    // Day singular/plural: ನಿನ್ನೆ / 1 ದಿನದ ಹಿಂದೆ vs X ದಿನಗಳ ಹಿಂದೆ
    if (diffDays === 1) return "ನಿನ್ನೆ";
    if (diffDays < 30) return `${diffDays} ದಿನಗಳ ಹಿಂದೆ`;
    return formatDate(d, { format: "short", language: "kn" });
  }

  if (diffMin < 1) return "Just now";
  if (diffMin === 1) return "1m ago";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHours === 1) return "1h ago";
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 30) return `${diffDays}d ago`;
  return formatDate(d, { format: "short", language: "en" });
}
