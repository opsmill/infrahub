import React from "react";

import { type DateInput, formatDate, formatRelativeTimeFromNow } from "@/shared/utils/date";

// Resolved date preferences a renderer needs. null = no preference → browser default. Lives in
// `shared` (no `entities` dependency); filled by the entities-layer date-preferences-provider.
export interface ResolvedDatePreferences {
  pattern: string | null;
  timezone: string | null;
}

// null = no provider mounted → consumers fall back to browser-locale formatting.
export const DatePreferencesContext = React.createContext<ResolvedDatePreferences | null>(null);

export type DateVariant = "datetime" | "date" | "relative";

function formatWithLocale(date: DateInput, variant: DateVariant, timezone: string | null): string {
  const d = new Date(date);
  const options: Intl.DateTimeFormatOptions =
    variant === "date" ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" };
  if (timezone) {
    options.timeZone = timezone;
  }
  return d.toLocaleString(undefined, options);
}

export interface UseFormatDateResult {
  formatDate: (date: DateInput, variant?: DateVariant) => string;
  pattern: string | null;
  timezone: string | null;
}

/** Renders dates against the active preferences. `"date"` reuses the datetime pattern's date part. */
export function useFormatDate(): UseFormatDateResult {
  const resolved = React.use(DatePreferencesContext);
  const pattern = resolved?.pattern ?? null;
  const timezone = resolved?.timezone ?? null;

  const boundFormat = (date: DateInput, variant: DateVariant = "datetime"): string => {
    if (variant === "relative") {
      return formatRelativeTimeFromNow(date);
    }

    if (!pattern) {
      return formatWithLocale(date, variant, timezone);
    }

    if (variant === "date") {
      const datePattern = dateOnlyPattern(pattern);
      return datePattern
        ? formatDate(date, { pattern: datePattern, timezone })
        : formatWithLocale(date, "date", timezone);
    }

    return formatDate(date, { pattern, timezone });
  };

  return { formatDate: boundFormat, pattern, timezone };
}

// Drops everything from the first time token onward, e.g. "yyyy-MM-dd HH:mm" → "yyyy-MM-dd".
function dateOnlyPattern(pattern: string): string {
  const timeTokenIndex = pattern.search(/[HhmsaXxOz]/);
  const dateSlice = timeTokenIndex === -1 ? pattern : pattern.slice(0, timeTokenIndex);
  return dateSlice.replace(/['T\s\-/.,:]+$/, "").trim();
}
