import { getGlobalPreferencesFromApi } from "@/entities/preferences/api/get-global-preferences-from-api";
import type { GlobalPreferences } from "@/entities/preferences/domain/model/preference";

export type GetGlobalPreferences = () => Promise<GlobalPreferences>;

/** Raw org defaults, not the caller's merged/effective values, so an admin with a personal override still sees the org default. */
export const getGlobalPreferences: GetGlobalPreferences = async () => {
  const { data } = await getGlobalPreferencesFromApi();
  const global = data.InfrahubGlobalPreferences;

  return {
    dateFormat: global.date_format ?? null,
    timezone: global.timezone ?? null,
  };
};
