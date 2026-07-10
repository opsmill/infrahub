import type { PreferenceSource } from "@/shared/api/graphql/generated/types";

export type { PreferenceSource };

export interface PreferenceValues {
  dateFormat: string | null;
  timezone: string | null;
}

/** A resolved field: effective value (null when unset everywhere) plus its source. */
export interface ResolvedPreference {
  value: string | null;
  source: PreferenceSource;
}

/**
 * Effective view (`InfrahubEffectivePreferences`): each field resolved to value + source. Raw org
 * defaults are NOT here — read those via `useGlobalPreferences()`; tab gating comes from the
 * `manage_global_preferences` permission (see `useCanManageGlobalPreferences`).
 */
export interface EffectivePreferences {
  dateFormat: ResolvedPreference;
  timezone: ResolvedPreference;
}

/**
 * Raw org-wide defaults (`InfrahubPreferences(scope: GLOBAL)`): the org's own stored values, never
 * merged with personal overrides, so the org-defaults editor prefills correctly even for an admin
 * who also set personal overrides.
 */
export type GlobalPreferences = PreferenceValues;
