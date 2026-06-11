import { getGlobalPreferenceFromApi } from "@/entities/preferences/api/get-global-preference-from-api";
import type { PreferenceNode } from "@/entities/preferences/domain/types";

export type GetGlobalPreference = () => Promise<PreferenceNode | null>;

/** Reads the singleton CoreGlobalPreference row (seeded at initialization). */
export const getGlobalPreference: GetGlobalPreference = async () => {
  const { data } = await getGlobalPreferenceFromApi();

  const node = data.CoreGlobalPreference?.edges?.[0]?.node;
  if (!node) return null;

  return {
    id: node.id,
    dateFormat: node.date_format?.value ?? null,
    timezone: node.timezone?.value ?? null,
  };
};
