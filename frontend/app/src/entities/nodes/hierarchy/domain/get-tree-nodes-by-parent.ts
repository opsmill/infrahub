import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { GetTreeNodesByParentFromApi } from "@/entities/nodes/hierarchy/api/get-tree-nodes-by-parent-from-api";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/hierarchy/domain/get-tree-nodes-by-parent.query";
import type { NodeCoreWithChildrenCount } from "@/entities/nodes/types";

export interface GetTreeNodesByParentParams extends PaginationParams, ContextParams {
  objectKind: string;
  parentObjectId?: string | null;
}

export type GetTreeNodesByParent = (
  params: GetTreeNodesByParentParams
) => Promise<Array<NodeCoreWithChildrenCount>>;

export const getTreeNodesByParent: GetTreeNodesByParent = async ({
  objectKind,
  parentObjectId,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
}: GetTreeNodesByParentParams) => {
  const { data } = await GetTreeNodesByParentFromApi({
    objectKind,
    parentObjectId,
    limit,
    offset,
    branchName,
    atDate,
  });

  return (
    data[objectKind]?.edges?.map((edge: { node: NodeCoreWithChildrenCount }) => edge.node) ?? []
  );
};
