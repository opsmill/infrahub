export interface PreferenceValues {
  dateFormat: string | null;
  timezone: string | null;
}

/**
 * Where a field's effective value comes from. Lowercased mirror of the GraphQL
 * `PreferenceSource` enum (USER / GLOBAL / DEFAULT):
 *   - "user"    → the caller set a personal override.
 *   - "global"  → inherited from the organisation default (no personal override).
 *   - "default" → neither a personal nor an org value is set; falls back to the browser.
 */
export type PreferenceSource = "user" | "global" | "default";

/**
 * A single resolved field: the effective value to render with (null when nothing
 * is defined anywhere) plus the source it came from.
 */
export interface ResolvedPreference {
  value: string | null;
  source: PreferenceSource;
}

/**
 * The effective-preferences view. Backed by the
 * `InfrahubEffectivePreferences` query: each field is resolved (value + source)
 * so consumers know where the value comes from. The raw organisation defaults are
 * NOT part of this view — the org-defaults editor reads them via
 * `useGlobalPreferences()` instead. Gating the org-defaults tab is likewise no
 * longer sourced from here; it is derived from the `manage_global_preferences`
 * global permission (see `useCanManageGlobalPreferences`).
 */
export interface EffectivePreferences {
  /** Resolved date-format field: effective value + where it came from. */
  dateFormat: ResolvedPreference;
  /** Resolved timezone field: effective value + where it came from. */
  timezone: ResolvedPreference;
}

/**
 * The raw organisation-wide defaults, read from `InfrahubPreferences(scope: GLOBAL)`.
 * Unlike {@link EffectivePreferences} these are the org's own stored values (never
 * merged with the caller's personal overrides), so the org-defaults editor prefills
 * correctly even for an admin who also set personal overrides.
 */
export type GlobalPreferences = PreferenceValues;
