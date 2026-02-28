import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { GetIpamTreeNodesByParentFromApi } from "@/entities/ipam/ipam-tree/api/get-ipam-tree-nodes-by-parent-from-api";
import { IPAM_NODES_PER_PAGE } from "@/entities/ipam/ipam-tree/ui/queries/get-ipam-tree-nodes-by-parent.query";
import type { IpamTreeNode } from "@/entities/ipam/ipam-tree/types";

export interface GetIpamTreeNodesByParentParams extends PaginationParams, ContextParams {
  namespaceId: string;
  parentObjectId?: string | null;
  search?: string;
}

export type GetIpamTreeNodesByParent = (
  params: GetIpamTreeNodesByParentParams
) => Promise<Array<IpamTreeNode>>;

export const getIpamTreeNodesByParent: GetIpamTreeNodesByParent = async ({
  namespaceId,
  parentObjectId,
  search,
  limit = IPAM_NODES_PER_PAGE,
  offset,
  branchName,
  atDate,
}: GetIpamTreeNodesByParentParams) => {
  const { data, errors } = await GetIpamTreeNodesByParentFromApi({
    namespaceId,
    parentObjectId,
    search,
    limit,
    offset,
    branchName,
    atDate,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return (
    (data[IP_PREFIX_GENERIC]?.edges
      ?.map((edge) => edge.node)
      .filter((n) => !!n) as IpamTreeNode[]) ?? []
  );
};
