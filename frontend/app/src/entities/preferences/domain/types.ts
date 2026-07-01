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
 * The effective-preferences view (IFC-2720). Backed by the scope-parameterised
 * `InfrahubPreferences` query at its default `EFFECTIVE` scope: each field is
 * resolved per-key (value + source) so consumers know where the value comes
 * from, plus the org-tab gating flag. The raw organisation defaults are NOT part
 * of this view any more — the org-defaults editor reads them via
 * `useGlobalPreferences()` (the `GLOBAL` scope) instead.
 */
export interface EffectivePreferences {
  /** Resolved date-format field: effective value + where it came from. */
  dateFormat: ResolvedPreference;
  /** Resolved timezone field: effective value + where it came from. */
  timezone: ResolvedPreference;
  /** Gates the "Organisation defaults" tab. */
  canEditGlobalPreferences: boolean;
}

/**
 * The raw organisation-wide defaults, read from `InfrahubPreferences(scope: GLOBAL)`.
 * Unlike {@link EffectivePreferences} these are the org's own stored values (never
 * merged with the caller's personal overrides), so the org-defaults editor prefills
 * correctly even for an admin who also set personal overrides.
 */
export type GlobalPreferences = PreferenceValues;
