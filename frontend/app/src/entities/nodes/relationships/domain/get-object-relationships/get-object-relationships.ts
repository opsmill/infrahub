import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";
import { DEFAULT_PAGE_SIZE, type PaginatedResponse } from "@/shared/utils/pagination";

import { getObjectRelationshipsFromApi } from "@/entities/nodes/relationships/api/get-object-relationships-from-api";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

////////////////////////////////////////////////////////////////////////////////////////////////////

/** @deprecated Use DEFAULT_PAGE_SIZE from @/shared/utils/pagination instead */
export const OBJECT_RELATIONSHIPS_PER_PAGE = DEFAULT_PAGE_SIZE;

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface GetObjectRelationshipsParams extends ContextParams, PaginationParams {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipSchema: ModelSchema;
  filters?: Array<Filter>;
}

export type GetObjectRelationships = (
  params: GetObjectRelationshipsParams
) => Promise<PaginatedResponse<NodeObject>>;

export const getObjectRelationships: GetObjectRelationships = async ({
  parentKind,
  relationshipName,
  limit = DEFAULT_PAGE_SIZE,
  ...params
}) => {
  const { data } = await getObjectRelationshipsFromApi({
    parentKind,
    relationshipName,
    limit,
    ...params,
  });

  const relationshipData = data[parentKind]?.edges?.[0]?.node?.[relationshipName];

  return {
    items: relationshipData?.edges?.map(({ node }: { node: NodeObject }) => node) ?? [],
    count: relationshipData?.count ?? 0,
  };
};
