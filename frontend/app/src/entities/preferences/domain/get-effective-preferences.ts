import { getEffectivePreferencesFromApi } from "@/entities/preferences/api/get-effective-preferences-from-api";
import type { EffectivePreferences, PreferenceSource } from "@/entities/preferences/domain/types";

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

export const getEffectivePreferences: GetEffectivePreferences = async () => {
  const { data } = await getEffectivePreferencesFromApi();
  const effective = data.InfrahubEffectivePreferences;

  // Each field arrives already resolved (value + source) as its own typed object.
  return {
    dateFormat: {
      value: effective.date_format.value ?? null,
      source: toSource(effective.date_format.source),
    },
    timezone: {
      value: effective.timezone.value ?? null,
      source: toSource(effective.timezone.source),
    },
  };
};
