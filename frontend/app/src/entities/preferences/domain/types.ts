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
 * The single effective-preferences view (IFC-2720). One round trip exposes each
 * field already resolved (value + source) for rendering, the raw organisation
 * defaults (for the admin-only org-defaults editor) and the org-tab gating flag.
 * Consumers never inspect raw user_/global_ fields — the resolution lives here.
 */
export interface EffectivePreferences {
  /** Resolved date-format field: effective value + where it came from. */
  dateFormat: ResolvedPreference;
  /** Resolved timezone field: effective value + where it came from. */
  timezone: ResolvedPreference;
  /** Raw org-wide defaults from the GlobalPreference singleton (org-defaults editor). */
  global: {
    dateFormat: string | null;
    timezone: string | null;
  };
  /** Gates the "Organisation defaults" tab. */
  canEditGlobalPreferences: boolean;
}
