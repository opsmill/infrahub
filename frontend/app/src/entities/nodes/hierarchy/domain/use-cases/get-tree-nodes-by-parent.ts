import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { GetTreeNodesByParentFromApi } from "@/entities/nodes/hierarchy/api/get-tree-nodes-by-parent-from-api";
import type { NodeCoreWithChildrenCount } from "@/entities/nodes/object/domain/model/node";

/** Page size for tree node queries — larger than default to reduce requests for hierarchical data. */
export const TREE_NODES_PAGE_SIZE = 80;

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
