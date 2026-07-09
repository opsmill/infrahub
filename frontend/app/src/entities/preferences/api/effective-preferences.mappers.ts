import type { PreferenceSource } from "@/entities/preferences/domain/model/preference";

/** Maps the GraphQL `PreferenceSource` enum (USER/GLOBAL/DEFAULT) to our lowercase union. */
export function toSource(source: string): PreferenceSource {
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
