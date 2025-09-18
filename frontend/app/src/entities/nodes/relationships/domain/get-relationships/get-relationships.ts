import {
  getRelationshipsFromApi,
  type getRelationshipsFromApiParams,
} from "@/entities/nodes/relationships/api/get-relationships-from-api";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const RELATIONSHIPS_PER_PAGE = 20;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetRelationshipsParams = getRelationshipsFromApiParams;

export type GetRelationships = (params: GetRelationshipsParams) => Promise<Array<RelationshipNode>>;

export const getRelationships: GetRelationships = async ({
  branchName,
  atDate,
  limit = RELATIONSHIPS_PER_PAGE,
  offset,
  peer,
  search,
  filterQuery,
}) => {
  const { data } = await getRelationshipsFromApi({
    peer,
    limit,
    offset,
    search,
    branchName,
    atDate,
    filterQuery,
  });

  const relationshipsData = data[peer];

  return relationshipsData.edges.map(({ node }: { node: any }) => ({
    id: node.id,
    display_label: node.display_label,
    __typename: node.__typename,
  }));
};
