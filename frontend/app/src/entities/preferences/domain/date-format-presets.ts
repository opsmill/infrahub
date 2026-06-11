// Curated date-format presets (IFC-2720). Presets are a UI constraint only:
// the backend stores the pattern verbatim, so the SDK can write any pattern.
// A later PR consolidates these with shared/utils/date.ts.

/** Literal preset value enabling relative-time rendering ("2 days ago"). */
export const RELATIVE_DATE_FORMAT = "relative";

/** Built-in default applied when neither user nor global preference is set. */
export const DEFAULT_DATE_FORMAT = "yyyy-MM-dd HH:mm";

export interface DateFormatPreset {
  key: string;
  label: string;
}

export const DATE_FORMAT_PRESETS: Array<DateFormatPreset> = [
  { key: DEFAULT_DATE_FORMAT, label: "2026-06-11 14:30 (yyyy-MM-dd HH:mm)" },
  { key: "yyyy-MM-dd", label: "2026-06-11 (yyyy-MM-dd)" },
  { key: "dd/MM/yyyy", label: "11/06/2026 (dd/MM/yyyy)" },
  { key: "dd/MM/yyyy HH:mm", label: "11/06/2026 14:30 (dd/MM/yyyy HH:mm)" },
  { key: "MM/dd/yyyy", label: "06/11/2026 (MM/dd/yyyy)" },
  { key: "MM/dd/yyyy hh:mm a", label: "06/11/2026 02:30 PM (MM/dd/yyyy hh:mm a)" },
  { key: "PPpp", label: "Jun 11, 2026, 2:30:00 PM (PPpp)" },
  { key: RELATIVE_DATE_FORMAT, label: "Relative (2 days ago)" },
];
