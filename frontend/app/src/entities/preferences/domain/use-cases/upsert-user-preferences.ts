import type { DateFormat } from "@/shared/api/graphql/generated/types";

import { upsertUserPreferencesFromApi } from "@/entities/preferences/api/upsert-user-preferences-from-api";

export interface UpsertUserPreferencesParams {
  /** Explicit `null` resets the field to the global default; omitting leaves it unchanged. */
  dateFormat?: DateFormat | null;
  timezone?: string | null;
}

export type UpsertUserPreferences = (params: UpsertUserPreferencesParams) => Promise<void>;

export const upsertUserPreferences: UpsertUserPreferences = async (params) => {
  const result = await upsertUserPreferencesFromApi(params);

  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to save your preferences");
  }
};
