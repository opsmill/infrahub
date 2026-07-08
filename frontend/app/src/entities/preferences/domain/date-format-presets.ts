// Curated date-format presets (IFC-2720). The STORED value is a semantic key (e.g. "ISO_DATETIME"),
// validated backend-side by the `DateFormat` GraphQL enum — it is NOT a date-fns pattern. Each
// client maps the key to its own renderer; here we map key -> date-fns pattern for the dropdown's
// live example (and, later, DateDisplay). The key set mirrors the backend exactly
// (backend/infrahub/core/preferences/formats.py, where the map is key -> strftime).
//
// Every preset includes date AND time. The set is deliberately limited to formats that render
// identically on every client (no locale library, no relative mode) — see
// dev/specs/2026-04-user-preferences.md.

import { format } from "date-fns";

/** Semantic date-format keys. Must stay in sync with the backend `DateFormat` enum. */
export type DateFormatKey =
  | "ISO_8601"
  | "ISO_DATETIME"
  | "ISO_DATETIME_SECONDS"
  | "EU_DATETIME"
  | "US_12H";

/** Applied when neither the user nor the organisation has set date_format (same key as backend). */
export const DEFAULT_DATE_FORMAT: DateFormatKey = "ISO_DATETIME";

interface DateFormatPresetDef {
  /** Human-facing dropdown label (the pattern itself, or a name where the pattern is unfriendly). */
  label: string;
  /** date-fns pattern this key renders with on the web client. */
  pattern: string;
}

/** Ordered semantic key -> { label, date-fns pattern }. Mirror of the backend key set. */
const DATE_FORMAT_PRESETS: Record<DateFormatKey, DateFormatPresetDef> = {
  // The offset (date-fns `XXX` → `+02:00`) intentionally differs from the backend strftime `%z`
  // (`+0200`, no colon): same key, per-client rendering.
  ISO_8601: { label: "ISO 8601", pattern: "yyyy-MM-dd'T'HH:mm:ssXXX" },
  ISO_DATETIME: { label: "yyyy-MM-dd HH:mm", pattern: "yyyy-MM-dd HH:mm" },
  ISO_DATETIME_SECONDS: { label: "yyyy-MM-dd HH:mm:ss", pattern: "yyyy-MM-dd HH:mm:ss" },
  EU_DATETIME: { label: "dd/MM/yyyy HH:mm", pattern: "dd/MM/yyyy HH:mm" },
  US_12H: { label: "MM/dd/yyyy hh:mm a", pattern: "MM/dd/yyyy hh:mm a" },
};

const DATE_FORMAT_KEYS = Object.keys(DATE_FORMAT_PRESETS) as Array<DateFormatKey>;

export interface DateFormatPreset {
  /** Stored value: a semantic key. */
  key: DateFormatKey;
  /** Display label shown in the dropdown. */
  label: string;
}

/**
 * Builds the preset list for the dropdown: each entry's `key` is the stored value and `label` is
 * what the user sees. A live example of the selected key is rendered next to the control via
 * {@link formatDateFormatExample}.
 */
export function buildDateFormatPresets(): Array<DateFormatPreset> {
  return DATE_FORMAT_KEYS.map((key) => ({ key, label: DATE_FORMAT_PRESETS[key].label }));
}

/** The date-fns pattern for a semantic key, falling back to the default (mirrors the backend). */
export function patternForKey(key: string): string {
  return (
    (DATE_FORMAT_PRESETS as Record<string, DateFormatPresetDef>)[key]?.pattern ??
    DATE_FORMAT_PRESETS[DEFAULT_DATE_FORMAT].pattern
  );
}

/** Human label for a semantic key, falling back to the raw key when it is unknown. */
export function dateFormatLabel(key: string): string {
  return (DATE_FORMAT_PRESETS as Record<string, DateFormatPresetDef>)[key]?.label ?? key;
}

/**
 * Renders `referenceDate` the way the given semantic key formats dates — the live example shown
 * beside the control. An unknown/invalid key falls back to the default pattern, so a value written
 * by an out-of-date client or the SDK still yields a real example.
 */
export function formatDateFormatExample(key: string, referenceDate: Date = new Date()): string {
  return format(referenceDate, patternForKey(key));
}
