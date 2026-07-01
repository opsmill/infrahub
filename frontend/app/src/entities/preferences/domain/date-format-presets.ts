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
  /** Display label: the pattern/sentinel itself (always equal to `key`). */
  label: string;
}

/**
 * Ordered list of preset keys — all include a time component (hours & minutes), since
 * these preferences drive date *and time* rendering across the app. Each is a date-fns
 * pattern except the trailing relative sentinel. The stored value is always the raw key.
 */
const DATE_FORMAT_KEYS: ReadonlyArray<string> = [
  DEFAULT_DATE_FORMAT, //          2026-07-01 14:30      (ISO, 24h)
  "yyyy-MM-dd HH:mm:ss", //        2026-07-01 14:30:00   (ISO, with seconds)
  "dd/MM/yyyy HH:mm", //           01/07/2026 14:30      (European, 24h)
  "MM/dd/yyyy hh:mm a", //         07/01/2026 02:30 PM   (US, 12h)
  "d MMM yyyy, HH:mm", //          1 Jul 2026, 14:30     (month name)
  "PPpp", //                       locale-aware long date + time
  RELATIVE_DATE_FORMAT, //         2 days ago
];

/**
 * Returns just the example portion for a given key — i.e. how the reference date
 * renders with that pattern. The relative sentinel yields a deterministic
 * "2 days ago". Any valid date-fns pattern is formatted (so a stored value written
 * via the SDK, or a preset removed from the list, still renders); an invalid pattern
 * is returned verbatim.
 */
export function formatDateFormatExample(key: string, referenceDate: Date = new Date()): string {
  if (key === RELATIVE_DATE_FORMAT) {
    return formatDistance(subDays(referenceDate, 2), referenceDate, { addSuffix: true });
  }
  try {
    return format(referenceDate, key);
  } catch {
    return key;
  }
}

/**
 * Builds the preset list. The label is the pattern/sentinel itself (key === label),
 * e.g. "yyyy-MM-dd HH:mm", "dd/MM/yyyy", "relative". A live example of the selected
 * pattern is rendered next to the control via {@link formatDateFormatExample}.
 */
export function buildDateFormatPresets(): Array<DateFormatPreset> {
  return DATE_FORMAT_KEYS.map((key) => ({ key, label: key }));
}
