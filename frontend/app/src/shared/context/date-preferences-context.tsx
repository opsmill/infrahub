import React from "react";

import { type DateInput, formatDate, formatRelativeTimeFromNow } from "@/shared/utils/date";

/**
 * The resolved date-rendering preferences, reduced to what a renderer actually needs: a date-fns
 * `pattern` and an IANA `timezone`. Both may be null, meaning "no explicit preference — use the
 * browser default" (locale pattern / browser zone). This lives in `shared` and carries NO
 * dependency on `entities/preferences`; the provider that fills it from `useEffectivePreferences()`
 * lives in `entities/preferences` (see `date-preferences-provider.tsx`), keeping the
 * data-fetching layer out of `shared`.
 */
export interface ResolvedDatePreferences {
  /** date-fns pattern for the user's full preferred datetime, or null to use the browser locale. */
  pattern: string | null;
  /** IANA timezone to render in, or null to use the browser's local zone. */
  timezone: string | null;
}

/**
 * `null` = no provider mounted. Consumers MUST treat this as "fall back to browser-locale
 * formatting" so a component rendered outside any provider (tests, isolated stories, early
 * boot) never crashes.
 */
export const DatePreferencesContext = React.createContext<ResolvedDatePreferences | null>(null);

/** The rendering variants `useFormatDate` understands. */
export type DateVariant = "datetime" | "date" | "relative";

/**
 * Browser-locale fallback used whenever there is no explicit `pattern` (either no provider is
 * mounted, or the preference source is "default"). `dateStyle`/`timeStyle` respect the browser's
 * locale AND, when a `timezone` is resolved, that zone — so we never hardcode a pattern.
 */
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
  /** Format `date` for the given `variant` (default `"datetime"`). */
  formatDate: (date: DateInput, variant?: DateVariant) => string;
  /** The resolved pattern (null → browser locale). */
  pattern: string | null;
  /** The resolved IANA timezone (null → browser zone). */
  timezone: string | null;
}

/**
 * The single entry point components use to render dates against the active preferences. Reads
 * {@link DatePreferencesContext} (filled higher up by the entities-layer provider) and returns a
 * `formatDate(date, variant?)`:
 *
 *   - `"datetime"` (default): the user's full preferred pattern in their timezone. When no pattern
 *     is resolved (no provider, or source === "default"), falls back to the browser locale
 *     (`toLocaleString`) rather than a hardcoded pattern.
 *   - `"relative"`: "x ago" — timezone-independent, so the resolved timezone is irrelevant.
 *   - `"date"`: date-only. Derived from the SAME resolved state, then stripped to the date portion:
 *     with a pattern we keep only the leading `yyyy-MM-dd`-style date tokens (everything up to the
 *     first time token H/h/m/s and any trailing separators); without a pattern we use the locale's
 *     `dateStyle: "medium"`. This keeps date-only rendering consistent with the full datetime.
 */
export function useFormatDate(): UseFormatDateResult {
  const resolved = React.use(DatePreferencesContext);
  const pattern = resolved?.pattern ?? null;
  const timezone = resolved?.timezone ?? null;

  const boundFormat = React.useCallback(
    (date: DateInput, variant: DateVariant = "datetime"): string => {
      if (variant === "relative") {
        return formatRelativeTimeFromNow(date);
      }

      if (!pattern) {
        return formatWithLocale(date, variant, timezone);
      }

      if (variant === "date") {
        const datePattern = dateOnlyPattern(pattern);
        // A pattern with no date tokens (unlikely for our presets) leaves nothing to render;
        // fall back to the locale date so the caller still gets a date.
        return datePattern
          ? formatDate(date, { pattern: datePattern, timezone })
          : formatWithLocale(date, "date", timezone);
      }

      return formatDate(date, { pattern, timezone });
    },
    [pattern, timezone]
  );

  return { formatDate: boundFormat, pattern, timezone };
}

/**
 * Derives a date-only date-fns pattern from a full datetime pattern by dropping everything from the
 * first time token onward (H, h, m, s, a, and the timezone tokens X/x/O/z), then trimming trailing
 * separators. E.g. "yyyy-MM-dd HH:mm" → "yyyy-MM-dd", "dd/MM/yyyy HH:mm" → "dd/MM/yyyy",
 * "MM/dd/yyyy hh:mm a" → "MM/dd/yyyy". Returns "" if no date tokens remain.
 */
function dateOnlyPattern(pattern: string): string {
  const timeTokenIndex = pattern.search(/[HhmsaXxOz]/);
  const dateSlice = timeTokenIndex === -1 ? pattern : pattern.slice(0, timeTokenIndex);
  return dateSlice.replace(/['T\s\-/.,:]+$/, "").trim();
}
