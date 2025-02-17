import { getRelationshipsFromApi } from "@/entities/nodes/relationships/api/get-relationships-from-api";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { ContextParams, PaginationParams } from "@/shared/api/types";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const RELATIONSHIPS_PER_PAGE = 20;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetRelationshipsParams = ContextParams &
  PaginationParams & {
    peer: string;
    search?: string;
    parentId?: string;
  };

export type GetRelationships = (params: GetRelationshipsParams) => Promise<Array<RelationshipNode>>;

export const getRelationships: GetRelationships = async ({
  branchName,
  atDate,
  limit = RELATIONSHIPS_PER_PAGE,
  offset,
  peer,
  search,
  parentId,
}) => {
  const { data } = await getRelationshipsFromApi({
    peer,
    limit,
    offset,
    search,
    branchName,
    atDate,
    parent: parentId ? { name: "parent", value: parentId } : undefined,
  });

  const relationshipsData = data[peer];

  return relationshipsData.edges.map(({ node }: { node: any }) => ({
    id: node.id,
    display_label: node.display_label,
    __typename: node.__typename,
  }));
};
