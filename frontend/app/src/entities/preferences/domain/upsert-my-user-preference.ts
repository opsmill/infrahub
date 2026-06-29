import {
  type UpsertUserPreferenceFromApiParams,
  upsertUserPreferenceFromApi,
} from "@/entities/preferences/api/upsert-user-preference-from-api";

export type UpsertMyUserPreferenceParams = UpsertUserPreferenceFromApiParams;

export type UpsertMyUserPreference = (params: UpsertMyUserPreferenceParams) => Promise<void>;

/**
 * Upsert the caller's own preference row. Passing explicit `null` for a field
 * resets it to the global default; omitting a field leaves it unchanged.
 */
export const upsertMyUserPreference: UpsertMyUserPreference = async (params) => {
  await upsertUserPreferenceFromApi(params);
};
