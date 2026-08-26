import { getEffectivePreferencesFromApi } from "@/entities/preferences/api/get-effective-preferences-from-api";
import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";

export type GetEffectivePreferences = () => Promise<EffectivePreferences>;

export const getEffectivePreferences: GetEffectivePreferences = async () => {
  const { data } = await getEffectivePreferencesFromApi();
  const effective = data.InfrahubEffectivePreferences;

  return {
    dateFormat: {
      value: effective.date_format.value ?? null,
      source: effective.date_format.source,
      inherited: {
        value: effective.date_format.inherited.value ?? null,
        source: effective.date_format.inherited.source,
      },
    },
    timezone: {
      value: effective.timezone.value ?? null,
      source: effective.timezone.source,
      inherited: {
        value: effective.timezone.inherited.value ?? null,
        source: effective.timezone.inherited.source,
      },
    },
  };
};
