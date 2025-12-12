import type { ContextParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export interface ObjectKeysBaseParams extends ContextParams {
  objectKind: string;
}

export interface ObjectListKeysParams extends ObjectKeysBaseParams {
  filters?: Filter[];
}

export interface ObjectDetailKeysParams extends ObjectKeysBaseParams {
  objectId: string;
  objectSchema?: ModelSchema;
  getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
  getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
}

export interface ObjectConvertFieldsMappingKeysParams extends ContextParams {
  sourceKind: string;
  targetKind: string;
}

export interface ObjectTreeKeysParams extends ObjectKeysBaseParams {
  parentObjectId?: string | null;
}

export const objectQueryKeys = {
  all: ["objects"] as const,
  allWithContext: ({ branchName, atDate }: ContextParams) =>
    [...objectQueryKeys.all, branchName, atDate] as const,
  lists: (params: ObjectKeysBaseParams) =>
    [...objectQueryKeys.allWithContext(params), params.objectKind] as const,
  convert: (params: ObjectConvertFieldsMappingKeysParams) =>
    [
      ...objectQueryKeys.lists({ ...params, objectKind: params.sourceKind }),
      "fields-mapping-type-conversion",
      params.targetKind,
    ] as const,
  count: (params: ObjectKeysBaseParams) => [...objectQueryKeys.lists(params), "count"] as const,
  list: (params: ObjectListKeysParams) =>
    [...objectQueryKeys.lists(params), params.filters] as const,
  profiles: (params: ObjectKeysBaseParams) =>
    [...objectQueryKeys.lists(params), "profiles"] as const,
  detail: (params: ObjectDetailKeysParams) =>
    [
      ...objectQueryKeys.lists(params),
      params.objectId,
      ...getAttributesKey(params),
      ...getRelationshipsKey(params),
    ] as const,
  ancestors: (params: ObjectDetailKeysParams) =>
    [...objectQueryKeys.detail(params), "ancestors"] as const,
  tree: ({ parentObjectId, ...params }: ObjectTreeKeysParams) =>
    [...objectQueryKeys.lists(params), "tree", parentObjectId] as const,
};

const getAttributesKey = (params: ObjectDetailKeysParams) => {
  if (!params?.objectSchema?.attributes) {
    return [];
  }

  const getAttributes = params?.getAttributesVisible ?? getAttributesVisibleInDetailedView;

  return getAttributes(params.objectSchema.attributes).map((attribute) => {
    return attribute.name;
  });
};

const getRelationshipsKey = (params: ObjectDetailKeysParams) => {
  if (!params?.objectSchema?.relationships) {
    return [];
  }

  const getRelationships = params?.getRelationshipsVisible ?? getRelationshipsVisibleInDetailedView;

  return getRelationships(params.objectSchema.relationships).map((relationship) => {
    return relationship.name;
  });
};
