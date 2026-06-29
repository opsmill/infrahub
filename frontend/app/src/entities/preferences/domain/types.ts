export interface PreferenceValues {
  dateFormat: string | null;
  timezone: string | null;
}

/**
 * The single effective-preferences view (IFC-2720). One round trip exposes the
 * merged values (rendering), the caller's own override (`user*`, null when none),
 * the org default (`global*`, null when unset) and the org-tab gating flag.
 */
export interface EffectivePreferences {
  /** Merged value to render with: user override > global default > null. */
  dateFormat: string | null;
  timezone: string | null;
  /** The caller's OWN override, or null when they have none. */
  userDateFormat: string | null;
  userTimezone: string | null;
  /** The organisation default, or null when unset. */
  globalDateFormat: string | null;
  globalTimezone: string | null;
  /** Gates the "Organisation defaults" tab. */
  canEditGlobalPreferences: boolean;
}
