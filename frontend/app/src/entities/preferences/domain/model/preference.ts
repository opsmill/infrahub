import type { PreferenceSource } from "@/shared/api/graphql/generated/types";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";

export type { PreferenceSource };

export interface PreferenceValues {
  dateFormat: DateFormatKey | null;
  timezone: string | null;
}

export interface ResolvedPreference<T = string> {
  value: T | null;
  source: PreferenceSource;
}

// Raw org defaults are NOT here — read those via `useGlobalPreferences()`.
export interface EffectivePreferences {
  dateFormat: ResolvedPreference<DateFormatKey>;
  timezone: ResolvedPreference;
}
