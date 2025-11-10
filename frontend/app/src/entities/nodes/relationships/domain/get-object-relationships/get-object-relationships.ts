import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { getObjectRelationshipsFromApi } from "@/entities/nodes/relationships/api/get-object-relationships-from-api";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECT_RELATIONSHIPS_PER_PAGE = 40;

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
) => Promise<Array<NodeObject>>;

export const getObjectRelationships: GetObjectRelationships = async ({
  parentKind,
  relationshipName,
  limit = OBJECT_RELATIONSHIPS_PER_PAGE,
  ...params
}) => {
  const { data } = await getObjectRelationshipsFromApi({
    parentKind,
    relationshipName,
    limit,
    ...params,
  });

  return (
    data[parentKind]?.edges?.[0]?.node?.[relationshipName]?.edges?.map(
      ({ node }: { node: NodeObject }) => node
    ) ?? []
  );
};
