import {
  type UpdateGlobalPreferenceFromApiParams,
  updateGlobalPreferenceFromApi,
} from "@/entities/preferences/api/update-global-preference-from-api";

export type UpdateGlobalPreferenceParams = UpdateGlobalPreferenceFromApiParams;

export type UpdateGlobalPreference = (params: UpdateGlobalPreferenceParams) => Promise<void>;

export const updateGlobalPreference: UpdateGlobalPreference = async (params) => {
  await updateGlobalPreferenceFromApi(params);
};
