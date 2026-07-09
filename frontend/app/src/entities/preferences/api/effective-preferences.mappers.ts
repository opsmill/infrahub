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
      // Surface an enum mismatch rather than silently reading it as a browser default, which would
      // show inherited values as if nothing were configured; then fall back conservatively.
      console.warn(`Unknown preference source "${source}"; treating it as the browser default.`);
      return "default";
  }
}
