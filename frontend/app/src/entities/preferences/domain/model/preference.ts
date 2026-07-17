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

export interface EffectivePreferences {
  dateFormat: Preference<DateFormatKey>;
  timezone: Preference;
}
