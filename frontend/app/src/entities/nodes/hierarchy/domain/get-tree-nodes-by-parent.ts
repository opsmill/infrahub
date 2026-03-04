import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { GetTreeNodesByParentFromApi } from "@/entities/nodes/hierarchy/api/get-tree-nodes-by-parent-from-api";
import { TREE_NODES_PAGE_SIZE } from "@/entities/nodes/hierarchy/ui/queries/get-tree-nodes-by-parent.query";
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
  limit = TREE_NODES_PAGE_SIZE,
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
