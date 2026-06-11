import { getEffectivePreferencesFromApi } from "@/entities/preferences/api/get-effective-preferences-from-api";
import type { PreferenceValues } from "@/entities/preferences/domain/types";

export type GetEffectivePreferences = () => Promise<PreferenceValues>;

export const getEffectivePreferences: GetEffectivePreferences = async () => {
  const { data } = await getEffectivePreferencesFromApi();

  return {
    dateFormat: data.InfrahubEffectivePreferences.date_format ?? null,
    timezone: data.InfrahubEffectivePreferences.timezone ?? null,
  };
};
