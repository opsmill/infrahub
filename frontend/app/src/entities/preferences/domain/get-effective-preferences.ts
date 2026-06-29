import { getEffectivePreferencesFromApi } from "@/entities/preferences/api/get-effective-preferences-from-api";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";

export type GetEffectivePreferences = () => Promise<EffectivePreferences>;

export const getEffectivePreferences: GetEffectivePreferences = async () => {
  const { data } = await getEffectivePreferencesFromApi();
  const preferences = data.InfrahubEffectivePreferences;

  return {
    dateFormat: preferences.date_format ?? null,
    timezone: preferences.timezone ?? null,
    userDateFormat: preferences.user_date_format ?? null,
    userTimezone: preferences.user_timezone ?? null,
    globalDateFormat: preferences.global_date_format ?? null,
    globalTimezone: preferences.global_timezone ?? null,
    canEditGlobalPreferences: preferences.can_edit_global_preferences,
  };
};
