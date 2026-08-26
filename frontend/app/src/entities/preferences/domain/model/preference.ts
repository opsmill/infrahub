import type { PreferenceSource } from "@/shared/api/graphql/generated/types";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";

export type { PreferenceSource };

export interface PreferenceValues {
  dateFormat: DateFormatKey | null;
  timezone: string | null;
}

export interface Preference<T = string> {
  value: T | null;
  source: PreferenceSource;
}

/** An effective preference plus the layer it would fall back to; `inherited` never reports USER. */
export interface EffectivePreference<T = string> extends Preference<T> {
  inherited: Preference<T>;
}

export interface EffectivePreferences {
  dateFormat: EffectivePreference<DateFormatKey>;
  timezone: EffectivePreference;
}

// Org's own stored values, never merged with personal overrides.
export type GlobalPreferences = PreferenceValues;
