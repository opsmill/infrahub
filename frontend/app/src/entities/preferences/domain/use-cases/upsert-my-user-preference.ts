import {
  type UpsertUserPreferenceFromApiParams,
  upsertUserPreferenceFromApi,
} from "@/entities/preferences/api/upsert-user-preference-from-api";

export type UpsertMyUserPreferenceParams = UpsertUserPreferenceFromApiParams;

export type UpsertMyUserPreference = (params: UpsertMyUserPreferenceParams) => Promise<void>;

/** Upsert the caller's own row: explicit `null` resets to the global default; omitting leaves unchanged. */
export const upsertMyUserPreference: UpsertMyUserPreference = async (params) => {
  await upsertUserPreferenceFromApi(params);
};
