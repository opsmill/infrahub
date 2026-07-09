import { toSource } from "@/entities/preferences/api/effective-preferences.mappers";
import { getEffectivePreferencesFromApi } from "@/entities/preferences/api/get-effective-preferences-from-api";
import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";

export type GetEffectivePreferences = () => Promise<EffectivePreferences>;

export const getEffectivePreferences: GetEffectivePreferences = async () => {
  const { data } = await getEffectivePreferencesFromApi();
  const effective = data.InfrahubEffectivePreferences;

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
