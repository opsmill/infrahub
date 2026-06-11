import {
  type DeleteUserPreferenceFromApiParams,
  deleteUserPreferenceFromApi,
} from "@/entities/preferences/api/delete-user-preference-from-api";

export type ResetMyUserPreferenceParams = DeleteUserPreferenceFromApiParams;

export type ResetMyUserPreference = (params: ResetMyUserPreferenceParams) => Promise<void>;

/**
 * Reset = delete the override row. The row is recreated lazily on the next
 * save, so deletion is the cleanest way to fall back to the global defaults
 * for every preference at once.
 */
export const resetMyUserPreference: ResetMyUserPreference = async (params) => {
  await deleteUserPreferenceFromApi(params);
};
