import { DEFAULT_PAGE_SIZE, type PaginatedResponse } from "@/shared/utils/pagination";

import {
  getRelationshipsFromApi,
  type getRelationshipsFromApiParams,
} from "@/entities/nodes/relationships/api/get-relationships-from-api";
import type { NodeCore } from "@/entities/nodes/types";

export type GetRelationshipsParams = getRelationshipsFromApiParams;

export type GetRelationships = (
  params: GetRelationshipsParams
) => Promise<PaginatedResponse<NodeCore>>;

export const getRelationships: GetRelationships = async ({
  branchName,
  atDate,
  limit = DEFAULT_PAGE_SIZE,
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

  return {
    items: relationshipsData.edges.map(({ node }: { node: NodeCore }) => node),
    count: relationshipsData.count ?? 0,
  };
};
