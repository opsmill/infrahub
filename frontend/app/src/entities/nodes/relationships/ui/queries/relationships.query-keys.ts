import type { Filter } from "@/shared/hooks/useFilters";

import {
  type ObjectDetailKeysParams,
  objectQueryKeys,
} from "@/entities/nodes/object/ui/queries/object.query-keys";

export interface RelationshipKeysBaseParams extends ObjectDetailKeysParams {
  relationshipName: string;
}

export interface RelationshipListKeysParams extends RelationshipKeysBaseParams {
  filters?: Filter[];
}

export interface RelationshipDetailKeysParams extends RelationshipKeysBaseParams {
  relationshipId: string;
}

export const relationshipsQueryKeys = {
  lists: ({ relationshipName, ...params }: RelationshipKeysBaseParams) =>
    [...objectQueryKeys.detail(params), relationshipName] as const,
  list: ({ filters, ...params }: RelationshipListKeysParams) =>
    [...relationshipsQueryKeys.lists(params), filters] as const,
  count: (params: RelationshipKeysBaseParams) =>
    [...relationshipsQueryKeys.lists(params), "count"] as const,
  properties: ({ relationshipId, ...params }: RelationshipDetailKeysParams) =>
    [...relationshipsQueryKeys.lists(params), relationshipId, "properties"] as const,
};
