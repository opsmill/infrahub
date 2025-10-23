import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { getObjectHierarchyChildrenFromApi } from "@/entities/nodes/hierarchy/api/get-object-hierarchy-children-from-api";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/hierarchy/domain/get-object-children.query";
import type { NodeCoreWithChildrenCount } from "@/entities/nodes/types";

export interface GetObjectChildrenParams extends PaginationParams, ContextParams {
  objectKind: string;
  parentObjectId?: string | null;
}

export type GetObjectChildren = (
  params: GetObjectChildrenParams
) => Promise<Array<NodeCoreWithChildrenCount>>;

export const getObjectChildren: GetObjectChildren = async ({
  objectKind,
  parentObjectId,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
}: GetObjectChildrenParams) => {
  const { data } = await getObjectHierarchyChildrenFromApi({
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
