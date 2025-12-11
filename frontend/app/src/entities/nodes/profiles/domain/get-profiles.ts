import type { ContextParams } from "@/shared/api/types";

import { getProfilesFromApi } from "@/entities/nodes/profiles/api/get-profiles-from-api";
import type { ProfileData } from "@/entities/nodes/profiles/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import type { GenericSchema, NodeSchema, ProfileSchema } from "@/entities/schema/types";

export interface GetProfilesParams extends ContextParams {
  schema: NodeSchema;
}
export type GetProfiles = (schema: GetProfilesParams) => Promise<ProfileData[]>;

export const getProfiles: GetProfiles = async ({ schema, branchName, atDate }) => {
  const inheritedKinds = schema.inherit_from ?? [];

  const inheritedProfileSchemas = [schema.kind, ...inheritedKinds]
    .map((kind) => getSchema(kind).schema as GenericSchema | null)
    .filter((genericSchema) => genericSchema?.generate_profile)
    .map(
      (genericSchema) => getSchema(`Profile${genericSchema!.kind}`).schema as ProfileSchema | null
    )
    .filter((profileSchema) => !!profileSchema);

  if (inheritedProfileSchemas.length === 0) {
    return [];
  }

  const { data, errors } = await getProfilesFromApi({
    profileSchemas: inheritedProfileSchemas,
    branchName,
    atDate,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return inheritedProfileSchemas.reduce((acc, profileSchema) => {
    const profilesData =
      data[profileSchema.kind!]?.edges?.map((edge: { node: ProfileData }) => edge.node) ?? [];
    return [...acc, ...profilesData];
  }, [] as ProfileData[]);
};
