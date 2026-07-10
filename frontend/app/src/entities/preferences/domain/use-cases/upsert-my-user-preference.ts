import {
  type UpsertUserPreferenceFromApiParams,
  upsertUserPreferenceFromApi,
} from "@/entities/preferences/api/upsert-user-preference-from-api";

export type UpsertMyUserPreferenceParams = UpsertUserPreferenceFromApiParams;

export type UpsertMyUserPreference = (params: UpsertMyUserPreferenceParams) => Promise<void>;

export const upsertMyUserPreference: UpsertMyUserPreference = async (params) => {
  await upsertUserPreferenceFromApi(params);
};
