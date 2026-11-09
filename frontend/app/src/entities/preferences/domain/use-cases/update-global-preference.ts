import type { DateFormat } from "@/shared/api/graphql/generated/types";

import { updateGlobalPreferenceFromApi } from "@/entities/preferences/api/update-global-preference-from-api";

export interface UpdateGlobalPreferenceParams {
  /** Explicit `null` clears the field; omitting the key leaves it unchanged. */
  dateFormat?: DateFormat | null;
  timezone?: string | null;
}

export type UpdateGlobalPreference = (params: UpdateGlobalPreferenceParams) => Promise<void>;

export const updateGlobalPreference: UpdateGlobalPreference = async (params) => {
  const result = await updateGlobalPreferenceFromApi(params);

  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to update the global preferences");
  }
};
