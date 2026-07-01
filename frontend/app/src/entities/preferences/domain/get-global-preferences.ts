import { getGlobalPreferencesFromApi } from "@/entities/preferences/api/get-global-preferences-from-api";
import type { GlobalPreferences } from "@/entities/preferences/domain/types";

export type GetGlobalPreferences = () => Promise<GlobalPreferences>;

/**
 * Read the organisation's OWN raw defaults via `InfrahubPreferences(scope: GLOBAL)`.
 * These are the values the org-defaults editor prefills from — the raw global row,
 * not the caller's merged/effective values, so an admin who also set a personal
 * override still sees the organisation default here.
 */
export const getGlobalPreferences: GetGlobalPreferences = async () => {
  const { data } = await getGlobalPreferencesFromApi();
  const byKey = new Map<string, string | null>(
    data.InfrahubPreferences.preferences.map((entry) => [entry.key, entry.value ?? null])
  );

  return {
    dateFormat: byKey.get("date_format") ?? null,
    timezone: byKey.get("timezone") ?? null,
  };
};
