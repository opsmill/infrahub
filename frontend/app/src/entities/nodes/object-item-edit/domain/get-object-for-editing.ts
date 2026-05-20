import type { ContextParams } from "@/shared/api/types";

import {
  type GetObjectForEditingFromApiParams,
  getObjectForEditingFromApi,
} from "@/entities/nodes/object-item-edit/api/get-object-for-editing-from-api";
import type { ProfileData } from "@/entities/nodes/profiles/types";
import type { NodeFieldsWithMetadata } from "@/entities/nodes/types";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

export interface GetObjectForEditingParams extends ContextParams {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
  extraRelationshipNames?: string[];
}

export interface ObjectForEditing {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  objectDetails: NodeFieldsWithMetadata & Record<string, any>;
  profiles: ProfileData[];
}

export async function getObjectForEditing(
  params: GetObjectForEditingParams
): Promise<ObjectForEditing> {
  const result = await getObjectForEditingFromApi(params as GetObjectForEditingFromApiParams);

  const schemaKind = params.schema.kind as string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const objectDetails = (result.data as any)?.[schemaKind]?.edges[0]?.node ?? null;

  if (!objectDetails) {
    throw new Error("No object details found.");
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const profiles: ProfileData[] =
    objectDetails?.profiles?.edges?.map((edge: any) => edge?.node) ?? [];

  return { objectDetails, profiles };
}
