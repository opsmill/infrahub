import type { ContextParams } from "@/shared/api/types";

import { getObjectFromApi } from "@/entities/nodes/object/api/get-object-from-api";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export interface GetObjectParams extends ContextParams {
  objectSchema: ModelSchema;
  objectId: string;
  getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
  getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
  relationshipFragment?: Record<string, string>;
}

export type GetObject = (params: GetObjectParams) => Promise<NodeObjectWithMetadata>;

export const getObject: GetObject = async ({
  branchName,
  atDate,
  objectSchema,
  objectId,
  getAttributesVisible = getAttributesVisibleInDetailedView,
  getRelationshipsVisible = getRelationshipsVisibleInDetailedView,
  relationshipFragment,
}) => {
  const attributesVisible = getAttributesVisible(objectSchema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisible(objectSchema.relationships ?? []);

  const schemaKind = objectSchema.kind as string;

  const { data } = await getObjectFromApi({
    schemaKind,
    objectId,
    attributes: attributesVisible,
    relationships: relationshipsVisible,
    relationshipFragment,
    branchName,
    atDate,
  });

  const result =
    data[schemaKind]?.edges?.map((edge: { node: NodeObjectWithMetadata }) => edge.node) ?? [];

  if (!result || result.length === 0) {
    throw new Error(`Cannot find ${objectSchema.label} with id ${objectId}`);
  }

  return result[0];
};
