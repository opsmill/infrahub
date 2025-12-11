import {
  type GetProfilesFromApiParams,
  getProfilesFromApi,
} from "@/entities/profiles/api/get-profiles-from-api";
import type { ProfileData } from "@/entities/profiles/types";

export type GetProfilesParams = GetProfilesFromApiParams;

export const getProfiles = async (params: GetProfilesParams): Promise<ProfileData[]> => {
  const { data, errors } = await getProfilesFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const profileNames = params.profiles.map((profile) => profile.name).filter(Boolean);

  return profileNames.reduce<ProfileData[]>((acc, profileName) => {
    const profileEdges = data?.[profileName!]?.edges ?? [];
    const profiles = profileEdges.map((edge: { node: ProfileData }) => edge.node);
    return [...acc, ...profiles];
  }, []);
};
