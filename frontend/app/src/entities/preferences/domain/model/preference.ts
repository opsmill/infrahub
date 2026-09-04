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

/**
 * An effective preference plus the value it would fall back to with no override of its own.
 *
 * `inherited` is null when there is nothing to inherit, so the client applies its own default. A
 * non-USER source inherits its own value; a USER source states the value it shadows.
 */
export interface EffectivePreference<T = string> extends Preference<T> {
  inherited: T | null;
}

export interface EffectivePreferences {
  dateFormat: EffectivePreference<DateFormatKey>;
  timezone: EffectivePreference;
}

// Org's own stored values, never merged with personal overrides.
export type GlobalPreferences = PreferenceValues;
