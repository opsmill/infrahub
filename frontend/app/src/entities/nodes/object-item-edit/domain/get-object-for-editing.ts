import type { ContextParams } from "@/shared/api/types";

import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { ProfileData } from "@/entities/nodes/profiles/types";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { getObjectForEditingFromApi } from "@/entities/nodes/object-item-edit/api/get-object-for-editing-from-api";

export interface GetObjectForEditingParams extends ContextParams {
  schema: NodeSchema | ProfileSchema;
  objectKind: string;
  objectId: string;
  extraRelationshipNames?: string[];
}

export type ObjectForEditingNode = NodeObjectWithMetadata & {
  profiles?: { edges: Array<{ node: ProfileData } | null> };
};

interface ObjectForEditingResponse {
  [kind: string]: {
    edges: Array<{ node: ObjectForEditingNode }>;
  };
}

export interface ObjectForEditing {
  objectDetails: ObjectForEditingNode;
  profiles: ProfileData[];
}

export async function getObjectForEditing(
  params: GetObjectForEditingParams
): Promise<ObjectForEditing> {
  const { objectKind, ...apiParams } = params;
  const result = await getObjectForEditingFromApi(apiParams);

  const data = result.data as ObjectForEditingResponse | null;
  const objectDetails = data?.[objectKind]?.edges?.[0]?.node ?? null;

  if (!objectDetails) {
    throw new Error("No object details found.");
  }

  const profiles: ProfileData[] =
    objectDetails.profiles?.edges
      ?.map((edge) => edge?.node)
      .filter((node): node is ProfileData => node != null) ?? [];

  return { objectDetails, profiles };
}
