// Curated date-format presets (IFC-2720). Presets are a UI constraint only:
// the backend stores the pattern verbatim, so the SDK can write any pattern.
// A later PR consolidates these with shared/utils/date.ts.

import { format, formatDistance, subDays } from "date-fns";

/** Literal preset value enabling relative-time rendering ("2 days ago"). */
export const RELATIVE_DATE_FORMAT = "relative";

/** Built-in default applied when neither user nor global preference is set. */
export const DEFAULT_DATE_FORMAT = "yyyy-MM-dd HH:mm";

export interface DateFormatPreset {
  /** Stored value: a date-fns pattern, or the RELATIVE_DATE_FORMAT sentinel. */
  key: string;
  /** Display label: a live example of `key` applied to the reference date. */
  label: string;
}

/**
 * Ordered list of preset keys. Each is a date-fns pattern except the trailing
 * relative sentinel. The stored value is always the raw key.
 */
const DATE_FORMAT_KEYS: ReadonlyArray<string> = [
  DEFAULT_DATE_FORMAT,
  "yyyy-MM-dd",
  "dd/MM/yyyy",
  "dd/MM/yyyy HH:mm",
  "MM/dd/yyyy",
  "MM/dd/yyyy hh:mm a",
  "PPpp",
  RELATIVE_DATE_FORMAT,
];

/**
 * Returns just the example portion for a given key — i.e. how the reference date
 * renders with that pattern. The relative sentinel yields a deterministic
 * "2 days ago"; an unknown key is returned verbatim. Used for the inherited hint.
 */
export function formatDateFormatExample(key: string, referenceDate: Date = new Date()): string {
  if (key === RELATIVE_DATE_FORMAT) {
    return formatDistance(subDays(referenceDate, 2), referenceDate, { addSuffix: true });
  }
  if (!DATE_FORMAT_KEYS.includes(key)) return key;
  return format(referenceDate, key);
}

/**
 * Builds the preset list with labels showing a live example of the reference date
 * rendered with each pattern, e.g. "2026-06-30 14:30 (yyyy-MM-dd HH:mm)".
 */
export function buildDateFormatPresets(referenceDate: Date = new Date()): Array<DateFormatPreset> {
  return DATE_FORMAT_KEYS.map((key) => ({
    key,
    label: `${formatDateFormatExample(key, referenceDate)} (${key})`,
  }));
}
