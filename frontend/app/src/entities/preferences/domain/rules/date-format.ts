import {
  DATE_FORMAT_KEYS,
  DATE_FORMAT_PRESETS,
  type DateFormatKey,
  type DateFormatPresetDef,
  DEFAULT_DATE_FORMAT,
} from "@/entities/preferences/domain/model/date-format";

export interface DateFormatPreset {
  key: DateFormatKey;
  label: string;
}

export function buildDateFormatPresets(): Array<DateFormatPreset> {
  return DATE_FORMAT_KEYS.map((key) => ({ key, label: DATE_FORMAT_PRESETS[key].label }));
}

// An unknown/invalid key (e.g. written by an out-of-date client or the SDK) falls back to the default pattern so dates still render.
export function dateFormatPattern(key: string): string {
  return (
    (DATE_FORMAT_PRESETS as Record<string, DateFormatPresetDef>)[key]?.pattern ??
    DATE_FORMAT_PRESETS[DEFAULT_DATE_FORMAT].pattern
  );
}

export function dateFormatLabel(key: string): string {
  return (DATE_FORMAT_PRESETS as Record<string, DateFormatPresetDef>)[key]?.label ?? key;
}
