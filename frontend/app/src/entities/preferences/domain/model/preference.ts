import type { PreferenceSource } from "@/shared/api/graphql/generated/types";

export type { PreferenceSource };

export interface PreferenceValues {
  dateFormat: string | null;
  timezone: string | null;
}

export interface ResolvedPreference {
  value: string | null;
  source: PreferenceSource;
}

// Raw org defaults are NOT here — read those via `useGlobalPreferences()`.
export interface EffectivePreferences {
  dateFormat: ResolvedPreference;
  timezone: ResolvedPreference;
}

// Org's own stored values, never merged with personal overrides.
export type GlobalPreferences = PreferenceValues;
