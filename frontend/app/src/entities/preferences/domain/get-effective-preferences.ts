import { getEffectivePreferencesFromApi } from "@/entities/preferences/api/get-effective-preferences-from-api";
import type {
  EffectivePreferences,
  PreferenceSource,
  ResolvedPreference,
} from "@/entities/preferences/domain/types";

export type GetEffectivePreferences = () => Promise<EffectivePreferences>;

/** Maps the GraphQL `PreferenceSource` enum (USER/GLOBAL/DEFAULT) to our lowercase union. */
function toSource(source: string): PreferenceSource {
  switch (source) {
    case "USER":
      return "user";
    case "GLOBAL":
      return "global";
    case "DEFAULT":
      return "default";
    default:
      // An unrecognised source (e.g. a backend/frontend enum mismatch) must not silently read as a
      // browser default — that would show inherited values as if nothing were configured. Surface
      // it, then fall back conservatively to "default".
      console.warn(`Unknown preference source "${source}"; treating it as the browser default.`);
      return "default";
  }
}

/** Resolved fallback used when a key is missing from the `preferences` list entirely. */
const UNSET: ResolvedPreference = { value: null, source: "default" };

export const getEffectivePreferences: GetEffectivePreferences = async () => {
  const { data } = await getEffectivePreferencesFromApi();
  const effective = data.InfrahubPreferences;

  // Key the flat list of {key,value,source} entries so each field is looked up
  // by name rather than positionally.
  const byKey = new Map<string, ResolvedPreference>(
    effective.preferences.map((entry) => [
      entry.key,
      { value: entry.value ?? null, source: toSource(entry.source) },
    ])
  );

  return {
    dateFormat: byKey.get("date_format") ?? UNSET,
    timezone: byKey.get("timezone") ?? UNSET,
    canEditGlobalPreferences: effective.can_edit_global_preferences,
  };
};
