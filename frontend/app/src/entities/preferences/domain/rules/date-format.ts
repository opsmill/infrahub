import { format } from "date-fns";

import {
  DATE_FORMAT_KEYS,
  DATE_FORMAT_PRESETS,
  type DateFormatKey,
  type DateFormatPresetDef,
  DEFAULT_DATE_FORMAT,
} from "@/entities/preferences/domain/model/date-format";

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
