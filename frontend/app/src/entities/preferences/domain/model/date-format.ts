// The stored value is a semantic key (NOT a date-fns pattern); each client maps the key to its own renderer.
// The key set mirrors backend/infrahub/core/preferences/formats.py (there: key -> strftime). See dev/specs/2026-04-user-preferences.md.

import type { DateFormat } from "@/shared/api/graphql/generated/types";

export type DateFormatKey = DateFormat;

export const DEFAULT_DATE_FORMAT: DateFormatKey = "ISO_DATETIME";

export interface DateFormatPresetDef {
  label: string;
  pattern: string;
}

export const DATE_FORMAT_PRESETS: Record<DateFormatKey, DateFormatPresetDef> = {
  // date-fns `XXX` (`+02:00`) intentionally differs from backend strftime `%z` (`+0200`): same key, per-client rendering.
  ISO_8601: { label: "ISO 8601", pattern: "yyyy-MM-dd'T'HH:mm:ssXXX" },
  ISO_DATETIME: { label: "yyyy-MM-dd HH:mm", pattern: "yyyy-MM-dd HH:mm" },
  ISO_DATETIME_SECONDS: { label: "yyyy-MM-dd HH:mm:ss", pattern: "yyyy-MM-dd HH:mm:ss" },
  EU_DATETIME: { label: "dd/MM/yyyy HH:mm", pattern: "dd/MM/yyyy HH:mm" },
  US_12H: { label: "MM/dd/yyyy hh:mm a", pattern: "MM/dd/yyyy hh:mm a" },
};

export const DATE_FORMAT_KEYS = Object.keys(DATE_FORMAT_PRESETS) as Array<DateFormatKey>;
