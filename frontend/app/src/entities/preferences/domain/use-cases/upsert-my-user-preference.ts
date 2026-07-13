import type { DateFormat } from "@/shared/api/graphql/generated/types";

import { upsertUserPreferenceFromApi } from "@/entities/preferences/api/upsert-user-preference-from-api";

export interface UpsertMyUserPreferenceParams {
  /** Explicit `null` resets the field to the global default; omitting leaves it unchanged. */
  dateFormat?: DateFormat | null;
  timezone?: string | null;
}

export type UpsertMyUserPreference = (params: UpsertMyUserPreferenceParams) => Promise<void>;

export const upsertMyUserPreference: UpsertMyUserPreference = async (params) => {
  const result = await upsertUserPreferenceFromApi(params);

  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to save your preferences");
  }
};
