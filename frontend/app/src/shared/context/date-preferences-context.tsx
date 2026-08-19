import React from "react";

import { type DateInput, formatRelativeTimeFromNow, formatWithPattern } from "@/shared/utils/date";

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
  if (Number.isNaN(d.getTime())) {
    return String(date);
  }
  const options: Intl.DateTimeFormatOptions =
    variant === "date" ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" };
  if (timezone) {
    try {
      return d.toLocaleString(undefined, { ...options, timeZone: timezone });
    } catch {
      // Unknown timezone on this browser → render in the browser's local zone.
    }
  }
  return d.toLocaleString(undefined, options);
}

export interface UseFormatDateResult {
  formatDate: (date: DateInput, variant?: DateVariant) => string;
  /** Preferred zone, exposed for the rare caller (e.g. an explicit-pattern escape hatch)
   * that formats a date itself and still needs to honour the user's timezone. */
  timezone: string | null;
}

/**
 * Renders a date against a resolved preference pair; `"date"` reuses the datetime pattern's date part.
 * Only for a pair that is not the active one (preferences still being edited) — otherwise use the hook.
 */
export function formatWithPreferences(
  date: DateInput,
  { pattern, timezone }: ResolvedDatePreferences,
  variant: DateVariant = "datetime"
): string {
  if (variant === "relative") {
    return formatRelativeTimeFromNow(date);
  }

  if (!pattern) {
    return formatWithLocale(date, variant, timezone);
  }

  if (variant === "date") {
    const datePattern = dateOnlyPattern(pattern);
    return datePattern
      ? formatWithPattern(date, { pattern: datePattern, timezone })
      : formatWithLocale(date, "date", timezone);
  }

  return formatWithPattern(date, { pattern, timezone });
}

/** Renders dates against the active preferences. */
export function useFormatDate(): UseFormatDateResult {
  const resolved = React.use(DatePreferencesContext);
  const preferences: ResolvedDatePreferences = {
    pattern: resolved?.pattern ?? null,
    timezone: resolved?.timezone ?? null,
  };

  return {
    formatDate: (date, variant) => formatWithPreferences(date, preferences, variant),
    timezone: preferences.timezone,
  };
}

// Drops everything from the first time token onward, e.g. "yyyy-MM-dd HH:mm" → "yyyy-MM-dd".
// Exported for direct testing of the fragile quoted-token / day-period presets.
export function dateOnlyPattern(pattern: string): string {
  const timeTokenIndex = pattern.search(/[HhmsaXxOz]/);
  const dateSlice = timeTokenIndex === -1 ? pattern : pattern.slice(0, timeTokenIndex);
  // The trailing character class already strips whitespace, so no separate trim is needed.
  return dateSlice.replace(/['T\s\-/.,:]+$/, "");
}
