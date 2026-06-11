import { getUserPreferenceFromApi } from "@/entities/preferences/api/get-user-preference-from-api";
import type { PreferenceNode } from "@/entities/preferences/domain/types";

export interface GetMyUserPreferenceParams {
  accountId: string;
}

export type GetMyUserPreference = (
  params: GetMyUserPreferenceParams
) => Promise<PreferenceNode | null>;

/** Returns the calling account's override row, or null when none exists yet (lazy creation). */
export const getMyUserPreference: GetMyUserPreference = async ({ accountId }) => {
  const { data } = await getUserPreferenceFromApi({ accountId });

  const node = data.CoreUserPreference?.edges?.[0]?.node;
  if (!node) return null;

  return {
    id: node.id,
    dateFormat: node.date_format?.value ?? null,
    timezone: node.timezone?.value ?? null,
  };
};
